import uuid
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from sqlalchemy import Column, String, Text, UniqueConstraint, Index

def utc_now():
    return datetime.now(timezone.utc)

class ParseRun(SQLModel, table=True):
    __tablename__ = "parse_runs"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    device_id: uuid.UUID = Field(foreign_key="devices.id", ondelete="CASCADE", index=True)
    adapter: Optional[str] = None
    spec_hash: Optional[str] = None
    detector_version: Optional[str] = None
    status: str
    warnings: Optional[str] = None # JSON string
    created_at: datetime = Field(default_factory=utc_now)

class Device(SQLModel, table=True):
    __tablename__ = "devices"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    filename: str
    vendor: Optional[str] = None
    os_hint: Optional[str] = None
    detection_confidence: Optional[float] = None
    hostname: Optional[str] = None
    serial_number: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    raw_config: str = Field(sa_column=Column(Text))
    # Phase 5: SHA-256 of the config content (after stripping volatile lines).
    # Used for upload idempotency — re-uploading the same config returns the
    # existing Device instead of creating a duplicate.
    config_hash: Optional[str] = Field(default=None, index=True)
    current_parse_run_id: Optional[uuid.UUID] = Field(default=None, foreign_key="parse_runs.id")
    uploaded_at: datetime = Field(default_factory=utc_now)

class NormalizedField(SQLModel, table=True):
    __tablename__ = "normalized_fields"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    device_id: uuid.UUID = Field(foreign_key="devices.id", ondelete="CASCADE", index=True)
    parse_run_id: Optional[uuid.UUID] = Field(default=None, foreign_key="parse_runs.id", index=True)
    control_area: str
    instance_id: Optional[str] = None
    value: str
    raw_line: str
    confidence: float
    source_lane: str
    # Phase 7b: superseded is dead — the parse_run_id pointer already
    # distinguishes current vs. stale fields. No query in this codebase
    # filters on it. Remove it in a future migration once Alembic is wired up.
    superseded: bool = Field(default=False)
    updated_at: datetime = Field(default_factory=utc_now)

    __table_args__ = (
        Index("ix_normalized_fields_device_control", "device_id", "control_area"),
    )

class ComplianceRuleDB(SQLModel, table=True):
    __tablename__ = "compliance_rules"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    control_id: str = Field(index=True)
    framework: str = Field(index=True)
    control_area: str
    check_type: str = Field(default="equals")
    expected_value: Optional[str] = None
    expected_list: Optional[str] = None # JSON encoded string
    framework_version: Optional[str] = None
    title: Optional[str] = None
    rationale: Optional[str] = None
    severity: str
    remediation_templates: str = Field(default="{}")

    __table_args__ = (
        UniqueConstraint("control_id", "framework", name="uix_control_framework"),
    )

class FindingDB(SQLModel, table=True):
    __tablename__ = "findings"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    device_id: uuid.UUID = Field(foreign_key="devices.id", ondelete="CASCADE", index=True)
    parse_run_id: Optional[uuid.UUID] = Field(default=None, foreign_key="parse_runs.id", index=True)
    control_id: str
    instance_id: Optional[str] = None
    status: str
    # Phase 3: store which framework produced this finding so reports.py can
    # read it directly without querying the always-empty ComplianceRuleDB.
    framework: Optional[str] = None
    observed_value: Optional[str] = None
    severity: Optional[str] = None
    remediation_cli: Optional[str] = None
    raw_line: Optional[str] = None
    evaluated_at: datetime = Field(default_factory=utc_now)

class Correction(SQLModel, table=True):
    __tablename__ = "corrections"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    vendor: str
    os_hint: Optional[str] = None
    raw_line: str
    mapped_control_area: str
    mapped_value: str
    corrected_by: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)

class ReportArchive(SQLModel, table=True):
    """
    Phase 7c decision: Nothing currently WRITES to this table.
    The old 'check archive first' branch in reports.py has been removed (Phase 3)
    because it served stale PDFs that didn't reflect current findings.

    To properly wire this up:
      - Add a parse_run_id FK column so the archive is keyed to a specific
        parse run and can't go stale.
      - Write an archive row in the /evaluate endpoint after generate_device_pdf.
    Until then, this table stays as a schema placeholder only.
    """
    __tablename__ = "report_archives"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    device_id: uuid.UUID = Field(foreign_key="devices.id", ondelete="CASCADE", index=True)
    framework: str
    pdf_content: bytes
    created_at: datetime = Field(default_factory=utc_now)

    __table_args__ = (
        UniqueConstraint("device_id", "framework", name="uix_device_framework"),
    )
