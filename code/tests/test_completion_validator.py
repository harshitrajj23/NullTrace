"""code/tests/test_completion_validator.py

Unit tests for Strict Deterministic Completion Validator (Step I).

Tests cover:
1. Fully evidenced synthetic COMPLETE case.
2. Each individual reason a case must remain INCOMPLETE (10+ reason codes).
3. Unknown state never becoming COMPLETE.
4. Active sync or restore risk blocking COMPLETE.
5. Uncorroborated operation success blocking COMPLETE.
6. Retained-record and tombstone policy compliance.
7. Evidence-backed verification steps only on COMPLETE.
8. NOT_APPLICABLE always producing steps_json = [].
9. Empty resources never implying successful deletion.
10. Deterministic repeated execution.
11. Valid operation/state combinations and sorting.
"""

from datetime import datetime, timezone
import pytest

from code.src.completion_validator import (
    IncompleteReasonCode,
    ValidationDecision,
    build_evidence_backed_verification_steps,
    validate_case_completion,
)
from code.src.identity import Cluster, Conflict, IdentifierNode
from code.src.models import SourceRef
from code.src.ops import Step, validate_steps
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
def synthetic_complete_assessments():
    """Provides a set of fully compliant resource assessments citing real evidence IDs."""
    return {
        "account_01": PolicyAssessment(
            resource_id="account_01",
            system_id="account_service",
            data_category="USER_PROFILE",
            applicable_rule_id="rule_01",
            required_action="DELETE",
            observed_state=ResourceState.ABSENT,
            policy_satisfied=True,
            rationale="Profile absent",
            supporting_evidence_ids=["evidence_01"],
        ),
        "tombstone_02": PolicyAssessment(
            resource_id="tombstone_02",
            system_id="auth_service",
            data_category="ACCOUNT_TOMBSTONE",
            applicable_rule_id="rule_04",
            required_action="REDACT",
            observed_state=ResourceState.REDACTED,
            policy_satisfied=True,
            is_tombstone=True,
            tombstone_direct_pii_removed=True,
            rationale="Tombstone preserved with direct PII stripped",
            supporting_evidence_ids=["evidence_02"],
        ),
        "audit_03": PolicyAssessment(
            resource_id="audit_03",
            system_id="security_audit",
            data_category="SECURITY_AUDIT_LOG",
            applicable_rule_id="rule_12",
            required_action="RETAIN",
            observed_state=ResourceState.PRESENT,
            policy_satisfied=True,
            rationale="Mandatory security audit preserved",
            supporting_evidence_ids=["evidence_03"],
        ),
        "backup_04": PolicyAssessment(
            resource_id="backup_04",
            system_id="backup_service",
            data_category="BACKUP_ARCHIVE",
            applicable_rule_id="rule_14",
            required_action="RETAIN",
            observed_state=ResourceState.BLOCKED,
            policy_satisfied=True,
            rationale="Backup restore path blocked",
            supporting_evidence_ids=["evidence_04"],
        ),
    }


@pytest.fixture
def synthetic_benign_flows():
    """Provides corroborated disabled flows and blocked restores."""
    return [
        ResurrectionRiskFinding(
            case_id="case_synth_01",
            risk_category=RiskCategory.ACTIVE_DATA_FLOW,
            source_system="integration_service",
            target_system="search_service",
            implicated_resource="sync_flow_01",
            downstream_resource="search_01",
            evidence_ids=["evidence_05"],
            event_times=[_dt("2026-10-01T12:00:00+00:00")],
            time_relation=TimeRelation.PRIOR_TO_AUDIT,
            confidence="CORROBORATED_BY_EVIDENCE",
            flow_status=FlowStatus.DISABLED,
            reason="Sync flow disabled before audit",
        ),
        ResurrectionRiskFinding(
            case_id="case_synth_01",
            risk_category=RiskCategory.RESTORE_RISK,
            source_system="backup_service",
            target_system="account_db",
            implicated_resource="restore_job_02",
            downstream_resource=None,
            evidence_ids=["evidence_06"],
            event_times=[_dt("2026-10-01T13:00:00+00:00")],
            time_relation=TimeRelation.PRIOR_TO_AUDIT,
            confidence="CORROBORATED_BY_EVIDENCE",
            flow_status=FlowStatus.BLOCKED,
            reason="Restore path blocked before audit",
        ),
    ]


@pytest.fixture
def known_evidence():
    return {"evidence_01", "evidence_02", "evidence_03", "evidence_04", "evidence_05", "evidence_06"}


def test_fully_evidenced_complete_case(synthetic_complete_assessments, synthetic_benign_flows, known_evidence):
    """A fully evidenced case with all requirements met qualifies as COMPLETE."""
    cluster = Cluster(case_id="case_synth_01", conflicts=[])

    decision = validate_case_completion(
        case_id="case_synth_01",
        is_non_deletion=False,
        policy_assessments=synthetic_complete_assessments,
        flow_risks=synthetic_benign_flows,
        identity_cluster=cluster,
        known_evidence_ids=known_evidence,
    )

    assert decision.is_complete is True
    assert decision.deletion_status == "COMPLETE"
    assert decision.reasons_incomplete == []
    assert len(decision.steps) > 0

    # Only verification steps allowed on COMPLETE
    for s in decision.steps:
        assert s.phase == "VERIFICATION"
        assert s.evidence_id != ""
        assert s.evidence_id in known_evidence

    # Must pass strict grader contract validation
    errs = validate_steps(decision.steps, "COMPLETE", known_evidence)
    assert errs == []

    # Check step consecutive numbering
    step_nos = [s.step_no for s in decision.steps]
    assert step_nos == list(range(1, len(decision.steps) + 1))


def test_not_applicable_always_empty_steps():
    """Non-deletion inquiry must produce NOT_APPLICABLE with steps = []."""
    decision = validate_case_completion(
        case_id="case_na",
        is_non_deletion=True,
        policy_assessments={},
    )

    assert decision.is_complete is False
    assert decision.deletion_status == "NOT_APPLICABLE"
    assert decision.steps == []
    assert IncompleteReasonCode.NON_DELETION_REQUEST.value in decision.reasons_incomplete


def test_empty_resources_never_implies_complete():
    """Lack of findings / empty resources must never produce COMPLETE."""
    decision = validate_case_completion(
        case_id="case_empty",
        is_non_deletion=False,
        policy_assessments={},
    )

    assert decision.is_complete is False
    assert decision.deletion_status == "INCOMPLETE"
    assert IncompleteReasonCode.NO_RESOURCES_IDENTIFIED.value in decision.reasons_incomplete


def test_identity_conflict_blocks_complete(synthetic_complete_assessments, synthetic_benign_flows, known_evidence):
    """Unresolved identity conflicts must block COMPLETE."""
    conflict_node = IdentifierNode(
        kind="email",
        value_raw="other@example.com",
        value_norm="other@example.com",
        role="unknown",
    )
    cluster = Cluster(
        case_id="case_synth_01",
        conflicts=[
            Conflict(
                conflict_type="EMAIL_CONFLICT",
                details="Conflicting account found",
                nodes=[conflict_node],
                source=SourceRef("user_audit_log.csv", 42),
            )
        ],
    )

    decision = validate_case_completion(
        case_id="case_synth_01",
        is_non_deletion=False,
        policy_assessments=synthetic_complete_assessments,
        flow_risks=synthetic_benign_flows,
        identity_cluster=cluster,
        known_evidence_ids=known_evidence,
    )

    assert decision.is_complete is False
    assert decision.deletion_status == "INCOMPLETE"
    assert IncompleteReasonCode.IDENTITY_CONFLICT.value in decision.reasons_incomplete


def test_unknown_resource_state_blocks_complete(synthetic_complete_assessments, synthetic_benign_flows, known_evidence):
    """An unknown resource state must resolve to INCOMPLETE."""
    assessments = dict(synthetic_complete_assessments)
    assessments["account_01"] = PolicyAssessment(
        resource_id="account_01",
        system_id="account_service",
        data_category="USER_PROFILE",
        applicable_rule_id="rule_01",
        required_action="DELETE",
        observed_state=ResourceState.UNKNOWN,
        policy_satisfied=False,
        rationale="State could not be corroborated",
        supporting_evidence_ids=["evidence_01"],
    )

    decision = validate_case_completion(
        case_id="case_synth_01",
        is_non_deletion=False,
        policy_assessments=assessments,
        flow_risks=synthetic_benign_flows,
        known_evidence_ids=known_evidence,
    )

    assert decision.is_complete is False
    assert decision.deletion_status == "INCOMPLETE"
    assert IncompleteReasonCode.UNKNOWN_RESOURCE_STATE.value in decision.reasons_incomplete


def test_unsatisfied_policy_blocks_complete(synthetic_complete_assessments, synthetic_benign_flows, known_evidence):
    """An unsatisfied policy (e.g. record still present when delete required) blocks COMPLETE."""
    assessments = dict(synthetic_complete_assessments)
    assessments["account_01"] = PolicyAssessment(
        resource_id="account_01",
        system_id="account_service",
        data_category="USER_PROFILE",
        applicable_rule_id="rule_01",
        required_action="DELETE",
        observed_state=ResourceState.PRESENT,
        policy_satisfied=False,
        rationale="Record still present",
        supporting_evidence_ids=["evidence_01"],
    )

    decision = validate_case_completion(
        case_id="case_synth_01",
        is_non_deletion=False,
        policy_assessments=assessments,
        flow_risks=synthetic_benign_flows,
        known_evidence_ids=known_evidence,
    )

    assert decision.is_complete is False
    assert decision.deletion_status == "INCOMPLETE"
    assert IncompleteReasonCode.UNSATISFIED_POLICY.value in decision.reasons_incomplete


def test_missing_retained_record_blocks_complete(synthetic_complete_assessments, synthetic_benign_flows, known_evidence):
    """A required retained record (e.g. security audit log) that is missing/ABSENT blocks COMPLETE."""
    assessments = dict(synthetic_complete_assessments)
    assessments["audit_03"] = PolicyAssessment(
        resource_id="audit_03",
        system_id="security_audit",
        data_category="SECURITY_AUDIT_LOG",
        applicable_rule_id="rule_12",
        required_action="RETAIN",
        observed_state=ResourceState.ABSENT,
        policy_satisfied=False,
        rationale="Retained audit log was improperly deleted",
        supporting_evidence_ids=["evidence_03"],
    )

    decision = validate_case_completion(
        case_id="case_synth_01",
        is_non_deletion=False,
        policy_assessments=assessments,
        flow_risks=synthetic_benign_flows,
        known_evidence_ids=known_evidence,
    )

    assert decision.is_complete is False
    assert decision.deletion_status == "INCOMPLETE"
    assert IncompleteReasonCode.MISSING_RETAINED_RECORD.value in decision.reasons_incomplete


def test_tombstone_direct_pii_exposed_blocks_complete(synthetic_complete_assessments, synthetic_benign_flows, known_evidence):
    """An account tombstone that still exposes direct PII blocks COMPLETE."""
    assessments = dict(synthetic_complete_assessments)
    assessments["tombstone_02"] = PolicyAssessment(
        resource_id="tombstone_02",
        system_id="auth_service",
        data_category="ACCOUNT_TOMBSTONE",
        applicable_rule_id="rule_04",
        required_action="REDACT",
        observed_state=ResourceState.REDACTED,
        policy_satisfied=False,
        is_tombstone=True,
        tombstone_direct_pii_removed=False,
        rationale="Direct PII still present in tombstone",
        supporting_evidence_ids=["evidence_02"],
    )

    decision = validate_case_completion(
        case_id="case_synth_01",
        is_non_deletion=False,
        policy_assessments=assessments,
        flow_risks=synthetic_benign_flows,
        known_evidence_ids=known_evidence,
    )

    assert decision.is_complete is False
    assert decision.deletion_status == "INCOMPLETE"
    assert IncompleteReasonCode.TOMBSTONE_DIRECT_PII_EXPOSED.value in decision.reasons_incomplete


def test_active_data_flow_blocks_complete(synthetic_complete_assessments, known_evidence):
    """An active data flow that could recreate data blocks COMPLETE."""
    active_flows = [
        ResurrectionRiskFinding(
            case_id="case_synth_01",
            risk_category=RiskCategory.ACTIVE_DATA_FLOW,
            source_system="integration_service",
            target_system="search_service",
            implicated_resource="sync_flow_01",
            downstream_resource="search_01",
            evidence_ids=["evidence_05"],
            event_times=[_dt("2026-10-01T12:00:00+00:00")],
            time_relation=TimeRelation.PRIOR_TO_AUDIT,
            confidence="CORROBORATED_BY_EVIDENCE",
            flow_status=FlowStatus.ACTIVE,
            reason="Sync is actively running",
        )
    ]

    decision = validate_case_completion(
        case_id="case_synth_01",
        is_non_deletion=False,
        policy_assessments=synthetic_complete_assessments,
        flow_risks=active_flows,
        known_evidence_ids=known_evidence,
    )

    assert decision.is_complete is False
    assert decision.deletion_status == "INCOMPLETE"
    assert IncompleteReasonCode.ACTIVE_DATA_FLOW.value in decision.reasons_incomplete


def test_active_restore_risk_blocks_complete(synthetic_complete_assessments, known_evidence):
    """An active restore risk that could restore deleted data blocks COMPLETE."""
    active_restore = [
        ResurrectionRiskFinding(
            case_id="case_synth_01",
            risk_category=RiskCategory.RESTORE_RISK,
            source_system="backup_service",
            target_system="account_db",
            implicated_resource="restore_job_02",
            downstream_resource=None,
            evidence_ids=["evidence_06"],
            event_times=[_dt("2026-10-01T13:00:00+00:00")],
            time_relation=TimeRelation.PRIOR_TO_AUDIT,
            confidence="CORROBORATED_BY_EVIDENCE",
            flow_status=FlowStatus.ACTIVE,
            reason="Restore path is unblocked",
        )
    ]

    decision = validate_case_completion(
        case_id="case_synth_01",
        is_non_deletion=False,
        policy_assessments=synthetic_complete_assessments,
        flow_risks=active_restore,
        known_evidence_ids=known_evidence,
    )

    assert decision.is_complete is False
    assert decision.deletion_status == "INCOMPLETE"
    assert IncompleteReasonCode.ACTIVE_RESTORE_RISK.value in decision.reasons_incomplete


def test_uncorroborated_operation_claim_blocks_complete(synthetic_complete_assessments, known_evidence):
    """Uncorroborated operation claims (reported without evidence proof) block COMPLETE."""
    unproven_flow = [
        ResurrectionRiskFinding(
            case_id="case_synth_01",
            risk_category=RiskCategory.ACTIVE_DATA_FLOW,
            source_system="integration_service",
            target_system="search_service",
            implicated_resource="sync_flow_01",
            downstream_resource="search_01",
            evidence_ids=["evidence_05"],
            event_times=[_dt("2026-10-01T12:00:00+00:00")],
            time_relation=TimeRelation.PRIOR_TO_AUDIT,
            confidence="UNCORROBORATED_CLAIM",
            flow_status=FlowStatus.DISABLED,
            reason="Claim of disablement not corroborated by evidence",
        )
    ]

    decision = validate_case_completion(
        case_id="case_synth_01",
        is_non_deletion=False,
        policy_assessments=synthetic_complete_assessments,
        flow_risks=unproven_flow,
        known_evidence_ids=known_evidence,
    )

    assert decision.is_complete is False
    assert decision.deletion_status == "INCOMPLETE"
    assert IncompleteReasonCode.UNCORROBORATED_OPERATION_CLAIM.value in decision.reasons_incomplete


def test_missing_verification_evidence_blocks_complete(synthetic_complete_assessments, synthetic_benign_flows, known_evidence):
    """A resource lacking supporting evidence IDs or citing unknown evidence blocks COMPLETE."""
    assessments = dict(synthetic_complete_assessments)
    assessments["account_01"] = PolicyAssessment(
        resource_id="account_01",
        system_id="account_service",
        data_category="USER_PROFILE",
        applicable_rule_id="rule_01",
        required_action="DELETE",
        observed_state=ResourceState.ABSENT,
        policy_satisfied=True,
        rationale="Missing evidence",
        supporting_evidence_ids=["unknown_evidence_999"],
    )

    decision = validate_case_completion(
        case_id="case_synth_01",
        is_non_deletion=False,
        policy_assessments=assessments,
        flow_risks=synthetic_benign_flows,
        known_evidence_ids=known_evidence,
    )

    assert decision.is_complete is False
    assert decision.deletion_status == "INCOMPLETE"
    assert IncompleteReasonCode.MISSING_VERIFICATION_EVIDENCE.value in decision.reasons_incomplete


def test_deterministic_repeated_execution(synthetic_complete_assessments, synthetic_benign_flows, known_evidence):
    """Repeated executions produce identical decisions and step orderings."""
    d1 = validate_case_completion(
        case_id="case_synth_01",
        is_non_deletion=False,
        policy_assessments=synthetic_complete_assessments,
        flow_risks=synthetic_benign_flows,
        known_evidence_ids=known_evidence,
    )
    d2 = validate_case_completion(
        case_id="case_synth_01",
        is_non_deletion=False,
        policy_assessments=synthetic_complete_assessments,
        flow_risks=synthetic_benign_flows,
        known_evidence_ids=known_evidence,
    )

    assert d1.deletion_status == d2.deletion_status
    assert d1.is_complete == d2.is_complete
    assert d1.reasons_incomplete == d2.reasons_incomplete
    assert len(d1.steps) == len(d2.steps)
    for s1, s2 in zip(d1.steps, d2.steps):
        assert s1.to_dict() == s2.to_dict()


def test_arbitrary_evidence_id_not_supporting_resource_blocks_complete(
    synthetic_complete_assessments, synthetic_benign_flows, known_evidence
):
    """
    Regression test for Step I.1 audit:
    An evidence ID that exists in known_evidence_ids but does NOT support the specific
    resource/flow being assessed must be rejected, preventing false COMPLETE promotion.
    """
    valid_map = {
        "account_01": {"evidence_01"},
        "tombstone_02": {"evidence_02"},
        "audit_03": {"evidence_03"},
        "backup_04": {"evidence_04"},
        "sync_flow_01": {"evidence_05"},
        "restore_job_02": {"evidence_06"},
    }

    # 1. Valid map produces COMPLETE
    clean_dec = validate_case_completion(
        case_id="case_synth_01",
        is_non_deletion=False,
        policy_assessments=synthetic_complete_assessments,
        flow_risks=synthetic_benign_flows,
        known_evidence_ids=known_evidence,
        resource_evidence_map=valid_map,
    )
    assert clean_dec.is_complete is True
    assert clean_dec.deletion_status == "COMPLETE"

    # 2. Tampered assessment: account_01 cites evidence_06 (which exists in known_evidence, but belongs to restore_job_02)
    tampered_assessments = dict(synthetic_complete_assessments)
    tampered_assessments["account_01"] = PolicyAssessment(
        resource_id="account_01",
        system_id="account_service",
        data_category="USER_PROFILE",
        applicable_rule_id="rule_01",
        required_action="DELETE",
        observed_state=ResourceState.ABSENT,
        policy_satisfied=True,
        rationale="Arbitrary evidence ID attached",
        supporting_evidence_ids=["evidence_06"],
    )

    tampered_dec = validate_case_completion(
        case_id="case_synth_01",
        is_non_deletion=False,
        policy_assessments=tampered_assessments,
        flow_risks=synthetic_benign_flows,
        known_evidence_ids=known_evidence,
        resource_evidence_map=valid_map,
    )

    assert tampered_dec.is_complete is False
    assert tampered_dec.deletion_status == "INCOMPLETE"
    assert IncompleteReasonCode.MISSING_VERIFICATION_EVIDENCE.value in tampered_dec.reasons_incomplete

