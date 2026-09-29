"""
test_field_contract.py — Phase 0 regression test.

Asserts that every control_area referenced by any rules/packs/*.yaml
exists in the set produced by at least one parsers/packs/*/spec.yaml.

This test SHOULD FAIL before Phase 1 is applied; it proves the field-name
mismatch that is the root cause of most evaluation failures.
"""
import glob
import os
import yaml
import pytest

RULES_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "rules", "packs")
PARSERS_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "parsers", "packs")


def _load_rule_control_areas() -> set[str]:
    """Collect every control_area referenced in any rules pack YAML."""
    areas: set[str] = set()
    for path in glob.glob(os.path.join(RULES_DIR, "*.yaml")):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or []
        if not isinstance(data, list):
            continue
        for rule in data:
            if isinstance(rule, dict) and "control_area" in rule:
                areas.add(rule["control_area"])
    return areas


def _load_spec_control_areas() -> set[str]:
    """Collect every control_area defined in any parser spec.yaml."""
    areas: set[str] = set()
    for path in glob.glob(os.path.join(PARSERS_DIR, "**", "spec.yaml"), recursive=True):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for field_def in data.get("fields", []):
            if isinstance(field_def, dict) and "control_area" in field_def:
                areas.add(field_def["control_area"])
    return areas


def test_all_rule_control_areas_exist_in_specs():
    """
    Every control_area used in a compliance rule must be producible by at
    least one parser spec.  A mismatch means evaluation will always return
    'needs_review' (field never found) even when the device has that config.

    Before Phase 1 this will fail, listing the mismatched areas.
    """
    rule_areas = _load_rule_control_areas()
    spec_areas = _load_spec_control_areas()

    missing = rule_areas - spec_areas

    # Report which specific areas are absent (makes the failure actionable)
    assert not missing, (
        f"The following control_areas are referenced in rules but never produced by any "
        f"parser spec.yaml:\n  {sorted(missing)}\n\n"
        f"Rule areas:  {sorted(rule_areas)}\n"
        f"Spec areas:  {sorted(spec_areas)}"
    )



