# Phase 3 Implementation Plan — PDF Reporting Mechanics

Establish the mechanics for PDF report generation using **Jinja2** template rendering and **WeasyPrint** PDF compilation, along with the API endpoint `GET /devices/{id}/report.pdf`.

## Proposed Changes

### Dependencies

#### [MODIFY] [requirements.txt](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/requirements.txt)
- Add `weasyprint` and `jinja2` dependencies.

---

### Backend Core & Reporting Engine

#### [NEW] [backend/app/reporting/__init__.py](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/reporting/__init__.py)
- Package initialization for reporting module.

#### [NEW] [backend/app/reporting/templates/report.html](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/reporting/templates/report.html)
- Jinja2 HTML template formatted with standard styling and structure containing the three required sections:
  1. **Device Identification**: Hostname, serial number, model, firmware version.
  2. **Compliance Findings**: Table of findings with rule ID, status (Pass/Fail), severity, and description.
  3. **Remediation Paths**: Remediation CLI commands formatted as copyable code blocks for failed findings.

#### [NEW] [backend/app/reporting/generate.py](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/reporting/generate.py)
- Implement `generate_device_pdf(device, findings)`:
  - Load and render `report.html` using Jinja2 with `autoescape=True`.
  - Pass the rendered HTML string to `weasyprint.HTML(string=...).write_pdf()`.
  - Return the raw bytes of the generated PDF.

---

### API Layer

#### [NEW] [backend/app/api/reports.py](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/api/reports.py)
- Implement `GET /devices/{id}/report.pdf`:
  - Fetch device and associated evaluation findings from the database.
  - Call `generate_device_pdf(device, findings)`.
  - Return `Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f"inline; filename=report_{device_id}.pdf"})`.

#### [MODIFY] [backend/app/main.py](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/app/main.py)
- Include `reports.router` into the FastAPI application.

---

### Testing

#### [NEW] [backend/tests/test_reporting.py](file:///c:/Users/BIT/Desktop/VendorAgnComp/backend/tests/test_reporting.py)
- Unit and integration tests for PDF generation:
  - Test Jinja2 template rendering logic with mock/fixture data.
  - Test `GET /devices/{id}/report.pdf` returns 200 OK and valid PDF bytes (starting with `%PDF-`).

---

## Verification Plan

### Automated Tests
- Run `pytest` in `backend/` to verify all test suites including PDF report generation test cases:
  ```powershell
  python -m pytest
  ```

### Manual Verification
- Execute `GET /devices/{id}/report.pdf` against a fixture device with evaluated findings and inspect the returned PDF binary headers and content structure.
