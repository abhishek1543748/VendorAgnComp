import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.core.db import get_session
from app.models.tables import Device, FindingDB
from app.reporting.generate import generate_device_pdf

# Set up in-memory database for testing
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

def override_get_session():
    with Session(engine) as session:
        yield session

client = TestClient(app)

@pytest.fixture(autouse=True)
def prepare_db():
    app.dependency_overrides[get_session] = override_get_session
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)
    app.dependency_overrides.pop(get_session, None)

def test_generate_pdf_bytes():
    dev = Device(
        id=uuid.uuid4(),
        filename="test_cisco.cfg",
        vendor="cisco",
        os_hint="cisco_ios",
        hostname="TEST-ROUTER",
        serial_number="SN123456",
        model="ISR4331",
        firmware_version="15.2",
        raw_config="hostname TEST-ROUTER"
    )
    findings = [
        FindingDB(
            device_id=dev.id,
            control_id="CIS-1.1",
            status="pass",
            severity="high",
            observed_value="15.2",
            raw_line="version 15.2"
        ),
        FindingDB(
            device_id=dev.id,
            control_id="CIS-2.1",
            status="fail",
            severity="critical",
            observed_value="public",
            remediation_cli="no snmp-server community public",
            raw_line="snmp-server community public RO"
        )
    ]

    pdf_bytes = generate_device_pdf(dev, findings)
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 0
    # PDF magic header check
    assert pdf_bytes.startswith(b"%PDF-")

def test_get_device_report_pdf_endpoint():
    with Session(engine) as session:
        dev = Device(
            filename="router.cfg",
            vendor="cisco",
            hostname="CORE-GW",
            serial_number="ABC987",
            model="C9300",
            firmware_version="17.3",
            raw_config="hostname CORE-GW"
        )
        session.add(dev)
        session.commit()
        session.refresh(dev)

        finding = FindingDB(
            device_id=dev.id,
            control_id="CIS-3.1",
            status="fail",
            severity="high",
            observed_value="unencrypted",
            remediation_cli="service password-encryption",
            raw_line="no service password-encryption"
        )
        session.add(finding)
        session.commit()

        dev_id = str(dev.id)

    response = client.get(f"/devices/{dev_id}/report.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "report_CORE-GW.pdf" in response.headers.get("content-disposition", "")
    assert response.content.startswith(b"%PDF-")

def test_get_report_pdf_nonexistent_device():
    random_id = str(uuid.uuid4())
    response = client.get(f"/devices/{random_id}/report.pdf")
    assert response.status_code == 404
    assert response.json()["detail"] == "Device not found"
