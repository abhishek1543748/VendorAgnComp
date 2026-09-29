import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.tables import Device, NormalizedField, FindingDB
from app.rules.engine import load_rules_for_framework, evaluate

router = APIRouter(prefix="/devices", tags=["findings"])

@router.post("/{device_id}/evaluate")
def evaluate_device(
    device_id: uuid.UUID,
    framework: str = Query(..., description="Framework to evaluate (CIS, NIST_800_53, STIG, ISO_27001)"),
    session: Session = Depends(get_session)
):
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    if not device.current_parse_run_id:
        return {"error": "Device has not been parsed yet."}

    fields = session.exec(
        select(NormalizedField)
        .where(NormalizedField.device_id == device_id)
        .where(NormalizedField.parse_run_id == device.current_parse_run_id)
    ).all()
    
    rules = load_rules_for_framework(framework)
    if not rules:
        raise HTTPException(status_code=400, detail=f"No rules found for framework {framework}")
        
    findings = evaluate(device_id=device_id, os_hint=device.os_hint, fields=fields, rules=rules)
    
    # Clear old findings for THIS parse run + framework's control_ids before saving
    rule_control_ids = [r.control_id for r in rules]
    old_findings = session.exec(
        select(FindingDB)
        .where(FindingDB.device_id == device_id)
        .where(FindingDB.parse_run_id == device.current_parse_run_id)
        .where(FindingDB.control_id.in_(rule_control_ids))
    ).all()
    for old in old_findings:
        session.delete(old)
    
    # Save new findings to DB
    for finding in findings:
        finding.parse_run_id = device.current_parse_run_id
        session.add(finding)
    session.commit()
    
    return {
        "device_id": str(device_id),
        "framework": framework,
        "evaluated_rules_count": len(rules),
        "findings_count": len(findings),
        "findings": [
            {
                "id": str(f.id),
                "device_id": str(f.device_id),
                "control_id": f.control_id,
                "status": f.status,
                "severity": f.severity,
                "framework": f.framework,
                "observed_value": f.observed_value,
                "remediation_cli": f.remediation_cli,
                "raw_line": f.raw_line,
                "instance_id": f.instance_id,
            }
            for f in findings
        ]
    }

@router.get("/{device_id}/findings")
def get_device_findings(device_id: uuid.UUID, session: Session = Depends(get_session)):
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    if not device.current_parse_run_id:
        return []

    findings = session.exec(
        select(FindingDB)
        .where(FindingDB.device_id == device_id)
        .where(FindingDB.parse_run_id == device.current_parse_run_id)
    ).all()
    
    return findings
