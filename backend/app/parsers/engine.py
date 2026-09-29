"""
engine.py — YAML-driven vendor-agnostic parse engine.

Architecture:
  packs/<pack_name>/
      fingerprint.yaml   → detection patterns + tokenizer_family
      spec.yaml          → extraction field definitions (regex + scope)
      remediation.yaml   → fix CLI templates (optional)

This engine:
  1. Discovers all packs on startup (auto-discovers any new directory).
  2. Runs fingerprint scoring to pick the best matching pack.
  3. Tokenizes the raw config using the pack's declared tokenizer_family.
  4. Extracts NormalizedField-compatible dicts using spec.yaml field rules.
  5. Looks up remediation templates from remediation.yaml when needed.
"""

import re
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

log = logging.getLogger(__name__)

PACKS_DIR = Path(__file__).parent / "packs"
AMBIGUITY_MARGIN = 0.15
MIN_SCORE = 0.15


# ──────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────

@dataclass
class DetectionResult:
    pack_name: str
    vendor: str
    tokenizer_family: str
    assumed_command: str
    confidence: float
    ambiguous: bool
    spec_hash: str


@dataclass
class ExtractedField:
    control_area: str
    value: str
    instance_id: Optional[str]
    raw_line: str
    confidence: float = 1.0
    source_lane: str = "deterministic"


@dataclass
class ParseResult:
    pack_name: str
    spec_hash: str
    fields: list[ExtractedField] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    coverage_score: float = 0.0   # fields_found / fields_defined


# ──────────────────────────────────────────────────────────────
# Pack loading (cached at module level)
# ──────────────────────────────────────────────────────────────

_PACK_CACHE: dict[str, dict] = {}


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _spec_hash(spec_path: Path) -> str:
    """SHA1 of the spec file — used to detect stale ParseRuns."""
    return hashlib.sha1(spec_path.read_bytes()).hexdigest()[:12]


def _all_packs() -> dict[str, dict]:
    """Discover and cache all packs from the packs/ directory."""
    global _PACK_CACHE
    if _PACK_CACHE:
        return _PACK_CACHE

    for pack_dir in sorted(PACKS_DIR.iterdir()):
        fp_path = pack_dir / "fingerprint.yaml"
        spec_path = pack_dir / "spec.yaml"
        if not fp_path.exists() or not spec_path.exists():
            continue

        try:
            fp = _load_yaml(fp_path)
            spec = _load_yaml(spec_path)
            rem_path = pack_dir / "remediation.yaml"
            remediation = _load_yaml(rem_path) if rem_path.exists() else {}

            _PACK_CACHE[pack_dir.name] = {
                "fingerprint": fp,
                "spec": spec,
                "remediation": remediation,
                "spec_hash": _spec_hash(spec_path),
            }
            log.debug("Loaded pack: %s", pack_dir.name)
        except Exception as exc:
            log.warning("Failed to load pack %s: %s", pack_dir.name, exc)

    return _PACK_CACHE


def reload_packs() -> None:
    """Force a cache reload — useful after adding a new pack at runtime."""
    global _PACK_CACHE
    _PACK_CACHE = {}
    _all_packs()


def config_hash(raw_config: str, pack_name: Optional[str] = None) -> str:
    """
    Compute a stable SHA-256 hash of raw_config for Phase 5 upload idempotency.

    If pack_name is provided, lines matching the pack's `hash_ignore` regex list
    are stripped before hashing, so volatile headers (timestamps, byte counts)
    don't cause false "content changed" mismatches on an otherwise identical
    config.  Line endings are normalised to \\n before hashing.
    """
    lines = raw_config.splitlines()

    if pack_name:
        packs = _all_packs()
        ignore_patterns: list[re.Pattern] = []
        if pack_name in packs:
            fp = packs[pack_name].get("fingerprint", {})
            for pattern_str in fp.get("hash_ignore", []):
                try:
                    ignore_patterns.append(re.compile(pattern_str, re.IGNORECASE))
                except re.error as e:
                    log.warning("Bad hash_ignore regex %r in pack %s: %s", pattern_str, pack_name, e)

        if ignore_patterns:
            lines = [
                line for line in lines
                if not any(p.match(line) for p in ignore_patterns)
            ]

    normalised = "\n".join(lines)
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


# ──────────────────────────────────────────────────────────────
# 1. Vendor Detection
# ──────────────────────────────────────────────────────────────

def detect(raw_config: str) -> Optional[DetectionResult]:
    """
    Run all pack fingerprints against raw_config and return the best match.
    Returns None only if nothing clears MIN_SCORE.
    """
    packs = _all_packs()
    scored: list[tuple[float, str, dict]] = []

    for pack_name, pack in packs.items():
        fp = pack["fingerprint"]
        score = 0.0
        for entry in fp.get("patterns", []):
            pattern = entry["pattern"]
            weight = entry["weight"]
            if re.search(pattern, raw_config, re.MULTILINE | re.IGNORECASE):
                score += weight
        scored.append((round(score, 3), pack_name, pack))

    scored.sort(key=lambda t: t[0], reverse=True)
    best_score, best_name, best_pack = scored[0]

    if best_score < MIN_SCORE:
        return None

    runner_up = scored[1][0] if len(scored) > 1 else 0.0
    ambiguous = (best_score - runner_up) < AMBIGUITY_MARGIN
    confidence = min(best_score, 1.0)
    if ambiguous:
        confidence = round(confidence * 0.6, 2)

    fp = best_pack["fingerprint"]
    return DetectionResult(
        pack_name=best_name,
        vendor=fp.get("vendor", best_name),
        tokenizer_family=fp.get("tokenizer_family", "flat"),
        assumed_command=fp.get("assumed_command", "show running-config"),
        confidence=round(confidence, 3),
        ambiguous=ambiguous,
        spec_hash=best_pack["spec_hash"],
    )


# ──────────────────────────────────────────────────────────────
# 2. Tokenization (flat-line engine — works for indent_delimited,
#    brace_delimited, and flat without needing external libraries)
# ──────────────────────────────────────────────────────────────

@dataclass
class Line:
    text: str
    indent: int
    parent_text: Optional[str]       # immediate parent's text (for scoped fields)
    raw: str
    ancestors: tuple = ()            # full path from root (Phase 4b: groups exclusion)
    in_banner: bool = False          # Phase 4a: True if line is inside a banner block


# Detect banner opening lines: `banner motd ^`, `banner login C`, etc.
_BANNER_OPEN_RE = re.compile(
    r"^banner\s+\S+\s+(?P<delim>\S)", re.IGNORECASE
)


def _tokenize(raw_config: str) -> list[Line]:
    """
    Produce a flat list of Line objects with indent level and parent context.
    This is the single tokenizer that replaces the old indent/brace split.
    It works on Cisco IOS, Arista EOS, Juniper JunOS, and flat formats.

    Phase 4a: Banner injection fix — lines inside a banner block are tagged
    in_banner=True and skipped by extract().

    Phase 4b: Juniper groups fix — each Line carries an `ancestors` tuple
    with the full ancestor chain. extract() rejects global-scope matches whose
    ancestors include 'groups', preventing groups-block values from shadowing
    real top-level values regardless of which block appears first in the file.
    """
    lines: list[Line] = []
    # Stack of (indent_level, text) for parent tracking
    parent_stack: list[tuple[int, str]] = []

    # Banner state tracking
    in_banner: bool = False
    banner_delim: str = ""

    for raw in raw_config.splitlines():
        stripped = raw.rstrip()
        if not stripped:
            continue

        # ── Banner block handling (Phase 4a) ────────────────────────────────
        if in_banner:
            # A line that contains the delimiter character ends the banner
            if banner_delim and banner_delim in stripped:
                in_banner = False
                banner_delim = ""
            # Either way, this line is banner body — skip it entirely
            # (don't even add to `lines` so it can't be matched)
            continue

        # Skip comment lines AFTER banner check
        clean_check = stripped.lstrip()
        if clean_check.startswith("!") or clean_check.startswith("#"):
            continue

        # Detect banner opening
        banner_m = _BANNER_OPEN_RE.match(clean_check)
        if banner_m:
            banner_delim = banner_m.group("delim")
            # Check if the banner body starts on the same line (after delimiter)
            # e.g. `banner motd ^C text ^C` (single-line banner)
            rest = clean_check[banner_m.end():]
            if banner_delim in rest:
                # Single-line banner — no multi-line body to skip
                in_banner = False
                banner_delim = ""
            else:
                in_banner = True
            # The banner header line itself is not a config field we care about
            continue

        # Strip Juniper semicolons for matching purposes
        clean = stripped.lstrip().rstrip(";").rstrip()

        # Strip Juniper opening brace
        if clean.endswith("{"):
            clean = clean[:-1].strip()

        # Skip closing braces
        if clean.strip() == "}":
            if parent_stack:
                parent_stack.pop()
            continue

        indent = len(stripped) - len(stripped.lstrip())

        # Pop parent stack until we find the correct parent level
        while parent_stack and parent_stack[-1][0] >= indent:
            parent_stack.pop()

        parent_text = parent_stack[-1][1] if parent_stack else None

        # Build full ancestor chain (Phase 4b)
        ancestors: tuple = tuple(entry[1] for entry in parent_stack)

        line = Line(
            text=clean,
            indent=indent,
            parent_text=parent_text,
            raw=raw,
            ancestors=ancestors,
            in_banner=False,
        )
        lines.append(line)

        # Push this line as a potential parent for deeper lines
        parent_stack.append((indent, clean))

    return lines



# ──────────────────────────────────────────────────────────────
# 3. Extraction via spec.yaml
# ──────────────────────────────────────────────────────────────

_INTERFACE_RE = re.compile(
    r"^(interface|vlan|port-channel|tunnel)\s+(\S+)", re.IGNORECASE
)
_VTY_LINE_RE = re.compile(
    r"^line\s+(vty\s+\d+(?:\s+\d+)?|con\s+0|aux\s+0)", re.IGNORECASE
)


def _apply_transform(value: Optional[str], transform: Optional[str]) -> Optional[str]:
    """Apply a semantic transform to the raw captured value."""
    if value is None:
        return None
    if transform is None:
        return value
    if transform == "present_absent":
        # 'no ' prefix → disabled, no prefix → enabled
        return "disabled" if value.lower().startswith("no ") else "enabled"
    if transform == "present_absent_inverted":
        # 'no ' prefix → enabled (e.g., 'no ip proxy-arp' → proxy_arp=disabled is good)
        return "enabled" if value.lower().startswith("no ") else "disabled"
    if transform == "exec_timeout_seconds":
        # Converts "minutes seconds" raw string to total seconds.
        # "10 0"  → "600"   (10 min, 0 sec = 600 s)
        # "0 0"   → "0"     (never times out — must FAIL a max_value rule)
        # "0 30"  → "30"    (30-second timeout)
        parts = value.split()
        try:
            total = int(parts[0]) * 60 + int(parts[1])
            return str(total)
        except (IndexError, ValueError):
            log.warning("exec_timeout_seconds transform failed for value %r", value)
            return value
    if transform == "junos_inactive_prefix":
        # Phase 4c: Juniper `inactive: <name>` in brace format → disabled.
        # The tokenizer strips semicolons so the line text looks like
        # "inactive: telnet" — capture group captures "inactive: telnet".
        # We check for the "inactive:" prefix and map it to disabled.
        return "disabled" if value.lower().startswith("inactive:") else "enabled"
    # Unknown transform — return raw value unchanged (do not silently drop)
    log.warning("Unknown transform %r applied to value %r", transform, value)
    return value


def extract(raw_config: str, pack_name: str) -> ParseResult:
    """
    Run the spec.yaml field rules for pack_name against raw_config.
    Returns a ParseResult containing all extracted fields.
    """
    packs = _all_packs()
    if pack_name not in packs:
        return ParseResult(
            pack_name=pack_name,
            spec_hash="",
            warnings=[f"Pack '{pack_name}' not found in {PACKS_DIR}"],
        )

    pack = packs[pack_name]
    spec_fields: list[dict] = pack["spec"].get("fields", [])
    spec_hash = pack["spec_hash"]

    lines = _tokenize(raw_config)
    results: list[ExtractedField] = []
    found_areas: set[str] = set()

    # Build compiled regex cache
    compiled: list[tuple[dict, re.Pattern]] = []
    for f_def in spec_fields:
        try:
            compiled.append((f_def, re.compile(f_def["match"], re.IGNORECASE)))
        except re.error as e:
            log.warning("Bad regex in pack %s field %s: %s", pack_name, f_def.get("control_area"), e)

    for line in lines:
        # Determine current scope context
        current_interface: Optional[str] = None
        current_vty: Optional[str] = None

        if line.parent_text:
            m = _INTERFACE_RE.match(line.parent_text)
            if m:
                current_interface = line.parent_text
            m2 = _VTY_LINE_RE.match(line.parent_text)
            if m2:
                current_vty = m2.group(1)

        for f_def, pattern in compiled:
            control_area = f_def["control_area"]
            scope = f_def.get("scope", "global")
            multi = f_def.get("multi", False)
            transform = f_def.get("transform")
            literal_value = f_def.get("literal_value")

            # Skip if already found and not multi
            if not multi and control_area in found_areas:
                continue

            # Scope guard
            if scope == "interface" and not current_interface:
                continue
            if scope == "vty" and not current_vty:
                continue
            if scope == "global" and line.indent > 0 and not f_def.get("allow_indented"):
                continue

            # Phase 4b: Juniper `groups` ancestor exclusion.
            # A line whose ancestor chain contains "groups" is inside a groups
            # block — its value must never override the real top-level block.
            # This check applies to all global-scope fields regardless of whether
            # allow_indented is set (JunOS global fields need allow_indented because
            # they are nested in `system {}`, but should never match inside `groups`).
            if scope == "global" and any(
                anc.lower().startswith("groups") for anc in line.ancestors
            ):
                continue

            m = pattern.search(line.text)
            if not m:
                continue

            # Extract value
            if literal_value:
                raw_value = literal_value
            else:
                try:
                    raw_value = m.group("value")
                except IndexError:
                    raw_value = m.group(0)
                if raw_value is None:
                    raw_value = m.group(0)

            value = _apply_transform(raw_value, transform)
            if not value:
                continue

            # Determine instance_id
            instance_id = None
            if scope == "interface":
                instance_id = current_interface
            elif scope == "vty":
                instance_id = current_vty

            results.append(ExtractedField(
                control_area=control_area,
                value=value,
                instance_id=instance_id,
                raw_line=line.raw.strip(),
            ))
            found_areas.add(control_area)

    # Coverage score
    total_fields = len(spec_fields)
    coverage = round(len(found_areas) / total_fields, 3) if total_fields else 0.0

    warnings = []
    if coverage < 0.3:
        warnings.append(
            f"Low parse coverage ({coverage:.0%}): only {len(found_areas)}/{total_fields} "
            f"fields extracted from spec"
        )

    return ParseResult(
        pack_name=pack_name,
        spec_hash=spec_hash,
        fields=results,
        warnings=warnings,
        coverage_score=coverage,
    )


# ──────────────────────────────────────────────────────────────
# 4. Remediation lookup
# ──────────────────────────────────────────────────────────────

def get_remediation_cli(
    pack_name: str,
    control_area: str,
    expected_value: str,
    instance_id: Optional[str] = None,
) -> Optional[str]:
    """
    Look up the remediation.yaml for pack_name and render the CLI command(s)
    for control_area. Returns a formatted multi-line string or None if not found.
    """
    packs = _all_packs()
    if pack_name not in packs:
        return None

    remediation: dict = packs[pack_name].get("remediation", {}).get("remediation", {})
    entry = remediation.get(control_area)
    if not entry:
        return None

    if entry.get("verify") == "skip":
        return f"# {entry.get('skip_reason', 'Manual remediation required')}"

    template_lines: Optional[list[str]] = None

    if "by_expected" in entry:
        by_exp = entry["by_expected"]
        template_lines = by_exp.get(expected_value) or by_exp.get(str(expected_value))
    elif "template" in entry:
        template_lines = entry["template"]

    if not template_lines:
        return None

    rendered = []
    for tpl in template_lines:
        line = tpl
        if "{expected}" in line:
            line = line.replace("{expected}", expected_value)
        if "{instance}" in line:
            inst = instance_id or ("vty 0 4" if "line" in line else "GigabitEthernet0/0")
            line = line.replace("{instance}", inst)
        rendered.append(line)

    return "\n".join(rendered)
