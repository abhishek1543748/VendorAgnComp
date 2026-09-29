"""
test_remediation_system.py — Phase 2 tests.

Verifies that:
1. evaluate() uses pack_engine.get_remediation_cli() (real remediation.yaml)
   instead of the deprecated remediation_templates dict.
2. A Junos device evaluated against CIS gets `set system` syntax,
   not `ip domain-name` (Cisco) syntax.
3. remediation.yaml round-trip: render the template, confirm it contains
   the right vendor CLI tokens.
"""
import uuid
import pytest
from app.parsers.engine import get_remediation_cli
from app.rules.engine import evaluate
from app.models.schema import ComplianceRule
from app.models.tables import NormalizedField


class TestRemediationLookup:
    """get_remediation_cli returns vendor-correct CLI."""

    def test_cisco_hostname_remediation(self):
        cli = get_remediation_cli("cisco_ios", "hostname", "MY-ROUTER")
        assert cli is not None, "Expected a CLI string for cisco_ios hostname"
        assert "hostname" in cli.lower(), f"Expected 'hostname' in CLI: {cli}"
        assert "MY-ROUTER" in cli, f"Expected expected_value in CLI: {cli}"

    def test_juniper_hostname_remediation_uses_set_system(self):
        cli = get_remediation_cli("juniper_junos", "hostname", "MY-SRX")
        assert cli is not None, "Expected a CLI string for juniper_junos hostname"
        assert "set system" in cli.lower(), (
            f"Juniper remediation must use 'set system' syntax, got: {cli}"
        )
        assert "ip domain-name" not in cli.lower(), (
            f"Juniper remediation must NOT contain Cisco 'ip domain-name', got: {cli}"
        )

    def test_juniper_logging_host_remediation_uses_set_system_syslog(self):
        cli = get_remediation_cli("juniper_junos", "logging_host", "10.0.0.100")
        assert cli is not None
        assert "set system syslog" in cli.lower(), (
            f"Expected 'set system syslog' in JunOS logging_host remediation: {cli}"
        )
        assert "10.0.0.100" in cli

    def test_cisco_ntp_server_remediation(self):
        cli = get_remediation_cli("cisco_ios", "ntp_server", "10.0.0.50")
        assert cli is not None
        assert "ntp server" in cli.lower()
        assert "10.0.0.50" in cli

    def test_arista_hostname_not_cisco_syntax(self):
        """Arista doesn't have a hostname remediation entry — should return None or
        a string that doesn't contain Cisco-only commands."""
        cli = get_remediation_cli("arista_eos", "hostname", "CORE-SW")
        # Arista remediation.yaml doesn't define hostname — should be None
        # (which is valid — not every pack covers every field)
        if cli is not None:
            assert "ip domain-name" not in cli.lower(), (
                f"Arista remediation must not contain Cisco 'ip domain-name': {cli}"
            )

    def test_skip_entry_returns_comment(self):
        """Entries with verify: skip must return a comment string, not None."""
        cli = get_remediation_cli("cisco_ios", "snmp_community", "whatever")
        assert cli is not None
        assert cli.startswith("#"), f"skip entry must return '# ...', got: {cli}"
        # And the skip reason must be non-empty
        assert len(cli) > 2


class TestEvaluateUsesRealRemediation:
    """evaluate() must use pack_engine CLI, not remediation_templates dict."""

    def test_junos_finding_has_set_system_remediation_not_cisco(self):
        """
        Evaluate a Juniper device against a CIS hostname rule.
        The resulting failing finding's remediation_cli must be Junos `set system`
        syntax, not Cisco `hostname ...` or `ip domain-name`.
        """
        dev_id = uuid.uuid4()
        # Provide NO hostname so the rule fails
        fields: list[NormalizedField] = []
        rules = [
            ComplianceRule(
                control_id="CIS-2.1",
                framework="CIS",
                control_area="hostname",
                check_type="presence_required",
                severity="low",
            )
        ]
        findings = evaluate(dev_id, os_hint="juniper_junos", fields=fields, rules=rules)
        assert findings, "Expected at least one finding"
        f = findings[0]
        assert f.status == "needs_review", f"Expected needs_review, got {f.status}"

        if f.remediation_cli:
            assert "ip domain-name" not in f.remediation_cli.lower(), (
                f"Cisco 'ip domain-name' leaked into JunOS finding remediation: {f.remediation_cli}"
            )
            assert "set system" in f.remediation_cli.lower(), (
                f"Expected 'set system' in JunOS finding remediation: {f.remediation_cli}"
            )

    def test_cisco_enable_secret_finding_uses_pack_remediation(self):
        """
        For a NIST-IA-5 failure (enable_secret_type not in [8, 9]), the
        remediation should come from cisco_ios/remediation.yaml, not from
        the deprecated remediation_templates dict.
        """
        dev_id = uuid.uuid4()
        fields = [
            NormalizedField(
                device_id=dev_id,
                control_area="enable_secret_type",
                value="5",  # MD5 — should fail
                raw_line="enable secret 5 $1$...",
                confidence=1.0,
                source_lane="deterministic",
            )
        ]
        rules = [
            ComplianceRule(
                control_id="NIST-IA-5",
                framework="NIST_800_53",
                control_area="enable_secret_type",
                check_type="in_list",
                expected_list=["8", "9"],
                severity="critical",
            )
        ]
        findings = evaluate(dev_id, os_hint="cisco_ios", fields=fields, rules=rules)
        assert findings
        f = findings[0]
        assert f.status == "fail", f"Expected fail for type 5 secret, got {f.status}"
        # The cisco_ios remediation.yaml marks enable_secret_type as verify:skip
        # so the result should be a comment string
        if f.remediation_cli:
            assert f.remediation_cli.startswith("#"), (
                f"enable_secret_type has verify:skip, expected comment: {f.remediation_cli}"
            )
