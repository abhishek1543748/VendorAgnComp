"""
test_upload_idempotency.py — Phase 5 tests.

Verify that uploading the same config file twice returns the same Device
row instead of creating a duplicate.
"""
import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine, select
from sqlmodel.pool import StaticPool

from app.main import app
from app.core.db import get_session
from app.models.tables import Device
from app.parsers.engine import config_hash

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

CISCO_CONFIG = b"""\
version 15.4
hostname TEST-IDEMPOTENCY
!
ip domain name corp.net
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


class TestConfigHashHelper:
    """Unit tests for the config_hash() helper function."""

    def test_same_config_same_hash(self):
        h1 = config_hash("hostname ROUTER\nversion 15.4")
        h2 = config_hash("hostname ROUTER\nversion 15.4")
        assert h1 == h2

    def test_different_config_different_hash(self):
        h1 = config_hash("hostname ROUTER-A")
        h2 = config_hash("hostname ROUTER-B")
        assert h1 != h2

    def test_hash_is_64_char_hex(self):
        h = config_hash("hostname TEST")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_ignore_strips_volatile_lines(self):
        """cisco_ios hash_ignore strips comment lines and byte-count headers."""
        config_a = "! Generated at 2026-01-01\nhostname ROUTER\nversion 15.2"
        config_b = "! Generated at 2026-06-15\nhostname ROUTER\nversion 15.2"
        # Both should hash to the same value because the timestamp comment is ignored
        h_a = config_hash(config_a, pack_name="cisco_ios")
        h_b = config_hash(config_b, pack_name="cisco_ios")
        assert h_a == h_b, (
            f"Volatile comment line caused different hashes:\n  {h_a}\n  {h_b}"
        )


class TestUploadIdempotency:
    """Uploading the same config twice must produce one Device row, not two."""

    def _upload(self, content: bytes, filename: str = "test.cfg") -> dict:
        response = client.post(
            "/devices/upload",
            files={"files": (filename, io.BytesIO(content), "text/plain")},
        )
        assert response.status_code == 200, response.text
        return response.json()

    def test_first_upload_creates_device(self):
        result = self._upload(CISCO_CONFIG)
        assert "uploaded" in result
        assert len(result["uploaded"]) == 1
        assert result["uploaded"][0].get("duplicate") is False

    def test_second_upload_returns_existing_device(self):
        first = self._upload(CISCO_CONFIG, "router-v1.cfg")
        second = self._upload(CISCO_CONFIG, "router-v2.cfg")  # Same content, different filename

        first_id = first["uploaded"][0]["id"]
        second_id = second["uploaded"][0]["id"]

        assert first_id == second_id, (
            f"Re-uploading identical config created a new Device "
            f"(first={first_id}, second={second_id})"
        )
        assert second["uploaded"][0].get("duplicate") is True

    def test_only_one_device_row_after_duplicate_upload(self):
        self._upload(CISCO_CONFIG, "copy1.cfg")
        self._upload(CISCO_CONFIG, "copy2.cfg")

        with Session(test_engine) as session:
            devices = session.exec(select(Device)).all()

        # Count only devices with our test hostname
        test_devices = [d for d in devices if d.raw_config == CISCO_CONFIG.decode()]
        assert len(test_devices) == 1, (
            f"Expected 1 Device row after duplicate upload, got {len(test_devices)}"
        )

    def test_different_config_creates_new_device(self):
        other_config = b"version 15.4\nhostname DIFFERENT-ROUTER\n"
        first = self._upload(CISCO_CONFIG, "original.cfg")
        second = self._upload(other_config, "different.cfg")

        first_id = first["uploaded"][0]["id"]
        second_id = second["uploaded"][0]["id"]

        assert first_id != second_id, "Different configs must create separate Device rows"
        assert second["uploaded"][0].get("duplicate") is False
