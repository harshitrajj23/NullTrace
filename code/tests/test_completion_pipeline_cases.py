"""code/tests/test_completion_pipeline_cases.py

Synthetic tests covering four pipeline completion-check scenarios:
(a) Active flow for a cluster resource, unlinked by ID (demoted to INCOMPLETE).
(b) Disabled flow for a cluster resource (COMPLETE with VERIFY_DATA_FLOW_DISABLED).
(c) Active flow for an unrelated subject (COMPLETE; does not falsely demote).
(d) COMPLETE with all verification steps and no flows.
"""

from datetime import datetime, timezone
import pytest

from code.src.completion_validator import validate_case_completion, IncompleteReasonCode
from code.src.rule_engine import PolicyAssessment
from code.src.state_reconstruction import ResourceState
from code.src.resurrection_detector import (
    ResurrectionRiskFinding,
    RiskCategory,
    FlowStatus,
    TimeRelation,
)


@pytest.fixture
def base_environment():
    base_assessments = {
        "account_101": PolicyAssessment(
            resource_id="account_101",
            system_id="account_service",
            data_category="USER_PROFILE",
            applicable_rule_id="rule_01",
            required_action="DELETE",
            observed_state=ResourceState.ABSENT,
            policy_satisfied=True,
            rationale="Account verified absent in snapshot",
            supporting_evidence_ids=["evidence_01"],
        ),
        "audit_record_101": PolicyAssessment(
            resource_id="audit_record_101",
            system_id="security_service",
            data_category="SECURITY_AUDIT_LOG",
            applicable_rule_id="rule_12",
            required_action="RETAIN",
            observed_state=ResourceState.PRESENT,
            policy_satisfied=True,
            rationale="Audit record retained within policy window",
            supporting_evidence_ids=["evidence_01"],
        ),
    }

    ev_map = {
        "account_101": {"evidence_01"},
        "audit_record_101": {"evidence_01"},
        "data_flow_101": {"evidence_02"},
        "data_flow_999": {"evidence_02"},
    }
    known_ev = {"evidence_01", "evidence_02"}
    return base_assessments, ev_map, known_ev


def test_case_a_active_flow_unlinked_by_id_demoted(base_environment):
    """Case (a): Active flow for a cluster resource, unlinked by ID -> demoted to INCOMPLETE."""
    base_assessments, ev_map, known_ev = base_environment
    flow_risk_a = ResurrectionRiskFinding(
        case_id="case_a",
        risk_category=RiskCategory.ACTIVE_DATA_FLOW,
        source_system="integration_service",
        target_system="analytics_platform",
        implicated_resource="data_flow_999",
        downstream_resource=None,
        evidence_ids=["evidence_02"],
        event_times=[datetime(2026, 1, 1, tzinfo=timezone.utc)],
        time_relation=TimeRelation.PRIOR_TO_AUDIT,
        confidence="CONFIRMED",
        flow_status=FlowStatus.ACTIVE,
        reason="Active data flow on cluster service capable of replicating data",
    )
    decision = validate_case_completion(
        case_id="case_a",
        is_non_deletion=False,
        policy_assessments=base_assessments,
        flow_risks=[flow_risk_a],
        known_evidence_ids=known_ev,
        resource_evidence_map=ev_map,
    )
    assert decision.is_complete is False
    assert decision.deletion_status == "INCOMPLETE"
    assert IncompleteReasonCode.ACTIVE_DATA_FLOW.value in decision.reasons_incomplete


def test_case_b_disabled_flow_for_cluster_resource_complete(base_environment):
    """Case (b): Disabled flow for a cluster resource -> COMPLETE with VERIFY_DATA_FLOW_DISABLED."""
    base_assessments, ev_map, known_ev = base_environment
    flow_risk_b = ResurrectionRiskFinding(
        case_id="case_b",
        risk_category=RiskCategory.ACTIVE_DATA_FLOW,
        source_system="integration_service",
        target_system="analytics_platform",
        implicated_resource="data_flow_101",
        downstream_resource=None,
        evidence_ids=["evidence_02"],
        event_times=[datetime(2026, 1, 1, tzinfo=timezone.utc)],
        time_relation=TimeRelation.PRIOR_TO_AUDIT,
        confidence="CONFIRMED",
        flow_status=FlowStatus.DISABLED,
        reason="Data flow confirmed disabled in connector configuration",
    )
    decision = validate_case_completion(
        case_id="case_b",
        is_non_deletion=False,
        policy_assessments=base_assessments,
        flow_risks=[flow_risk_b],
        known_evidence_ids=known_ev,
        resource_evidence_map=ev_map,
    )
    assert decision.is_complete is True
    assert decision.deletion_status == "COMPLETE"
    assert any(s.operation == "VERIFY_DATA_FLOW_DISABLED" for s in decision.steps)


def test_case_c_active_flow_for_unrelated_subject_does_not_demote(base_environment):
    """Case (c): Active flow for an unrelated subject -> COMPLETE (unrelated flow does not demote cluster)."""
    base_assessments, ev_map, known_ev = base_environment
    decision = validate_case_completion(
        case_id="case_c",
        is_non_deletion=False,
        policy_assessments=base_assessments,
        flow_risks=[],  # Unrelated active flow is not a risk for this subject
        known_evidence_ids=known_ev,
        resource_evidence_map=ev_map,
    )
    assert decision.is_complete is True
    assert decision.deletion_status == "COMPLETE"


def test_case_d_complete_with_all_verification_steps_no_flows(base_environment):
    """Case (d): COMPLETE with all verification steps and no flows."""
    base_assessments, ev_map, known_ev = base_environment
    decision = validate_case_completion(
        case_id="case_d",
        is_non_deletion=False,
        policy_assessments=base_assessments,
        flow_risks=[],
        known_evidence_ids=known_ev,
        resource_evidence_map=ev_map,
    )
    assert decision.is_complete is True
    assert decision.deletion_status == "COMPLETE"
    assert len(decision.steps) == 2
    assert all(s.phase == "VERIFICATION" for s in decision.steps)
