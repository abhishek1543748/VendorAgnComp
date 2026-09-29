# Implementation Plan & Checklist — Phase 1 & Phase 2

This document outlines the step-by-step roadmap and checklist for implementing **Phase 1** and **Phase 2** of the Vendor-Agnostic Compliance Engine as specified in [`agent-build-spec.md`](file:///c:/Users/BIT/Desktop/VendorAgnComp/agent-build-spec.md).

> [!IMPORTANT]
> **Strict Phase Order Constraint (§0 Rule 1):**
> Phase 1 (*Unified Ingestion Engine & Deterministic Normalization*) **must** be fully implemented, tested, and passing exit criteria before starting Phase 2 (*Multi-Framework Compliance Engine*).

---

## 1. Phase 1 Checklist — Unified Ingestion Engine + Deterministic Normalization
*Version tag: `v0.2` · Prerequisite Phase*

### Proposed Changes

#### Backend Ingestion & Parsers
- [ ] **[NEW]** [`app/ingestion/vendor_detect.py`](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/ingestion/vendor_detect.py): Multi-keyword scored fingerprinting.
  > [!WARNING]
  > Must use `re.MULTILINE` on all fingerprint regexes using `^` as anchor so multiline config lines match correctly.
- [ ] **[NEW]** [`app/parsers/deterministic.py`](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/parsers/deterministic.py): `parse_deterministic(platform, command, raw_text)` wrapping `ntc_templates.parse.parse_output`.
  > [!NOTE]
  > Must raise custom `NoDeterministicTemplate` exception if `parse_output` fails or returns empty list.

#### Backend API Endpoints
- [ ] **[NEW]** [`app/api/devices.py`](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/api/devices.py):
  - `POST /devices/upload`: Handles single or bulk file uploads, runs vendor detection, saves raw config to DB.
  - `GET /devices`: Lists all uploaded devices.
  - `GET /devices/{id}`: Retrieves single device details.
  - `GET /devices/{id}/fields`: Returns stored `normalized_fields`.
- [ ] **[NEW]** [`app/api/parse.py`](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/api/parse.py):
  - `POST /devices/{id}/parse`: Runs deterministic parser. If template is missing/empty, flags device with `needs_llm_fallback`.
- [ ] **[MODIFY]** [`app/main.py`](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/main.py): Include API routers from `devices` and `parse`.

#### Frontend
- [ ] **[NEW]** [`frontend/src/pages/Upload.tsx`](file:///c:/Users/BIT/Desktop/VendorAgnComp/frontend/src/pages/Upload.tsx): Single and multi-select file uploader with detected vendor and confidence display.

#### Testing & Fixtures
- [ ] Add Cisco IOS (`show run`) and Juniper Junos (`show configuration`) test fixtures to `backend/tests/fixtures/`.
- [ ] Add pytest suite covering vendor detection accuracy and deterministic parsing (`confidence == 1.0`, `source_lane == "deterministic"`).

---

## 2. Phase 2 Checklist — Multi-Framework Compliance Engine
*Version tag: `v0.3` · Target Phase*

### Proposed Changes

#### Rule Packs & Evaluator Engine
- [ ] **[NEW]** [`app/rules/packs/cis_ios.yaml`](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/rules/packs/cis_ios.yaml): CIS Benchmark rules (e.g., SSH v2 enforced, Telnet disabled).
- [ ] **[NEW]** [`app/rules/packs/nist_800_53.yaml`](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/rules/packs/nist_800_53.yaml): NIST 800-53 password & session policy rules.
- [ ] **[NEW]** [`app/rules/packs/stig_generic.yaml`](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/rules/packs/stig_generic.yaml): STIG logging & audit requirement rules.
- [ ] **[NEW]** [`app/rules/engine.py`](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/rules/engine.py):
  - `evaluate(fields: list[SecurityBaselineField], rules: list[ComplianceRule]) -> list[Finding]`.
  - Enforce `CONFIDENCE_THRESHOLD = 0.75`.
  > [!IMPORTANT]
  > Rules missing a matching field or having confidence below `CONFIDENCE_THRESHOLD` must produce `status = "needs_review"`. Never skip a rule silently.

#### Backend API Endpoints
- [ ] **[NEW]** [`app/api/frameworks.py`](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/api/frameworks.py):
  - `GET /frameworks`: Returns fixed list `["CIS", "NIST_800_53", "STIG", "ISO_27001"]`.
- [ ] **[NEW]** [`app/api/findings.py`](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/api/findings.py):
  - `POST /devices/{id}/evaluate?framework=CIS`: Evaluates normalized fields against rule pack and persists findings into the `findings` table.
  - `GET /devices/{id}/findings`: Retrieves evaluated findings for a device.
- [ ] **[MODIFY]** [`app/main.py`](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/main.py): Register `frameworks` and `findings` routers.

---

## Verification Plan

### Automated Tests (pytest)
1. **Phase 1 Verification**:
   - `pytest backend/tests/test_ingestion.py`: Test `vendor_detect.py` against Cisco, Juniper, Palo Alto, and Fortinet fixtures.
   - `pytest backend/tests/test_parsers.py`: Test `parse_deterministic()` returning structured output with `confidence = 1.0`.
2. **Phase 2 Verification**:
   - `pytest backend/tests/test_rules_engine.py`: Test rule evaluation producing expected `pass`, `fail`, and `needs_review` statuses.

### Manual Verification
1. Upload Cisco IOS config via `POST /devices/upload` -> Verify `device_id` returned.
2. Trigger parse via `POST /devices/{id}/parse` -> Verify `normalized_fields` stored with `source_lane = "deterministic"`.
3. Run evaluation via `POST /devices/{id}/evaluate?framework=CIS` -> Verify `findings` table populated.
4. Fetch findings via `GET /devices/{id}/findings` -> Check expected pass/fail status per rule.
