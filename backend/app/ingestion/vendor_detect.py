"""
vendor_detect.py — thin shim over the YAML engine.

All detection logic now lives in app/parsers/engine.py and the
per-vendor pack fingerprint.yaml files. This module remains the
public API so that devices.py (upload) and other callers don't
need to change their import.
"""
from pydantic import BaseModel
from app.parsers import engine as pack_engine


class VendorDetectionResult(BaseModel):
    vendor: str
    os_hint: str | None
    confidence: float
    syntax_family: str | None = None
    assumed_command: str = "show running-config"
    adapter: str | None = None
    ambiguous: bool = False


def detect_vendor(raw_config: str) -> VendorDetectionResult:
    result = pack_engine.detect(raw_config)

    if result is None:
        return VendorDetectionResult(
            vendor="unknown",
            os_hint=None,
            confidence=0.0,
            syntax_family=None,
            assumed_command="show running-config",
        )

    packs = pack_engine._all_packs()
    fp = packs.get(result.pack_name, {}).get("fingerprint", {})

    return VendorDetectionResult(
        vendor=result.vendor,
        os_hint=result.pack_name,
        confidence=result.confidence,
        syntax_family=fp.get("tokenizer_family"),
        assumed_command=result.assumed_command,
        adapter=result.pack_name,
        ambiguous=result.ambiguous,
    )
