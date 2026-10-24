"""code/tests/test_planner.py

Unit tests for Evidence-Grounded Remediation Planner (Step H).

Tests cover:
1. Every allowed operation and state.
2. Exact phase and operation ordering.
3. System/resource sorting and consecutive numbering.
4. Empty evidence IDs on proposed remediation/verification.
5. Evidence-backed findings only.
6. No fabricated findings from uncorroborated claims.
7. NOT_APPLICABLE produces [].
8. Retained resources are not incorrectly deleted.
9. Active-flow and restore dependencies precede affected resource treatment.
10. Deterministic output.
"""

from datetime import datetime, timezone
import pytest

from code.src.ops import Step, validate_steps
from code.src.planner import (
    CasePlanResult,
    build_candidate_verification_steps,
    plan_case,
)
from code.src.rule_engine import PolicyAssessment
from code.src.state_reconstruction import ResourceState
from code.src.resurrection_detector import (
    FlowStatus,
    ResurrectionRiskFinding,
    RiskCategory,
    TimeRelation,
)


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


@pytest.fixture
def synthetic_policy_violations():
    """Provides synthetic policy violations covering delete, redact, anonymize, and restore."""
    return {
        "account_01": PolicyAssessment(
            resource_id="account_01",
            system_id="account_service",
            data_category="USER_PROFILE",
            applicable_rule_id="rule_01",
            required_action="DELETE",
            observed_state=ResourceState.PRESENT,
            policy_satisfied=False,
            rationale="Profile present",
            supporting_evidence_ids=["evidence_01"],
        ),
        "support_02": PolicyAssessment(
            resource_id="support_02",
            system_id="support_platform",
            data_category="SUPPORT_MESSAGE",
            applicable_rule_id="rule_05",
            required_action="REDACT",
            observed_state=ResourceState.PRESENT,
            policy_satisfied=False,
            rationale="Message exposes email",
            supporting_evidence_ids=["evidence_02"],
        ),
        "analytics_03": PolicyAssessment(
            resource_id="analytics_03",
            system_id="analytics_platform",
            data_category="ANALYTICS_PROFILE",
            applicable_rule_id="rule_07",
            required_action="ANONYMIZE",
            observed_state=ResourceState.PRESENT,
            policy_satisfied=False,
            rationale="Analytics identifiable",
            supporting_evidence_ids=["evidence_03"],
        ),
        "backup_04": PolicyAssessment(
            resource_id="backup_04",
            system_id="backup_service",
            data_category="BACKUP_ARCHIVE",
            applicable_rule_id="rule_14",
            required_action="RETAIN",
            observed_state=ResourceState.ACTIVE,
            policy_satisfied=False,
            rationale="Restore unblocked",
            supporting_evidence_ids=["evidence_04"],
        ),
    }


@pytest.fixture
def synthetic_flow_risks():
    """Provides synthetic flow risk findings."""
    return [
        ResurrectionRiskFinding(
            case_id="case_synth",
            risk_category=RiskCategory.ACTIVE_DATA_FLOW,
            source_system="integration_service",
            target_system="search_service",
            implicated_resource="data_flow_05",
            downstream_resource="search_05",
            evidence_ids=["evidence_05"],
            event_times=[_dt("2026-08-01T00:00:00Z")],
            time_relation=TimeRelation.PRIOR_TO_AUDIT,
            confidence="CONFIRMED",
            flow_status=FlowStatus.ACTIVE,
            reason="Connector active",
        ),
        ResurrectionRiskFinding(
            case_id="case_synth",
            risk_category=RiskCategory.RESTORE_RISK,
            source_system="backup_service",
            target_system="restored_environment",
            implicated_resource="backup_06",
            downstream_resource=None,
            evidence_ids=["evidence_06"],
            event_times=[_dt("2026-08-01T00:00:00Z")],
            time_relation=TimeRelation.PRIOR_TO_AUDIT,
            confidence="HIGH",
            flow_status=FlowStatus.ACTIVE,
            reason="Archive restorable",
        ),
    ]


# 1. Every allowed operation and state
def test_every_allowed_operation_and_state(synthetic_policy_violations, synthetic_flow_risks):
    plan = plan_case(
        case_id="case_full",
        is_non_deletion=False,
        policy_assessments=synthetic_policy_violations,
        flow_risks=synthetic_flow_risks,
    )

    operations_emitted = {s.operation for s in plan.steps}
    # Check that key operations across findings, remediation, and verification are present
    expected_ops = {
        "REPORT_REMAINING_RECORD",
        "REPORT_EXPOSED_PII",
        "REPORT_ACTIVE_DATA_FLOW",
        "REPORT_RESTORE_RISK",
        "DISABLE_DATA_FLOW",
        "BLOCK_RESTORE",
        "DELETE_RECORD",
        "REDACT_RECORD",
        "ANONYMIZE_RECORD",
        "VERIFY_RECORD_ABSENT",
        "VERIFY_RECORD_REDACTED",
        "VERIFY_RECORD_ANONYMIZED",
        "VERIFY_DATA_FLOW_DISABLED",
        "VERIFY_RESTORE_BLOCKED",
    }
    for op in expected_ops:
        assert op in operations_emitted, f"Expected operation {op} was not emitted"

    # Also check candidate verification for VERIFY_RECORD_PRESENT
    retained_assessment = {
        "audit_record_99": PolicyAssessment(
            resource_id="audit_record_99",
            system_id="security_service",
            data_category="SECURITY_AUDIT_LOG",
            applicable_rule_id="rule_12",
            required_action="RETAIN",
            observed_state=ResourceState.PRESENT,
            policy_satisfied=True,
            rationale="Retained audit log present",
            supporting_evidence_ids=["evidence_audit"],
        )
    }
    candidate_steps = build_candidate_verification_steps(retained_assessment, [])
    assert any(s.operation == "VERIFY_RECORD_PRESENT" and s.state == "PRESENT" for s in candidate_steps)

    # Validate against ops validator
    errs = validate_steps(plan.steps, "INCOMPLETE")
    assert errs == []


# 2. Exact phase and operation ordering
def test_exact_phase_and_operation_ordering(synthetic_policy_violations, synthetic_flow_risks):
    plan = plan_case(
        case_id="case_order",
        is_non_deletion=False,
        policy_assessments=synthetic_policy_violations,
        flow_risks=synthetic_flow_risks,
    )

    phases = [s.phase for s in plan.steps]
    # Check phase transitions: FINDING -> REMEDIATION -> VERIFICATION
    finding_end = max(i for i, p in enumerate(phases) if p == "FINDING")
    remediation_start = min(i for i, p in enumerate(phases) if p == "REMEDIATION")
    remediation_end = max(i for i, p in enumerate(phases) if p == "REMEDIATION")
    verification_start = min(i for i, p in enumerate(phases) if p == "VERIFICATION")

    assert finding_end < remediation_start
    assert remediation_end < verification_start

    # Within REMEDIATION, DISABLE_DATA_FLOW & BLOCK_RESTORE must precede DELETE/REDACT/ANONYMIZE
    rem_ops = [s.operation for s in plan.steps if s.phase == "REMEDIATION"]
    op_ranks = {
        "DISABLE_DATA_FLOW": 1,
        "BLOCK_RESTORE": 2,
        "DELETE_RECORD": 3,
        "REDACT_RECORD": 4,
        "ANONYMIZE_RECORD": 5,
    }
    ranks = [op_ranks[op] for op in rem_ops]
    assert ranks == sorted(ranks), f"Remediation operations not in exact rank order: {rem_ops}"


# 3. System/resource sorting and consecutive numbering
def test_system_resource_sorting_and_consecutive_numbering():
    # Two identical operations on different systems and resources
    assessments = {
        "account_zebra": PolicyAssessment(
            resource_id="account_zebra",
            system_id="b_system",
            data_category="USER_PROFILE",
            applicable_rule_id="rule_01",
            required_action="DELETE",
            observed_state=ResourceState.PRESENT,
            policy_satisfied=False,
            rationale="Present",
            supporting_evidence_ids=["ev_1"],
        ),
        "account_apple": PolicyAssessment(
            resource_id="account_apple",
            system_id="a_system",
            data_category="USER_PROFILE",
            applicable_rule_id="rule_01",
            required_action="DELETE",
            observed_state=ResourceState.PRESENT,
            policy_satisfied=False,
            rationale="Present",
            supporting_evidence_ids=["ev_2"],
        ),
        "account_banana": PolicyAssessment(
            resource_id="account_banana",
            system_id="a_system",
            data_category="USER_PROFILE",
            applicable_rule_id="rule_01",
            required_action="DELETE",
            observed_state=ResourceState.PRESENT,
            policy_satisfied=False,
            rationale="Present",
            supporting_evidence_ids=["ev_3"],
        ),
    }

    plan = plan_case("case_sort", False, assessments)
    findings = [s for s in plan.steps if s.phase == "FINDING"]

    # a_system/account_apple -> a_system/account_banana -> b_system/account_zebra
    assert findings[0].system_id == "a_system" and findings[0].resource_id == "account_apple"
    assert findings[1].system_id == "a_system" and findings[1].resource_id == "account_banana"
    assert findings[2].system_id == "b_system" and findings[2].resource_id == "account_zebra"

    # Consecutive numbering 1, 2, 3...
    step_nos = [s.step_no for s in plan.steps]
    assert step_nos == list(range(1, len(plan.steps) + 1))


# 4. Empty evidence IDs on proposed remediation/verification
def test_empty_evidence_ids_on_remediation_and_verification(synthetic_policy_violations):
    plan = plan_case("case_ev_empty", False, synthetic_policy_violations)
    for s in plan.steps:
        if s.phase in ("REMEDIATION", "VERIFICATION"):
            assert s.evidence_id == "", f"Expected empty evidence_id for {s.phase} step {s.step_no}"


# 5. Evidence-backed findings only
def test_evidence_backed_findings_only(synthetic_policy_violations):
    plan = plan_case("case_ev_backed", False, synthetic_policy_violations)
    findings = [s for s in plan.steps if s.phase == "FINDING"]
    assert len(findings) > 0
    for f in findings:
        assert f.evidence_id != "", f"Finding step {f.step_no} must cite evidence_id"


# 6. No fabricated findings from uncorroborated claims
def test_no_fabricated_findings_from_uncorroborated_claims():
    # Assessment with UNKNOWN state
    assessments = {
        "account_ghost": PolicyAssessment(
            resource_id="account_ghost",
            system_id="account_service",
            data_category="USER_PROFILE",
            applicable_rule_id="rule_01",
            required_action="DELETE",
            observed_state=ResourceState.UNKNOWN,
            policy_satisfied=False,
            rationale="Uncorroborated activity claim",
            supporting_evidence_ids=["activity_99"],
            gap_reason="Uncorroborated claim",
        )
    }
    # Flow risk with UNCORROBORATED_CLAIM confidence
    flow_risks = [
        ResurrectionRiskFinding(
            case_id="case_unverified",
            risk_category=RiskCategory.REPOPULATED_DOWNSTREAM,
            source_system="backup_service",
            target_system="search_service",
            implicated_resource="backup_unverified",
            downstream_resource="search_unverified",
            evidence_ids=["activity_100"],
            event_times=[_dt("2026-08-01T00:00:00Z")],
            time_relation=TimeRelation.PRIOR_TO_AUDIT,
            confidence="UNCORROBORATED_CLAIM",
            flow_status=FlowStatus.EXECUTED,
            reason="Unverified restore",
            unresolved_gaps=["No independent corroboration"],
        )
    ]

    plan = plan_case("case_unverified", False, assessments, flow_risks)
    # Zero fabricated findings
    assert len(plan.steps) == 0
    assert len(plan.unresolved_gaps) >= 2


# 7. NOT_APPLICABLE produces []
def test_not_applicable_produces_empty_steps(synthetic_policy_violations):
    plan = plan_case("case_na", True, synthetic_policy_violations)
    assert plan.deletion_status == "NOT_APPLICABLE"
    assert plan.steps == []


# 8. Retained resources are not incorrectly deleted
def test_retained_resources_not_incorrectly_deleted():
    retained_records = {
        "audit_record_77": PolicyAssessment(
            resource_id="audit_record_77",
            system_id="security_service",
            data_category="SECURITY_AUDIT_LOG",
            applicable_rule_id="rule_12",
            required_action="RETAIN",
            observed_state=ResourceState.PRESENT,
            policy_satisfied=True,
            rationale="Security audit log within retention period",
            supporting_evidence_ids=["evidence_audit"],
        ),
        "legal_hold_88": PolicyAssessment(
            resource_id="legal_hold_88",
            system_id="legal_service",
            data_category="LEGAL_HOLD_RECORD",
            applicable_rule_id="rule_13",
            required_action="RETAIN",
            observed_state=ResourceState.PRESENT,
            policy_satisfied=True,
            rationale="Active legal hold record",
            supporting_evidence_ids=["evidence_legal"],
        ),
    }

    plan = plan_case("case_retain", False, retained_records)
    # Retained records that satisfy policy must NOT emit DELETE_RECORD or REDACT_RECORD
    destructive_ops = {s.operation for s in plan.steps if s.operation in ("DELETE_RECORD", "REDACT_RECORD")}
    assert len(destructive_ops) == 0


# 9. Active-flow and restore dependencies precede affected resource treatment
def test_active_flow_and_restore_dependencies_precede_resource_treatment(
    synthetic_policy_violations, synthetic_flow_risks
):
    plan = plan_case("case_deps", False, synthetic_policy_violations, synthetic_flow_risks)
    rem_steps = [s for s in plan.steps if s.phase == "REMEDIATION"]

    disable_idx = min(i for i, s in enumerate(rem_steps) if s.operation == "DISABLE_DATA_FLOW")
    block_idx = min(i for i, s in enumerate(rem_steps) if s.operation == "BLOCK_RESTORE")
    delete_idx = min(i for i, s in enumerate(rem_steps) if s.operation == "DELETE_RECORD")

    assert disable_idx < delete_idx, "DISABLE_DATA_FLOW must precede DELETE_RECORD"
    assert block_idx < delete_idx, "BLOCK_RESTORE must precede DELETE_RECORD"


# 10. Deterministic output
def test_deterministic_output(synthetic_policy_violations, synthetic_flow_risks):
    plan1 = plan_case("case_det", False, synthetic_policy_violations, synthetic_flow_risks)
    plan2 = plan_case("case_det", False, synthetic_policy_violations, synthetic_flow_risks)

    assert plan1.deletion_status == plan2.deletion_status
    assert len(plan1.steps) == len(plan2.steps)
    for s1, s2 in zip(plan1.steps, plan2.steps):
        assert s1 == s2
