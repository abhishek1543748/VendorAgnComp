from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime


class SourceEvidence(BaseModel):
    raw_line: str
    line_number: int | None = None


class SecurityBaselineField(BaseModel):
    control_area: str
    value: str
    evidence: SourceEvidence
    confidence: float = Field(ge=0.0, le=1.0)
    source_lane: Literal["deterministic", "llm"]
    # NEW: distinguishes multiple instances of the same control_area on one
    # device (e.g. "vty 0 4" vs "vty 5 15", or "GigabitEthernet0/1" vs
    # "GigabitEthernet0/2"). None for controls that only ever have one
    # instance per device (hostname, domain_name, version, ...).
    instance_id: str | None = None


class DeviceIdentity(BaseModel):
    hostname: str | None = None
    serial_number: str | None = None
    model: str | None = None
    firmware_version: str | None = None


class NormalizedDeviceConfig(BaseModel):
    device_id: str
    vendor: str
    os_hint: str | None = None
    identity: DeviceIdentity = DeviceIdentity()
    fields: list[SecurityBaselineField]
    parsed_at: datetime


class ComplianceRule(BaseModel):
    control_id: str
    # Phase 8: ISO_27001 removed — no iso_27001.yaml pack exists.
    # Add it back once a real rule pack is written.
    framework: Literal["CIS", "NIST_800_53", "STIG"]
    control_area: str
    severity: Literal["low", "medium", "high", "critical"]
    # DEPRECATED: superseded by per-vendor remediation.yaml packs.
    # Kept as optional for backwards compatibility; rules engine no longer reads it.
    remediation_templates: dict[str, str] = {}

    # NEW: what kind of comparison this rule performs. Replaces overloading
    # a single expected_value string-equality check for every control shape
    # (version thresholds, numeric limits, presence/absence, list membership
    # all need different comparison logic).
    check_type: Literal[
        "equals", "not_equals",
        "min_version", "min_value", "max_value",
        "regex_match", "in_list", "not_in_list",
        "presence_required", "absence_required",
    ] = "equals"

    # expected_value now optional: presence_required/absence_required don't
    # need one at all, and in_list/not_in_list use expected_list instead.
    expected_value: Optional[str] = None
    expected_list: Optional[list[str]] = None

    # Optional metadata -- doesn't affect evaluation, but makes the PDF
    # report and rule-pack authoring much clearer than a bare control_id.
    framework_version: str | None = None
    title: str | None = None
    rationale: str | None = None


class Finding(BaseModel):
    device_id: str
    control_id: str
    status: Literal["pass", "fail", "needs_review"]
    observed_value: str | None
    severity: str
    remediation_cli: str | None
    evidence: SourceEvidence | None
    # NEW: mirrors SecurityBaselineField.instance_id, so a rule with multiple
    # matching instances produces one Finding per instance instead of one
    # finding for whichever instance happened to be evaluated last.
    instance_id: str | None = None

class CorrectionExample(BaseModel):
    vendor: str
    os_hint: str | None
    raw_line: str
    mapped_control_area: str
    mapped_value: str
    corrected_by: str
    created_at: datetime
