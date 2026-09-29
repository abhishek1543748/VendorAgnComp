import os
import glob
import yaml
import uuid
import re
from packaging.version import parse as parse_version
from collections import defaultdict
from app.models.schema import ComplianceRule
from app.models.tables import NormalizedField, FindingDB
import app.parsers.engine as pack_engine

CONFIDENCE_THRESHOLD = 0.75

PACKS_DIR = os.path.join(os.path.dirname(__file__), "packs")

def load_rules_for_framework(framework: str) -> list[ComplianceRule]:
    rules = []
    yaml_files = glob.glob(os.path.join(PACKS_DIR, "*.yaml"))
    
    for file_path in yaml_files:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, list):
                for item in data:
                    if item.get("framework") == framework:
                        rules.append(ComplianceRule(**item))
    return rules

def evaluate_check(check_type: str, expected_value: str | None, expected_list: list[str] | None, observed: str) -> bool:
    try:
        if check_type == "equals":
            return (expected_value == "*") or (expected_value.lower() == observed.lower())
        elif check_type == "not_equals":
            return expected_value.lower() != observed.lower()
        elif check_type == "min_value":
            return float(observed) >= float(expected_value)
        elif check_type == "max_value":
            return float(observed) <= float(expected_value)
        elif check_type == "min_version":
            return parse_version(observed) >= parse_version(expected_value)
        elif check_type == "regex_match":
            return bool(re.search(expected_value, observed))
        elif check_type == "in_list":
            return observed in (expected_list or [])
        elif check_type == "not_in_list":
            return observed not in (expected_list or [])
        elif check_type == "presence_required":
            return True # If we are here, the field is present
        elif check_type == "absence_required":
            return False # If we are here, the field is present (which is bad)
    except Exception:
        return False # Type coercion failure or invalid regex means fail
    return False

def evaluate(device_id: uuid.UUID, os_hint: str | None, fields: list[NormalizedField], rules: list[ComplianceRule]) -> list[FindingDB]:
    findings = []
    
    # Map control_area -> list of fields (to support multiple instances)
    field_map = defaultdict(list)
    for f in fields:
        field_map[f.control_area.lower()].append(f)
    
    for rule in rules:
        target_area = rule.control_area.lower()
        matched_fields = field_map.get(target_area, [])
        
        def _get_remediation(matched_field=None) -> str | None:
            """Look up CLI remediation from the vendor's remediation.yaml pack."""
            if not os_hint:
                return None
            instance_id = matched_field.instance_id if matched_field else None
            expected = rule.expected_value or (
                rule.expected_list[0] if rule.expected_list else None
            )
            return pack_engine.get_remediation_cli(
                pack_name=os_hint,
                control_area=rule.control_area,
                expected_value=expected or "",
                instance_id=instance_id,
            )

        # Derive framework string for storing on FindingDB
        framework_str = rule.framework if hasattr(rule, "framework") else None

        def _make_finding(status: str, observed: str | None, remediation: str | None,
                          raw_line: str | None, instance_id: str | None) -> FindingDB:
            f = FindingDB(
                device_id=device_id,
                control_id=rule.control_id,
                status=status,
                observed_value=observed,
                severity=rule.severity,
                remediation_cli=remediation,
                raw_line=raw_line,
                instance_id=instance_id,
            )
            # Store the framework string on the finding so reports.py doesn't
            # need to reverse-derive it from ComplianceRuleDB (which is never
            # populated).  This is the Phase 3 fix.
            if framework_str and hasattr(f, "framework"):
                f.framework = framework_str
            return f

        # If no fields match this rule
        if not matched_fields:
            if rule.check_type == "absence_required":
                # It's good that it's missing!
                findings.append(_make_finding("pass", None, None, None, None))
            else:
                # Needs review because parser might have missed it, or it's
                # actually missing — get remediation regardless
                findings.append(_make_finding(
                    "needs_review", None, _get_remediation(), None, None
                ))
            continue
            
        for matched_field in matched_fields:
            if matched_field.confidence < CONFIDENCE_THRESHOLD:
                findings.append(_make_finding(
                    "needs_review",
                    matched_field.value,
                    _get_remediation(matched_field),
                    matched_field.raw_line,
                    matched_field.instance_id,
                ))
            else:
                observed = matched_field.value
                is_pass = evaluate_check(
                    rule.check_type, 
                    rule.expected_value, 
                    rule.expected_list, 
                    observed
                )
                findings.append(_make_finding(
                    "pass" if is_pass else "fail",
                    observed,
                    None if is_pass else _get_remediation(matched_field),
                    matched_field.raw_line,
                    matched_field.instance_id,
                ))
                
    return findings
