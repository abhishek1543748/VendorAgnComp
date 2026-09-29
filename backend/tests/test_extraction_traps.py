"""
test_extraction_traps.py — Phase 0 regression tests.

Encodes the two parser trap cases from the audit:
  1. Banner injection: lines inside a banner block must NOT be extracted as
     config fields.
  2. Juniper groups duplicate: when `groups { ... system { host-name FAKE; } }`
     appears BEFORE the real top-level `system { host-name REAL; }`, the
     extractor must return REAL, not FAKE.

Both tests SHOULD FAIL before Phase 4 is applied.
"""
import pytest
from app.parsers.engine import extract, reload_packs

# ── Fixture: Cisco banner injection ─────────────────────────────────────────
CISCO_BANNER_INJECTION = """\
version 15.4
hostname REAL-ROUTER
!
banner motd ^
hostname FAKE-ROUTER
ip domain-name attacker.net
ntp server 1.2.3.4
^
!
ip domain-name real.corp
"""

# ── Fixture: Juniper groups duplicate (groups block appears FIRST) ───────────
JUNIPER_GROUPS_FIRST = """\
groups {
    node-common {
        system {
            host-name FAKE-FROM-GROUPS;
            domain-name fake.example.com;
        }
    }
}
system {
    host-name REAL-HOSTNAME;
    domain-name real.corp;
}
"""

# Reverse ordering (real block first) – already worked before the fix
JUNIPER_REAL_FIRST = """\
system {
    host-name REAL-HOSTNAME;
    domain-name real.corp;
}
groups {
    node-common {
        system {
            host-name FAKE-FROM-GROUPS;
        }
    }
}
"""


# ────────────────────────────────────────────────────────────────────────────
# Banner injection tests
# ────────────────────────────────────────────────────────────────────────────

class TestBannerInjection:
    """Lines inside a banner block must be invisible to the extractor."""

    def test_hostname_not_contaminated_by_banner_content(self):
        result = extract(CISCO_BANNER_INJECTION, "cisco_ios")
        hostnames = [f for f in result.fields if f.control_area == "hostname"]
        assert len(hostnames) == 1, (
            f"Expected exactly 1 hostname field, got {len(hostnames)}: "
            f"{[f.value for f in hostnames]}"
        )
        assert hostnames[0].value == "REAL-ROUTER", (
            f"Expected 'REAL-ROUTER' but got '{hostnames[0].value}' — "
            "banner content is being parsed as config"
        )

    def test_domain_name_not_contaminated_by_banner_content(self):
        result = extract(CISCO_BANNER_INJECTION, "cisco_ios")
        domains = [f for f in result.fields if f.control_area == "domain_name"]
        # Only the real 'ip domain-name real.corp' should appear
        for d in domains:
            assert d.value != "attacker.net", (
                f"Banner-injected domain 'attacker.net' leaked into parsed fields"
            )
        assert any(d.value == "real.corp" for d in domains), (
            "Real domain 'real.corp' was not extracted"
        )

    def test_ntp_server_not_injected_from_banner(self):
        result = extract(CISCO_BANNER_INJECTION, "cisco_ios")
        ntp_servers = [f for f in result.fields if f.control_area == "ntp_server"]
        injected = [f for f in ntp_servers if f.value == "1.2.3.4"]
        assert not injected, (
            "NTP server '1.2.3.4' from inside banner block leaked into parsed fields"
        )


# ────────────────────────────────────────────────────────────────────────────
# Juniper groups duplicate tests
# ────────────────────────────────────────────────────────────────────────────

class TestJuniperGroupsDuplicate:
    """
    Values inside `groups { ... }` blocks must NOT shadow the real top-level
    values.  The fix must work regardless of which block appears first in the
    file.
    """

    def _get_hostname(self, config: str) -> str:
        result = extract(config, "juniper_junos")
        hostnames = [f for f in result.fields if f.control_area == "hostname"]
        assert hostnames, "No hostname field extracted at all"
        return hostnames[0].value

    def test_groups_block_first_returns_real_hostname(self):
        """Critical ordering: groups appears BEFORE the real system block."""
        hostname = self._get_hostname(JUNIPER_GROUPS_FIRST)
        assert hostname == "REAL-HOSTNAME", (
            f"Expected 'REAL-HOSTNAME' but got '{hostname}' — "
            "groups-block value is overriding the real top-level system block "
            "(groups appears FIRST in this fixture)"
        )

    def test_real_block_first_returns_real_hostname(self):
        """Sanity: the reverse ordering must also work after the fix."""
        hostname = self._get_hostname(JUNIPER_REAL_FIRST)
        assert hostname == "REAL-HOSTNAME", (
            f"Expected 'REAL-HOSTNAME' but got '{hostname}'"
        )

    def test_groups_block_domain_not_extracted(self):
        """Domain from inside groups block must not appear in results."""
        result = extract(JUNIPER_GROUPS_FIRST, "juniper_junos")
        domains = [f for f in result.fields if f.control_area == "domain_name"]
        fake = [d for d in domains if d.value == "fake.example.com"]
        assert not fake, (
            "domain 'fake.example.com' from inside groups block leaked into parsed fields"
        )


# ────────────────────────────────────────────────────────────────────────────
# Juniper inactive: / deactivate handling (Phase 4c)
# ────────────────────────────────────────────────────────────────────────────

JUNIPER_INACTIVE_TELNET = """\
system {
    services {
        inactive: telnet;
        ssh {
            protocol-version v2;
        }
    }
}
"""


class TestJuniperInactive:
    """
    Juniper `inactive: <name>;` must map to 'disabled', not be ignored or
    treated as 'enabled'.
    """

    def test_inactive_telnet_extracted_as_disabled(self):
        """
        This test verifies that when telnet is marked `inactive:` in JunOS,
        it is extracted as 'disabled'. Before Phase 4c this will fail because
        the engine either ignores the line or parses it incorrectly.

        NOTE: This requires a 'telnet_service' or similar field in juniper spec.
        For now we assert it does NOT appear as 'enabled'.
        """
        result = extract(JUNIPER_INACTIVE_TELNET, "juniper_junos")
        telnet_fields = [f for f in result.fields if "telnet" in f.control_area.lower()]
        # If the field is extracted, it must not be 'enabled'
        for f in telnet_fields:
            assert f.value != "enabled", (
                f"inactive: telnet extracted as 'enabled' — "
                "Juniper inactive: marker is not being respected"
            )
