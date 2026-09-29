import uuid
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.tables import Device, FindingDB
from app.reporting.generate import generate_device_pdf

router = APIRouter(prefix="/devices", tags=["reports"])

@router.get("/{device_id}/report.pdf", response_class=Response)
def get_device_pdf_report(
    device_id: uuid.UUID,
    session: Session = Depends(get_session)
):
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Dynamic generation with all findings for the current parse run
    if not device.current_parse_run_id:
        findings = []
    else:
        findings = session.exec(
            select(FindingDB)
            .where(FindingDB.device_id == device_id)
            .where(FindingDB.parse_run_id == device.current_parse_run_id)
        ).all()

    # Phase 3 fix: read framework directly from the findings' framework column
    # (stamped by evaluate() at evaluation time). The old approach queried the
    # always-empty ComplianceRuleDB table and silently fell back to "General".
    framework = "General"
    if findings:
        # Use the first non-None framework value found
        for f in findings:
            if getattr(f, "framework", None):
                framework = f.framework
                break

    # Build parse quality warnings
    parse_warnings = []
    if not device.hostname:
        parse_warnings.append("Device hostname was not extracted — config may be unparsed or incomplete.")
    if not findings:
        parse_warnings.append("No compliance findings exist — run Parse then Evaluate before generating a report.")

    pdf_bytes = generate_device_pdf(device, findings, framework=framework, parse_warnings=parse_warnings)

    filename = f"report_{device.hostname or str(device_id)}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename={filename}"
        }
    )
