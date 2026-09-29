import uuid
import pytest
from app.ingestion.vendor_detect import detect_vendor
from app.models.schema import ComplianceRule, SourceEvidence
from app.models.tables import NormalizedField
from app.rules.engine import evaluate, CONFIDENCE_THRESHOLD

CISCO_SAMPLE = """
Building configuration...

Current configuration : 1104 bytes
!
version 15.2
service timestamps debug datetime msec
hostname ROUTER-01
!
interface GigabitEthernet0/0
 ip address 192.168.1.1 255.255.255.0
!
line vty 0 4
 login
!
end
"""

JUNIPER_SAMPLE = """
system {
    host-name JUNIPER-SRX;
    domain-name internal.net;
}
interfaces {
    ge-0/0/0 {
        unit 0 {
            family inet {
                address 10.0.0.1/24;
            }
        }
    }
}
"""

def test_vendor_detection_cisco():
    res = detect_vendor(CISCO_SAMPLE)
    assert res.vendor == "cisco"
    assert res.os_hint == "cisco_ios"
    assert res.confidence >= 0.5
    assert res.syntax_family == "indent_delimited"

def test_vendor_detection_juniper():
    res = detect_vendor(JUNIPER_SAMPLE)
    assert res.vendor == "juniper"
    assert res.os_hint == "juniper_junos"
    assert res.confidence >= 0.5

def test_rule_engine_evaluation_pass_fail():
    """
    Updated for Phase 1: field names now use the canonical registry names.
    - CIS-1.1: control_area='firmware_version' (was 'version')
    - CIS-3.1: control_area='domain_name', check_type='presence_required' (placeholder removed)
    - CIS-4.1: control_area='exec_timeout' (was 'vty_line'), value in seconds
    """
    dev_id = uuid.uuid4()
    fields = [
        NormalizedField(
            device_id=dev_id,
            control_area="firmware_version",   # Phase 1 canonical name
            value="15.2",
            raw_line="version 15.2",
            confidence=1.0,
            source_lane="deterministic",
        ),
        NormalizedField(
            device_id=dev_id,
            control_area="domain_name",
            value="public.net",
            raw_line="ip domain-name public.net",
            confidence=1.0,
            source_lane="deterministic",
        ),
        NormalizedField(
            device_id=dev_id,
            control_area="exec_timeout",        # Phase 1 canonical name (was vty_line)
            value="600",                        # 10 min in seconds after transform
            raw_line="exec-timeout 10 0",
            confidence=1.0,
            source_lane="deterministic",
            instance_id="vty 0 4"
        ),
        NormalizedField(
            device_id=dev_id,
            control_area="exec_timeout",
            value="900",                        # 15 min — exceeds 600 limit
            raw_line="exec-timeout 15 0",
            confidence=1.0,
            source_lane="deterministic",
            instance_id="vty 5 15"
        )
    ]
    rules = [
        ComplianceRule(
            control_id="CIS-1.1",
            framework="CIS",
            control_area="firmware_version",
            check_type="min_version",
            expected_value="15.1",
            severity="high",
        ),
        ComplianceRule(
            control_id="CIS-3.1",
            framework="CIS",
            control_area="domain_name",
            check_type="presence_required",   # Phase 1: no longer equals 'internal.net'
            severity="medium",
        ),
        ComplianceRule(
            control_id="NIST-AC-12",
            framework="NIST_800_53",
            control_area="exec_timeout",
            check_type="max_value",
            expected_value="600",             # 10 minutes in seconds
            severity="high",
        ),
    ]

    findings = evaluate(device_id=dev_id, os_hint="cisco_ios", fields=fields, rules=rules)
    # 1 firmware_version, 1 domain_name, 2 exec_timeout instances
    assert len(findings) == 4, f"Expected 4 findings, got {len(findings)}: {[(f.control_id, f.status) for f in findings]}"

    finding_dict = {f.control_id: [] for f in findings}
    for f in findings:
        finding_dict[f.control_id].append(f)

    # firmware_version 15.2 >= 15.1 → pass
    assert finding_dict["CIS-1.1"][0].status == "pass"
    # domain_name 'public.net' is present → pass (presence_required)
    assert finding_dict["CIS-3.1"][0].status == "pass"
    # exec_timeout 600 <= 600 → pass; 900 > 600 → fail
    timeout_statuses = sorted([f.status for f in finding_dict["NIST-AC-12"]])
    assert "fail" in timeout_statuses, f"Expected at least one fail for exec_timeout 900s: {timeout_statuses}"
    assert "pass" in timeout_statuses, f"Expected at least one pass for exec_timeout 600s: {timeout_statuses}"

def test_rule_engine_needs_review_on_low_confidence_or_missing():
    dev_id = uuid.uuid4()
    fields = [
        NormalizedField(
            device_id=dev_id,
            control_area="enable_secret_type",   # Phase 1 canonical name
            value="5",                            # MD5 — low confidence LLM field
            raw_line="enable secret 5 $1$...",
            confidence=0.5,  # Below 0.75 threshold
            source_lane="llm",
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
        ),
        ComplianceRule(
            control_id="MISSING-RULE",
            framework="NIST_800_53",
            control_area="non_existent_area",
            check_type="equals",
            expected_value="foo",
            severity="low",
        ),
        ComplianceRule(
            control_id="ABSENCE-RULE",
            framework="NIST_800_53",
            control_area="telnet",
            check_type="absence_required",
            severity="low",
        ),
    ]

    findings = evaluate(device_id=dev_id, os_hint="cisco_ios", fields=fields, rules=rules)
    assert len(findings) == 3

    finding_dict = {f.control_id: f for f in findings}
    assert finding_dict["NIST-IA-5"].status == "needs_review"
    assert finding_dict["MISSING-RULE"].status == "needs_review"
    assert finding_dict["ABSENCE-RULE"].status == "pass"
