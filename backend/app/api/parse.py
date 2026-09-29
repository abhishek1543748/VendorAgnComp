import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.db import get_session
from app.models.tables import Device, NormalizedField, ParseRun
from app.parsers import engine as pack_engine

log = logging.getLogger(__name__)
router = APIRouter(prefix="/devices", tags=["parse"])


def _fallback(device: Device, message: str) -> dict:
    return {"device_id": str(device.id), "status": "needs_llm_fallback", "message": message}


@router.post("/{device_id}/parse")
def parse_device(device_id: uuid.UUID, session: Session = Depends(get_session)):
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # ── 1. Detect vendor via YAML fingerprint packs ──────────────
    detection = pack_engine.detect(device.raw_config)

    if not detection:
        return _fallback(device, "No fingerprint pack matched this config (below MIN_SCORE)")

    log.info(
        "Device %s detected as pack=%s confidence=%.2f ambiguous=%s",
        device.id, detection.pack_name, detection.confidence, detection.ambiguous,
    )

    # ── 2. Extract fields via spec.yaml ──────────────────────────
    parse_result = pack_engine.extract(device.raw_config, detection.pack_name)

    if not parse_result.fields:
        log.warning("Pack %s extracted zero fields for device %s", detection.pack_name, device.id)

    # ── 3. Persist: ParseRun + NormalizedFields (one transaction) ─
    try:
        run = ParseRun(
            device_id=device.id,
            adapter=detection.pack_name,
            spec_hash=detection.spec_hash,
            status="success" if parse_result.fields else "empty",
            warnings=json.dumps(parse_result.warnings) if parse_result.warnings else None,
        )
        session.add(run)
        session.flush()  # Materialise run.id before using it

        device.current_parse_run_id = run.id
        device.vendor = detection.vendor
        device.os_hint = detection.pack_name   # pack_name is the canonical os_hint
        device.detection_confidence = detection.confidence

        for ef in parse_result.fields:
            # Mirror identity fields onto the Device row
            if ef.instance_id is None:
                if ef.control_area == "hostname":
                    device.hostname = ef.value
                elif ef.control_area == "firmware_version":
                    device.firmware_version = ef.value
                elif ef.control_area == "serial_number":
                    device.serial_number = ef.value
                elif ef.control_area == "model":
                    device.model = ef.value

            session.add(NormalizedField(
                device_id=device.id,
                parse_run_id=run.id,
                control_area=ef.control_area,
                instance_id=ef.instance_id,
                value=ef.value,
                raw_line=ef.raw_line,
                confidence=ef.confidence,
                source_lane=ef.source_lane,
                superseded=False,
            ))

        session.add(device)
        session.commit()

    except Exception:
        session.rollback()
        log.exception("Failed to persist parse results for device %s", device.id)
        raise HTTPException(status_code=500, detail="Failed to persist parsed fields")

    return {
        "device_id": str(device.id),
        "status": "parsed",
        "pack": detection.pack_name,
        "vendor": detection.vendor,
        "confidence": detection.confidence,
        "ambiguous": detection.ambiguous,
        "spec_hash": detection.spec_hash,
        "fields_count": len(parse_result.fields),
        "coverage_score": parse_result.coverage_score,
        "warnings": parse_result.warnings,
    }
