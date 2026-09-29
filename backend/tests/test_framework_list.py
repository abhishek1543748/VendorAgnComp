"""
test_framework_list.py — Phase 8 tests.

Every framework returned by GET /frameworks must have at least one rule
loadable by load_rules_for_framework(). No framework should be advertised
that always errors on evaluate.
"""
import pytest
from app.rules.engine import load_rules_for_framework


class TestFrameworkListIntegrity:
    """Frameworks endpoint must only advertise implemented rule packs."""

    def test_cis_has_rules(self):
        rules = load_rules_for_framework("CIS")
        assert rules, "CIS framework has no rules — is cis_ios.yaml missing or empty?"

    def test_nist_800_53_has_rules(self):
        rules = load_rules_for_framework("NIST_800_53")
        assert rules, "NIST_800_53 framework has no rules — is nist_800_53.yaml missing or empty?"

    def test_stig_has_rules(self):
        rules = load_rules_for_framework("STIG")
        assert rules, "STIG framework has no rules — is stig_generic.yaml missing or empty?"

    def test_iso_27001_has_no_rules_and_must_not_be_advertised(self):
        """
        ISO_27001 is not implemented yet — no yaml pack exists.
        This test confirms the framework list endpoint won't serve it.
        When a real iso_27001.yaml is written, this test should be deleted
        and ISO_27001 added to the implemented list.
        """
        rules = load_rules_for_framework("ISO_27001")
        # Either no rules at all, or we want an empty list
        # (the YAML files only have CIS/NIST/STIG frameworks defined)
        assert not rules, (
            f"ISO_27001 unexpectedly has rules: {[r.control_id for r in rules]}. "
            "If a real iso_27001.yaml was added, update the frameworks list too."
        )

    def test_all_implemented_frameworks_have_rules(self):
        """
        The canonical implemented list must be non-empty for all entries.
        This catches adding a framework name without writing its rules file.
        """
        # Import the same list from the frameworks API to avoid drift
        import app.api.frameworks as fw_module
        implemented = fw_module._IMPLEMENTED_FRAMEWORKS
        for framework in implemented:
            rules = load_rules_for_framework(framework)
            assert rules, (
                f"Framework '{framework}' is in _IMPLEMENTED_FRAMEWORKS but "
                f"load_rules_for_framework('{framework}') returned no rules. "
                f"Either write the rules pack or remove it from the list."
            )
