# Schema & Rule Engine Upgrade

The upgrade of the models and rule engine to support advanced validation logic and multi-instance controls has been successfully completed and tested.

## Changes Made

### 1. Advanced Schema (`schema.py` & `tables.py`)
- Integrated the new `SecurityBaselineField` and `Finding` schemas with `instance_id` to allow tracking multiple occurrences of a control area on a single device (e.g. multiple `vty` lines or interfaces).
- Expanded `ComplianceRule` and `ComplianceRuleDB` with a `check_type` enum (defaulting to `"equals"`), `expected_list`, and optional metadata fields (`framework_version`, `title`, `rationale`).

### 2. Enhanced Rule Engine (`engine.py`)
- Implemented `evaluate_check()`, which now handles various comparison operators such as:
  - `equals` / `not_equals`
  - `min_value` / `max_value`
  - `min_version` (using robust version string comparison)
  - `regex_match`
  - `in_list` / `not_in_list`
  - `presence_required` / `absence_required`
- The `evaluate` loop was refactored to support mapping a single `control_area` to a list of matching fields instead of just the last-found field. The engine now creates distinct `Finding` results for each instance. 
- Properly handles cases where a field is absent entirely: a rule marked `absence_required` will explicitly PASS if no field is found, while other types fail gracefully to `needs_review`.

### 3. Rule Pack Updates (`packs/*.yaml`)
- `cis_ios.yaml`: Updated the `version` rule to use `check_type: "min_version"` and the `hostname` rule to use `check_type: "presence_required"`.
- `nist_800_53.yaml` & `stig_generic.yaml`: Added explicit `check_type: "equals"` mapping.

### 4. Test Suite Coverage
- Added unit tests for multiple `vty_line` instances to ensure both produce passing/failing findings separately.
- Validated `min_version`, `presence_required`, and `absence_required` rules in the testing environment.

## Validation Results
All 7 unit tests across ingestion, rule evaluation, and PDF report generation passed successfully against the modified schemas.

```
tests\test_ingestion_and_rules.py ....                                   [ 57%]
tests\test_reporting.py ...                                              [100%]
======================== 7 passed, 2 warnings in 5.42s ========================
```
