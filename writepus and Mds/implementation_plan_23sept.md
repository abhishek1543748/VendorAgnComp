# Implement Enhanced Schema and Rule Engine

This plan covers the implementation of the advanced `schema.py` changes you proposed, which introduces `instance_id` tracking for multi-instance fields (like interfaces) and a robust `check_type` system to replace naive string matching.

## User Review Required

> [!WARNING]  
> This requires a change to the core database tables (`tables.py`) to add the `instance_id` and rule metadata fields. Since there are no Alembic migrations present in the repository, I will simply update the SQLModel definitions. Any existing local database will need to be recreated (e.g., `SQLModel.metadata.drop_all()` / `create_all()`) or deleted so it can be automatically recreated.

> [!IMPORTANT]
> The `ComplianceRuleDB` model in `tables.py` currently defines rules as database entries, even though `engine.py` currently loads rules from the YAML packs. I will update both the YAML files and the `ComplianceRuleDB` definition to ensure parity.

## Open Questions

> [!NOTE]
> For version comparisons (`min_version`), do you want to use a specific library like `packaging.version`, or a custom string parsing method? For this plan, I'll assume we use Python's built-in `packaging.version` (which is standard for version string comparisons).

## Proposed Changes

---

### `app/models`

Updates to the core Pydantic schemas and SQLModel tables.

#### [MODIFY] [schema.py](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/models/schema.py)
- Replace lines 1-42 with the new schema you provided.
- Includes `instance_id` in `SecurityBaselineField` and `Finding`.
- Updates `ComplianceRule` with `check_type`, `expected_list`, `framework_version`, `title`, and `rationale`.

#### [MODIFY] [tables.py](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/models/tables.py)
- `NormalizedField`: Add `instance_id: Optional[str] = None`.
- `ComplianceRuleDB`: Add `check_type: str`, `expected_list: Optional[str]` (stored as JSON string), `framework_version: Optional[str]`, `title: Optional[str]`, `rationale: Optional[str]`. Change `expected_value` to `Optional[str]`.
- `FindingDB`: Add `instance_id: Optional[str] = None`.

---

### `app/rules`

Updates to the engine to evaluate the new properties, and updating the sample packs.

#### [MODIFY] [engine.py](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/rules/engine.py)
- Update the `evaluate()` function to handle multiple `instance_id`s per `control_area`. 
  - Instead of `field_map` being `dict[control_area, field]`, it will be `dict[control_area, list[field]]`.
- If a rule targets an area with multiple instances, it will iterate over all instances and generate a `FindingDB` for each.
- If a rule specifies `presence_required` or `absence_required`, handle the logic properly even if the `fields` list is empty for that `control_area`.
- Implement `check_type` logic:
  - `equals` / `not_equals`
  - `min_value` / `max_value` (numeric coercion)
  - `min_version` (version comparison)
  - `regex_match` (using `re.match`)
  - `in_list` / `not_in_list` (using `expected_list`)

#### [MODIFY] [cis_ios.yaml](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/rules/packs/cis_ios.yaml)
- Update existing rules to conform to the new structure.
- Replace `expected_value: "*"` in `CIS-2.1` with `check_type: "presence_required"`.
- Set `check_type: "equals"` explicitly or omit it for others.

#### [MODIFY] [nist_800_53.yaml](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/rules/packs/nist_800_53.yaml)
- Update existing rules.

#### [MODIFY] [stig_generic.yaml](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/rules/packs/stig_generic.yaml)
- Update existing rules.

---

### `tests`

Updates to ensure tests pass with the new required database fields.

#### [MODIFY] [test_ingestion_and_rules.py](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/tests/test_ingestion_and_rules.py)
- Update manually constructed `ComplianceRule` and `NormalizedField` objects to include `check_type` and (optional) `instance_id`.
- Add a new test to verify `instance_id` generates multiple findings (e.g. testing `vty` or interfaces).
- Add tests for new `check_type` behaviors (e.g., `presence_required`).

#### [MODIFY] [test_reporting.py](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/tests/test_reporting.py)
- Update `FindingDB` mock data construction to include the new fields if needed.

## Verification Plan

### Automated Tests
- Run `pytest backend/tests/test_ingestion_and_rules.py` to ensure the rule engine handles multi-instance areas and correctly applies the new `check_type` logic.
- Run `pytest backend/tests/test_reporting.py` to ensure PDFs can still be generated with the modified `FindingDB`.

### Manual Verification
- None required for this structural change, as everything is covered by automated unit tests.
