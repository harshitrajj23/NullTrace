"""code/tests/test_completion_flow_safety.py

Synthetic test for completion validator:
Verifies that if a COMPLETE candidate has an active data flow (even unlinked to the cluster),
the completion check strictly demotes it to INCOMPLETE with ACTIVE_DATA_FLOW.
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


def test_complete_candidate_demoted_by_unlinked_active_data_flow():
    """
    Synthetic test:
    Candidate has compliant, evidence-backed deleted resources (normally COMPLETE).
    An active data flow unlinked to the cluster is present in flow_risks.
    The completion check must fail-closed and demote the case to INCOMPLETE.
    """
    # 1. Compliant policy assessments (normally COMPLETE)
    policy_assessments = {
        "account_test_01": PolicyAssessment(
            resource_id="account_test_01",
            system_id="account_service",
            data_category="USER_PROFILE",
            applicable_rule_id="rule_01",
            required_action="DELETE",
            observed_state=ResourceState.ABSENT,
            policy_satisfied=True,
            rationale="Account verified absent in database snapshot",
            supporting_evidence_ids=["evidence_01"],
        ),
        "audit_record_test_01": PolicyAssessment(
            resource_id="audit_record_test_01",
            system_id="security_service",
            data_category="SECURITY_AUDIT_LOG",
            applicable_rule_id="rule_12",
            required_action="RETAIN",
            observed_state=ResourceState.PRESENT,
            policy_satisfied=True,
            rationale="Security audit log preserved within retention period",
            supporting_evidence_ids=["evidence_01"],
        ),
    }

    known_evidence_ids = {"evidence_01", "evidence_02"}
    resource_evidence_map = {
        "account_test_01": {"evidence_01"},
        "audit_record_test_01": {"evidence_01"},
    }

    # Clean case with no active flow risks -> COMPLETE
    clean_decision = validate_case_completion(
        case_id="case_synthetic_clean",
        is_non_deletion=False,
        policy_assessments=policy_assessments,
        flow_risks=[],
        known_evidence_ids=known_evidence_ids,
        resource_evidence_map=resource_evidence_map,
    )
    assert clean_decision.is_complete is True
    assert clean_decision.deletion_status == "COMPLETE"
    assert len(clean_decision.steps) == 2

    # 2. Inject an active data flow unlinked to the cluster
    unlinked_active_flow = ResurrectionRiskFinding(
        case_id="case_synthetic_unlinked_flow",
        risk_category=RiskCategory.ACTIVE_DATA_FLOW,
        source_system="integration_service",
        target_system="analytics_platform",
        implicated_resource="data_flow_synthetic_999",  # unlinked to cluster resources
        downstream_resource=None,
        evidence_ids=["evidence_02"],
        event_times=[datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)],
        time_relation=TimeRelation.PRIOR_TO_AUDIT,
        confidence="CONFIRMED",
        flow_status=FlowStatus.ACTIVE,
        reason="Active data flow on integration service capable of replicating data",
    )

    demoted_decision = validate_case_completion(
        case_id="case_synthetic_unlinked_flow",
        is_non_deletion=False,
        policy_assessments=policy_assessments,
        flow_risks=[unlinked_active_flow],
        known_evidence_ids=known_evidence_ids,
        resource_evidence_map=resource_evidence_map,
    )

    # Must be demoted to INCOMPLETE
    assert demoted_decision.is_complete is False
    assert demoted_decision.deletion_status == "INCOMPLETE"
    assert IncompleteReasonCode.ACTIVE_DATA_FLOW.value in demoted_decision.reasons_incomplete
