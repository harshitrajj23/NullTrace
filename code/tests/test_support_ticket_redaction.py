"""code/tests/test_support_ticket_redaction.py

Regression test suite for Support Ticket Redaction-State Interpretation (Step L):
1. Explicitly verified historical redaction.
2. An active unredacted identifier.
3. Missing redaction evidence.
4. Contradictory redaction evidence.
"""

from datetime import datetime, timezone
import pytest

from code.src.identity import Cluster, IdentifierNode
from code.src.loader import Dataset, LoaderReport
from code.src.models import DeletionRequest, DeletionRule, SourceRef, SystemActivity
from code.src.state_reconstruction import (
    EvidenceObservation,
    ResourceState,
    reconstruct_resource_state,
)
from code.src.rule_engine import assess_resource_policy
from code.src.completion_validator import validate_case_completion, IncompleteReasonCode
from code.src.planner import plan_case


def _make_dummy_dataset(activities=None):
    return Dataset(
        data_dir="./dataset",
        deletion_requests=[],
        sample_deletion_requests=[],
        sample_output=[],
        user_identities=[],
        user_audit_log=[],
        system_activity=activities or [],
        deletion_rules=[
            DeletionRule("rule_05", "SUPPORT_MESSAGE", "Shared support message", "REDACT", SourceRef("deletion_rules.csv", 5)),
            DeletionRule("rule_06", "SUPPORT_ATTACHMENT", "Support attachment", "DELETE", SourceRef("deletion_rules.csv", 6)),
        ],
        evidence_files=[],
        report=LoaderReport(),
    )


def test_1_explicitly_verified_historical_redaction():
    """1. Explicitly verified historical redaction produces VERIFY_RECORD_REDACTED."""
    dataset = _make_dummy_dataset()
    cutoff = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)

    # Support ticket observation with verified redaction (PII masked, requester fields None)
    verified_obs = EvidenceObservation(
        resource_id="support_4715",
        observed_state=ResourceState.REDACTED,
        timestamp=datetime(2026, 9, 15, 10, 0, 5, tzinfo=timezone.utc),
        evidence_id="evidence_92",
        source_path="evidence/records/service_export.json",
        is_direct=True,
        details={
            "customer_reference": "user_26",
            "message_excerpt": "Customer followed up about an order update.",
            "requester_email": None,
            "requester_phone": None,
            "requester_name": None,
        },
    )

    recon = reconstruct_resource_state(
        resource_id="support_4715",
        audit_at=cutoff,
        direct_observations=[verified_obs],
        activity_events=[],
    )
    assert recon.state == ResourceState.REDACTED
    assert recon.provenance_evidence_id == "evidence_92"

    assess = assess_resource_policy(recon, dataset.deletion_rules)
    assert assess.policy_satisfied is True
    assert assess.required_action == "REDACT"
    assert assess.supporting_evidence_ids == ["evidence_92"]

    cluster = Cluster(case_id="case_26")
    cluster.nodes["user_26"] = IdentifierNode("user_id", "user_26", "user_26", SourceRef("test.csv", 1))

    decision = validate_case_completion(
        case_id="case_26",
        is_non_deletion=False,
        policy_assessments={"support_4715": assess},
        identity_cluster=cluster,
        known_evidence_ids={"evidence_92"},
    )
    assert decision.is_complete is True
    assert decision.deletion_status == "COMPLETE"
    assert len(decision.steps) == 1
    step = decision.steps[0]
    assert step.phase == "VERIFICATION"
    assert step.operation == "VERIFY_RECORD_REDACTED"
    assert step.state == "REDACTED"
    assert step.evidence_id == "evidence_92"


def test_2_active_unredacted_direct_identifier():
    """2. An active unredacted identifier is flagged as REPORT_EXPOSED_PII and requires REDACT_RECORD."""
    dataset = _make_dummy_dataset()
    cutoff = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)

    # Support ticket observation with active email exposed in message body
    unredacted_obs = EvidenceObservation(
        resource_id="support_5281",
        observed_state=ResourceState.PRESENT,
        timestamp=datetime(2026, 9, 15, 10, 48, 45, tzinfo=timezone.utc),
        evidence_id="evidence_92",
        source_path="evidence/records/service_export.json",
        is_direct=True,
        details={
            "customer_reference": "user_29",
            "message_excerpt": "Please send delivery update to noah.f438085@outlook.com",
            "requester_email": "noah.f438085@outlook.com",
        },
    )

    recon = reconstruct_resource_state(
        resource_id="support_5281",
        audit_at=cutoff,
        direct_observations=[unredacted_obs],
        activity_events=[],
    )
    assert recon.state == ResourceState.PRESENT

    assess = assess_resource_policy(recon, dataset.deletion_rules)
    assert assess.policy_satisfied is False  # Policy requires REDACT, but state is PRESENT

    plan = plan_case(
        case_id="case_29",
        is_non_deletion=False,
        policy_assessments={"support_5281": assess},
    )
    ops = [s.operation for s in plan.steps]
    assert "REPORT_EXPOSED_PII" in ops
    assert "REDACT_RECORD" in ops
    assert "VERIFY_RECORD_REDACTED" in ops


def test_3_missing_redaction_evidence():
    """3. Missing redaction evidence preserves INCOMPLETE."""
    dataset = _make_dummy_dataset()
    cutoff = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)

    # Activity claims redaction succeeded, but NO direct evidence corroborates it
    act = SystemActivity(
        activity_id="act_redact_303",
        event_time_raw="2026-09-14T10:00:00Z",
        event_time=datetime(2026, 9, 14, 10, 0, 0, tzinfo=timezone.utc),
        event_type="REDACT_RECORD",
        source_system="deletion_worker",
        target_system="support_platform",
        resource_id="support_303",
        reported_result="SUCCESS",
        details="Redacted ticket headers",
        source=SourceRef("system_activity.csv", 1),
    )

    recon = reconstruct_resource_state(
        resource_id="support_303",
        audit_at=cutoff,
        direct_observations=[],  # Missing direct evidence
        activity_events=[act],
    )
    assert recon.state == ResourceState.UNKNOWN
    assert recon.is_uncorroborated_claim is True

    assess = assess_resource_policy(recon, dataset.deletion_rules)
    assert assess.policy_satisfied is False

    decision = validate_case_completion(
        case_id="case_test_303",
        is_non_deletion=False,
        policy_assessments={"support_303": assess},
    )
    assert decision.is_complete is False
    assert decision.deletion_status == "INCOMPLETE"
    assert IncompleteReasonCode.UNKNOWN_RESOURCE_STATE.value in decision.reasons_incomplete


def test_4_contradictory_redaction_evidence():
    """4. Contradictory redaction evidence preserves INCOMPLETE due to UNKNOWN state."""
    dataset = _make_dummy_dataset()
    cutoff = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
    obs_time = datetime(2026, 9, 15, 10, 0, 0, tzinfo=timezone.utc)

    # Conflicting observations at the same timestamp
    obs_redacted = EvidenceObservation(
        resource_id="support_404",
        observed_state=ResourceState.REDACTED,
        timestamp=obs_time,
        evidence_id="evidence_snap_a",
        source_path="evidence/records/snap_a.json",
        is_direct=True,
        details={"message_text": "[REDACTED]"},
    )
    obs_exposed = EvidenceObservation(
        resource_id="support_404",
        observed_state=ResourceState.PRESENT,
        timestamp=obs_time,
        evidence_id="evidence_snap_b",
        source_path="evidence/records/snap_b.json",
        is_direct=True,
        details={"message_text": "Exposed email: test@example.com"},
    )

    recon = reconstruct_resource_state(
        resource_id="support_404",
        audit_at=cutoff,
        direct_observations=[obs_redacted, obs_exposed],
        activity_events=[],
    )
    assert recon.state == ResourceState.UNKNOWN
    assert recon.has_conflict is True

    assess = assess_resource_policy(recon, dataset.deletion_rules)
    assert assess.policy_satisfied is False

    decision = validate_case_completion(
        case_id="case_test_404",
        is_non_deletion=False,
        policy_assessments={"support_404": assess},
    )
    assert decision.is_complete is False
    assert decision.deletion_status == "INCOMPLETE"
    assert IncompleteReasonCode.UNKNOWN_RESOURCE_STATE.value in decision.reasons_incomplete
