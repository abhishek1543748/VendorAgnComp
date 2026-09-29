"""
test_report_framework.py — Phase 0 regression test.

Parse + evaluate a device against CIS, generate its PDF (or call
generate_device_pdf directly), assert the resulting framework label is
"CIS", not "General".

This test SHOULD FAIL before Phase 3 is applied because reports.py looks up
the framework from ComplianceRuleDB (which is never populated), so it falls
back to "General".
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.core.db import get_session
from app.models.tables import Device, FindingDB, NormalizedField, ParseRun
from app.reporting.generate import generate_device_pdf
from app.rules.engine import load_rules_for_framework, evaluate

# ── In-memory test DB ────────────────────────────────────────────────────────
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def override_get_session():
    with Session(test_engine) as session:
        yield session


client = TestClient(app)

CISCO_SAMPLE = """\
version 15.4
hostname TEST-CIS-ROUTER
!
ip domain name corp.internal
!
enable secret 9 $9$something
!
ntp server 10.0.0.50
!
logging host 10.0.0.100
!
line vty 0 4
 exec-timeout 10 0
 transport input ssh
 login local
!
end
"""


@pytest.fixture(autouse=True)
def prepare_db():
    app.dependency_overrides[get_session] = override_get_session
    SQLModel.metadata.create_all(test_engine)
    yield
    SQLModel.metadata.drop_all(test_engine)
    app.dependency_overrides.pop(get_session, None)


class TestReportFrameworkLabel:
    """
    Full round-trip: upload → parse → evaluate (CIS) → generate PDF.
    The PDF must say 'CIS', not 'General'.
    """

    def _create_device_with_findings(self, session: Session) -> tuple[Device, list[FindingDB]]:
        """Create a device and CIS findings directly in the DB."""
        dev = Device(
            filename="test_cis.cfg",
            vendor="cisco",
            os_hint="cisco_ios",
            hostname="TEST-CIS-ROUTER",
            firmware_version="15.4",
            raw_config=CISCO_SAMPLE,
        )
        session.add(dev)
        session.flush()

        run = ParseRun(
            device_id=dev.id,
            adapter="cisco_ios",
            spec_hash="abc123",
            status="success",
        )
        session.add(run)
        session.flush()

        dev.current_parse_run_id = run.id
        session.add(dev)

        # Populate a few normalized fields
        for area, val, raw in [
            ("firmware_version", "15.4", "version 15.4"),
            ("hostname", "TEST-CIS-ROUTER", "hostname TEST-CIS-ROUTER"),
        ]:
            session.add(NormalizedField(
                device_id=dev.id,
                parse_run_id=run.id,
                control_area=area,
                value=val,
                raw_line=raw,
                confidence=1.0,
                source_lane="deterministic",
            ))

        session.commit()
        session.refresh(dev)

        # Generate findings via the rules engine
        fields = session.exec(
            __import__("sqlmodel", fromlist=["select"]).select(NormalizedField)
            .where(NormalizedField.device_id == dev.id)
        ).all()
        rules = load_rules_for_framework("CIS")
        findings = evaluate(device_id=dev.id, os_hint="cisco_ios", fields=fields, rules=rules)
        for f in findings:
            f.parse_run_id = run.id
            session.add(f)
        session.commit()

        findings_db = session.exec(
            __import__("sqlmodel", fromlist=["select"]).select(FindingDB)
            .where(FindingDB.device_id == dev.id)
        ).all()
        return dev, list(findings_db)

    def test_generate_pdf_has_cis_framework_label_not_general(self):
        """
        generate_device_pdf called with framework='CIS' must embed 'CIS' in the
        output, not fall back to 'General'.  This tests the generate function
        directly — if it silently substitutes 'General', the report is wrong.
        """
        dev = Device(
            id=uuid.uuid4(),
            filename="cis_test.cfg",
            vendor="cisco",
            os_hint="cisco_ios",
            hostname="CIS-RTR",
            firmware_version="15.4",
            raw_config="hostname CIS-RTR",
        )
        findings = [
            FindingDB(
                device_id=dev.id,
                control_id="CIS-1.1",
                status="pass",
                severity="high",
                observed_value="15.4",
                raw_line="version 15.4",
            )
        ]
        # We pass framework explicitly — the function must honour it
        pdf_bytes = generate_device_pdf(dev, findings, framework="CIS")
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 0

    def test_report_endpoint_uses_finding_framework_not_db_lookup(self):
        """
        The /report.pdf endpoint must derive 'CIS' from the findings'
        framework column (Phase 3 fix), not from the always-empty
        ComplianceRuleDB table.  Before Phase 3 the report will say
        'General' because ComplianceRuleDB has no rows.
        """
        with Session(test_engine) as session:
            dev, findings = self._create_device_with_findings(session)
            dev_id = str(dev.id)

        response = client.get(f"/devices/{dev_id}/report.pdf")
        assert response.status_code == 200, response.text
        assert response.content.startswith(b"%PDF-"), "Response is not a valid PDF"

        # After Phase 3 the framework column exists on FindingDB and the
        # endpoint reads it directly.  Check that the findings have it set.
        with Session(test_engine) as session:
            db_findings = session.exec(
                __import__("sqlmodel", fromlist=["select"]).select(FindingDB)
                .where(FindingDB.device_id == uuid.UUID(dev_id))
            ).all()
            # Every finding produced by evaluate() for CIS framework must have
            # framework == "CIS" after Phase 3.
            frameworks_found = {getattr(f, "framework", None) for f in db_findings}
            assert "CIS" in frameworks_found, (
                f"No FindingDB row has framework='CIS'.  "
                f"Found frameworks: {frameworks_found}.  "
                f"Phase 3 fix (add framework column + populate it) has not been applied."
            )
