"""code/tests/test_canonical_account_link.py

Regression test suite for Canonical Account ID Linkage (Step L):
1. A supported canonical mapping that resolves a previously unlinked resource.
2. An unrelated account with a similar numeric suffix that must not be linked.
3. A missing snapshot that must not be interpreted as proof of deletion.
4. A supported mapping where the resource remains present and therefore requires remediation.
"""

from datetime import datetime, timezone
import pytest

from code.src.identity import Cluster, IdentifierNode
from code.src.loader import Dataset, LoaderReport
from code.src.models import DeletionRequest, DeletionRule, SourceRef, SystemActivity
from code.src.resource_link import (
    CandidateResource,
    get_canonical_account_id,
    check_canonical_account_corroboration,
    link_cluster_resources,
)
from code.src.evidence_extraction import ExtractedObservation, ObservationConfidence
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
            DeletionRule("rule_01", "USER_PROFILE", "User profile", "DELETE", SourceRef("deletion_rules.csv", 1)),
        ],
        evidence_files=[],
        report=LoaderReport(),
    )


def test_canonical_id_derivation_leading_zeros():
    """Verify derivation preserves leading-zero semantics across widths."""
    assert get_canonical_account_id("user_01") == "account_001"
    assert get_canonical_account_id("user_05") == "account_005"
    assert get_canonical_account_id("user_34") == "account_034"
    assert get_canonical_account_id("user_106") == "account_106"
    assert get_canonical_account_id("user_8741") == "account_8741"
    assert get_canonical_account_id("invalid_id") is None


def test_1_supported_canonical_mapping_resolves_unlinked_resource():
    """1. A supported canonical mapping resolves a previously unlinked resource."""
    cluster = Cluster(case_id="case_test_01")
    cluster.nodes["user_01"] = IdentifierNode("user_id", "user_01", "user_01", SourceRef("test.csv", 1))
    cluster.nodes["amina@example.com"] = IdentifierNode("email", "amina@example.com", "amina@example.com", SourceRef("test.csv", 1))

    act = SystemActivity(
        activity_id="act_3342",
        event_time_raw="2026-08-20T16:41:43Z",
        event_time=datetime(2026, 8, 20, 16, 41, 43, tzinfo=timezone.utc),
        event_type="DELETE_RECORD",
        source_system="deletion_worker",
        target_system="account_service",
        resource_id="account_001",
        reported_result="SUCCESS",
        details="Target resource: account_001",
        source=SourceRef("system_activity.csv", 1),
    )
    dataset = _make_dummy_dataset([act])

    # Direct evidence observation confirms ABSENT at cutoff
    obs = ExtractedObservation(
        source_file="evidence/records/service_export.json",
        file_id="evidence_92",
        evidence_id="evidence_92",
        source_location="profile_lookups:1",
        observation_type="PROFILE_LOOKUP",
        extraction_method="JSON_PARSER",
        confidence=ObservationConfidence.HIGH,
        timestamp=datetime(2026, 8, 20, 17, 0, 0, tzinfo=timezone.utc),
        resource_id="account_001",
        system_id="account_service",
        associated_identifiers={},
        observed_state=ResourceState.ABSENT,
        raw_payload={"status_code": 404},
    )

    is_valid, cand = check_canonical_account_corroboration(
        canonical_rid="account_001",
        cluster=cluster,
        dataset=dataset,
        evidence_observations=[obs],
    )
    assert is_valid is True
    assert cand is not None
    assert cand.resource_id == "account_001"
    assert cand.reason_code == "CANONICAL_ACCOUNT_MATCH"
    assert cand.strength == "CONFIRMED"

    # Full linking pass includes account_001
    cands = link_cluster_resources(cluster, dataset, evidence_observations=[obs])
    assert any(c.resource_id == "account_001" for c in cands)


def test_2_unrelated_account_similar_suffix_rejected():
    """2. An unrelated account with a similar numeric suffix must not be linked."""
    cluster = Cluster(case_id="case_test_248")
    cluster.nodes["user_246"] = IdentifierNode("user_id", "user_246", "user_246", SourceRef("test.csv", 1))
    cluster.nodes["junseo@example.com"] = IdentifierNode("email", "junseo@example.com", "junseo@example.com", SourceRef("test.csv", 1))

    # account_246 exists, but evidence proves it belongs to user_173 (unrelated person)
    unrelated_obs = ExtractedObservation(
        source_file="evidence/records/snapshot.json",
        file_id="evidence_02",
        evidence_id="evidence_02",
        source_location="customer_profiles:1",
        observation_type="DATA_RECORD",
        extraction_method="JSON_PARSER",
        confidence=ObservationConfidence.HIGH,
        timestamp=datetime(2026, 7, 25, 10, 0, 0, tzinfo=timezone.utc),
        resource_id="account_246",
        system_id="account_service",
        associated_identifiers={"user_id": "user_173", "email": "louis@example.com"},
        observed_state=ResourceState.PRESENT,
        raw_payload={"customer_reference": "user_173"},
    )
    dataset = _make_dummy_dataset([])

    is_valid, cand = check_canonical_account_corroboration(
        canonical_rid="account_246",
        cluster=cluster,
        dataset=dataset,
        evidence_observations=[unrelated_obs],
    )
    # Must reject the ungrounded link due to conflicting subject identity
    assert is_valid is False
    assert cand is None


def test_3_missing_snapshot_not_interpreted_as_deletion():
    """3. A missing snapshot that must not be interpreted as proof of deletion."""
    cluster = Cluster(case_id="case_test_36")
    cluster.nodes["user_34"] = IdentifierNode("user_id", "user_34", "user_34", SourceRef("test.csv", 1))

    # Activity claims deletion worker succeeded, but NO post-event evidence snapshot exists
    act = SystemActivity(
        activity_id="act_034",
        event_time_raw="2026-08-10T12:00:00Z",
        event_time=datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc),
        event_type="DELETE_RECORD",
        source_system="deletion_worker",
        target_system="account_service",
        resource_id="account_034",
        reported_result="SUCCESS",
        details="Target resource: account_034",
        source=SourceRef("system_activity.csv", 1),
    )
    dataset = _make_dummy_dataset([act])

    cutoff = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    recon = reconstruct_resource_state(
        resource_id="account_034",
        audit_at=cutoff,
        direct_observations=[],  # Missing snapshot
        activity_events=[act],
    )
    # Must be UNKNOWN because reported_result alone is uncorroborated
    assert recon.state == ResourceState.UNKNOWN
    assert recon.is_uncorroborated_claim is True

    assess = assess_resource_policy(recon, dataset.deletion_rules)
    assert assess.policy_satisfied is False

    decision = validate_case_completion(
        case_id="case_test_36",
        is_non_deletion=False,
        policy_assessments={"account_034": assess},
        identity_cluster=cluster,
    )
    # Must preserve INCOMPLETE
    assert decision.is_complete is False
    assert decision.deletion_status == "INCOMPLETE"
    assert IncompleteReasonCode.UNKNOWN_RESOURCE_STATE.value in decision.reasons_incomplete


def test_4_supported_mapping_resource_remains_present_requires_remediation():
    """4. A supported mapping where the resource remains present requires remediation."""
    cluster = Cluster(case_id="case_test_05")
    cluster.nodes["user_05"] = IdentifierNode("user_id", "user_05", "user_05", SourceRef("test.csv", 1))

    # account_005 corroborated in failover replica, still ACTIVE / PRESENT
    replica_obs = EvidenceObservation(
        resource_id="account_005",
        observed_state=ResourceState.PRESENT,
        timestamp=datetime(2026, 9, 2, 22, 45, 0, tzinfo=timezone.utc),
        evidence_id="evidence_db_05",
        source_path="evidence/databases/replica.sql",
        is_direct=True,
        details={"status": "ACTIVE", "customer_reference": "user_05"},
    )
    dataset = _make_dummy_dataset([])

    cutoff = datetime(2026, 9, 3, 12, 0, 0, tzinfo=timezone.utc)
    recon = reconstruct_resource_state(
        resource_id="account_005",
        audit_at=cutoff,
        direct_observations=[replica_obs],
        activity_events=[],
    )
    assert recon.state == ResourceState.PRESENT

    assess = assess_resource_policy(recon, dataset.deletion_rules)
    assert assess.policy_satisfied is False  # Policy requires DELETE, observed PRESENT

    # Planner must emit REPORT_REMAINING_RECORD and DELETE_RECORD
    plan = plan_case(
        case_id="case_test_05",
        is_non_deletion=False,
        policy_assessments={"account_005": assess},
    )
    ops = [s.operation for s in plan.steps]
    assert "REPORT_REMAINING_RECORD" in ops
    assert "DELETE_RECORD" in ops
    assert "VERIFY_RECORD_ABSENT" in ops
