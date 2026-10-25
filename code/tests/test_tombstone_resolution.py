"""
Regression tests for ACCOUNT_TOMBSTONE Resolution & Safe Integration under Step V.
"""

from datetime import datetime, timezone
import pytest

from code.src.identity import Cluster, IdentifierNode
from code.src.models import SourceRef, SystemActivity
from code.src.rule_engine import (
    PolicyAssessment,
    apply_account_tombstone_resolution,
)
from code.src.state_reconstruction import (
    EvidenceObservation,
    ReconstructedState,
    ResourceState,
)


def _make_cluster(user_id: str) -> Cluster:
    c = Cluster(case_id="case_test")
    node = IdentifierNode(kind="user_id", value_raw=user_id, value_norm=user_id, role="current")
    c.add_node(node)
    return c


def _make_recon(rid: str, state: ResourceState, ts: datetime, details: dict = None) -> ReconstructedState:
    return ReconstructedState(
        resource_id=rid,
        state=state,
        provenance_evidence_id="evidence_51",
        source_path="evidence.json",
        timestamp=ts,
        is_direct=True,
        rationale="Test recon",
        raw_details=details or {},
    )


def _make_act(act_id: str, rid: str, dt: datetime, event_type: str = "UPDATE_RECORD") -> SystemActivity:
    return SystemActivity(
        activity_id=act_id,
        event_time_raw=dt.isoformat(),
        event_time=dt,
        event_type=event_type,
        source_system="profile_service",
        target_system="account_service",
        resource_id=rid,
        reported_result="SUCCESS",
        details="{}",
        source=SourceRef(file="system_activity.csv", row_number=1),
    )


def test_compliant_tombstone_resolves_primary_account():
    """Verify compliant tombstone safely establishes associated primary account as ABSENT."""
    cluster = _make_cluster("user_541")
    tomb_dt = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
    old_act_dt = datetime(2026, 1, 26, 13, 5, tzinfo=timezone.utc)

    # Tombstone is compliant: redacted, direct PII removed, policy satisfied
    t_assess = PolicyAssessment(
        resource_id="tombstone_440",
        system_id="identity_service",
        data_category="ACCOUNT_TOMBSTONE",
        applicable_rule_id="RULE-TOMB-001",
        required_action="REDACT",
        observed_state=ResourceState.REDACTED,
        policy_satisfied=True,
        rationale="Account tombstone satisfies policy",
        supporting_evidence_ids=["evidence_51"],
        is_tombstone=True,
        tombstone_direct_pii_removed=True,
        tombstone_internal_id_preserved=True,
    )
    t_recon = _make_recon(
        "tombstone_440",
        ResourceState.REDACTED,
        tomb_dt,
        {"subject_reference": "user_541", "account_status": "DELETED"},
    )

    # Primary account had an old activity event
    a_assess = PolicyAssessment(
        resource_id="account_541",
        system_id="account_service",
        data_category="ACCOUNT",
        applicable_rule_id="RULE-DEL-001",
        required_action="DELETE",
        observed_state=ResourceState.PRESENT,
        policy_satisfied=False,
        rationale="Activity event UPDATE_RECORD confirms present",
        supporting_evidence_ids=["activity_303"],
    )
    a_recon = _make_recon("account_541", ResourceState.PRESENT, old_act_dt)

    policy_assessments = {"account_541": a_assess, "tombstone_440": t_assess}
    reconstructed_states = {"account_541": a_recon, "tombstone_440": t_recon}
    activity_by_res = {
        "account_541": [_make_act("activity_303", "account_541", old_act_dt)]
    }
    obs_by_res = {}
    res_ev_map = {"account_541": {"activity_303"}, "tombstone_440": {"evidence_51"}}

    apply_account_tombstone_resolution(
        policy_assessments=policy_assessments,
        reconstructed_states=reconstructed_states,
        activity_by_res=activity_by_res,
        obs_by_res=obs_by_res,
        cluster=cluster,
        resource_evidence_map=res_ev_map,
    )

    # Account should now be ABSENT, policy satisfied, citing evidence_51
    updated_a = policy_assessments["account_541"]
    assert updated_a.observed_state == ResourceState.ABSENT
    assert updated_a.policy_satisfied is True
    assert updated_a.supporting_evidence_ids == ["evidence_51"]
    assert "evidence_51" in res_ev_map["account_541"]


def test_noncompliant_tombstone_with_exposed_pii_rejected():
    """Verify noncompliant tombstone with exposed PII (like tombstone_9178) does NOT resolve account."""
    cluster = _make_cluster("user_542")
    tomb_dt = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
    old_act_dt = datetime(2026, 1, 26, 13, 5, tzinfo=timezone.utc)

    # Noncompliant tombstone: exposed PII
    t_assess = PolicyAssessment(
        resource_id="tombstone_9178",
        system_id="identity_service",
        data_category="ACCOUNT_TOMBSTONE",
        applicable_rule_id="RULE-TOMB-001",
        required_action="REDACT",
        observed_state=ResourceState.PRESENT,
        policy_satisfied=False,
        rationale="Account tombstone violates policy: contains exposed direct identifiers",
        supporting_evidence_ids=["evidence_51"],
        is_tombstone=True,
        tombstone_direct_pii_removed=False,  # Direct PII exposed!
        tombstone_internal_id_preserved=True,
    )
    t_recon = _make_recon(
        "tombstone_9178",
        ResourceState.PRESENT,
        tomb_dt,
        {"subject_reference": "user_542", "name": "Kofi Addo", "account_status": "DELETED"},
    )

    a_assess = PolicyAssessment(
        resource_id="account_542",
        system_id="account_service",
        data_category="ACCOUNT",
        applicable_rule_id="RULE-DEL-001",
        required_action="DELETE",
        observed_state=ResourceState.PRESENT,
        policy_satisfied=False,
        rationale="Activity event confirms present",
        supporting_evidence_ids=["activity_304"],
    )
    a_recon = _make_recon("account_542", ResourceState.PRESENT, old_act_dt)

    policy_assessments = {"account_542": a_assess, "tombstone_9178": t_assess}
    reconstructed_states = {"account_542": a_recon, "tombstone_9178": t_recon}
    activity_by_res = {"account_542": []}
    obs_by_res = {}
    res_ev_map = {"account_542": {"activity_304"}}

    apply_account_tombstone_resolution(
        policy_assessments=policy_assessments,
        reconstructed_states=reconstructed_states,
        activity_by_res=activity_by_res,
        obs_by_res=obs_by_res,
        cluster=cluster,
        resource_evidence_map=res_ev_map,
    )

    # Account remains PRESENT and policy_satisfied is False!
    updated_a = policy_assessments["account_542"]
    assert updated_a.observed_state == ResourceState.PRESENT
    assert updated_a.policy_satisfied is False


def test_post_tombstone_activity_prevents_resolution():
    """Verify post-tombstone activity (e.g. recreation or update after deletion) prevents ABSENT resolution."""
    cluster = _make_cluster("user_541")
    tomb_dt = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
    # Subsequent activity AFTER tombstone
    post_act_dt = datetime(2026, 9, 16, 10, 0, tzinfo=timezone.utc)

    t_assess = PolicyAssessment(
        resource_id="tombstone_440",
        system_id="identity_service",
        data_category="ACCOUNT_TOMBSTONE",
        applicable_rule_id="RULE-TOMB-001",
        required_action="REDACT",
        observed_state=ResourceState.REDACTED,
        policy_satisfied=True,
        rationale="Account tombstone satisfies policy",
        supporting_evidence_ids=["evidence_51"],
        is_tombstone=True,
        tombstone_direct_pii_removed=True,
    )
    t_recon = _make_recon(
        "tombstone_440",
        ResourceState.REDACTED,
        tomb_dt,
        {"subject_reference": "user_541"},
    )

    a_assess = PolicyAssessment(
        resource_id="account_541",
        system_id="account_service",
        data_category="ACCOUNT",
        applicable_rule_id="RULE-DEL-001",
        required_action="DELETE",
        observed_state=ResourceState.PRESENT,
        policy_satisfied=False,
        rationale="Post-tombstone activity",
        supporting_evidence_ids=["activity_999"],
    )
    a_recon = _make_recon("account_541", ResourceState.PRESENT, post_act_dt)

    policy_assessments = {"account_541": a_assess, "tombstone_440": t_assess}
    reconstructed_states = {"account_541": a_recon, "tombstone_440": t_recon}
    activity_by_res = {
        "account_541": [_make_act("activity_999", "account_541", post_act_dt)]
    }
    obs_by_res = {}

    apply_account_tombstone_resolution(
        policy_assessments=policy_assessments,
        reconstructed_states=reconstructed_states,
        activity_by_res=activity_by_res,
        obs_by_res=obs_by_res,
        cluster=cluster,
    )

    # Resolution should be blocked due to post-tombstone activity
    assert policy_assessments["account_541"].observed_state == ResourceState.PRESENT
    assert policy_assessments["account_541"].policy_satisfied is False


def test_post_tombstone_observation_prevents_resolution():
    """Verify post-tombstone direct observation showing account PRESENT blocks resolution."""
    cluster = _make_cluster("user_541")
    tomb_dt = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
    post_obs_dt = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)

    t_assess = PolicyAssessment(
        resource_id="tombstone_440",
        system_id="identity_service",
        data_category="ACCOUNT_TOMBSTONE",
        applicable_rule_id="RULE-TOMB-001",
        required_action="REDACT",
        observed_state=ResourceState.REDACTED,
        policy_satisfied=True,
        rationale="Account tombstone satisfies policy",
        supporting_evidence_ids=["evidence_51"],
        is_tombstone=True,
        tombstone_direct_pii_removed=True,
    )
    t_recon = _make_recon(
        "tombstone_440",
        ResourceState.REDACTED,
        tomb_dt,
        {"subject_reference": "user_541"},
    )

    a_assess = PolicyAssessment(
        resource_id="account_541",
        system_id="account_service",
        data_category="ACCOUNT",
        applicable_rule_id="RULE-DEL-001",
        required_action="DELETE",
        observed_state=ResourceState.PRESENT,
        policy_satisfied=False,
        rationale="Direct observation",
        supporting_evidence_ids=["evidence_99"],
    )
    a_recon = _make_recon("account_541", ResourceState.PRESENT, post_obs_dt)

    policy_assessments = {"account_541": a_assess, "tombstone_440": t_assess}
    reconstructed_states = {"account_541": a_recon, "tombstone_440": t_recon}
    activity_by_res = {"account_541": []}
    obs_by_res = {
        "account_541": [
            EvidenceObservation(
                resource_id="account_541",
                observed_state=ResourceState.PRESENT,
                timestamp=post_obs_dt,
                evidence_id="evidence_99",
                source_path="evidence.json",
                is_direct=True,
            )
        ]
    }

    apply_account_tombstone_resolution(
        policy_assessments=policy_assessments,
        reconstructed_states=reconstructed_states,
        activity_by_res=activity_by_res,
        obs_by_res=obs_by_res,
        cluster=cluster,
    )

    # Blocked due to post-tombstone observation
    assert policy_assessments["account_541"].observed_state == ResourceState.PRESENT
    assert policy_assessments["account_541"].policy_satisfied is False


def test_mismatched_subject_reference_rejected():
    """Verify tombstone belonging to user_999 does not resolve account_541."""
    cluster = _make_cluster("user_541")
    tomb_dt = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
    old_act_dt = datetime(2026, 1, 26, 13, 5, tzinfo=timezone.utc)

    t_assess = PolicyAssessment(
        resource_id="tombstone_999",
        system_id="identity_service",
        data_category="ACCOUNT_TOMBSTONE",
        applicable_rule_id="RULE-TOMB-001",
        required_action="REDACT",
        observed_state=ResourceState.REDACTED,
        policy_satisfied=True,
        rationale="Account tombstone satisfies policy",
        supporting_evidence_ids=["evidence_51"],
        is_tombstone=True,
        tombstone_direct_pii_removed=True,
    )
    t_recon = _make_recon(
        "tombstone_999",
        ResourceState.REDACTED,
        tomb_dt,
        {"subject_reference": "user_999"},
    )

    a_assess = PolicyAssessment(
        resource_id="account_541",
        system_id="account_service",
        data_category="ACCOUNT",
        applicable_rule_id="RULE-DEL-001",
        required_action="DELETE",
        observed_state=ResourceState.PRESENT,
        policy_satisfied=False,
        rationale="Prior state present",
        supporting_evidence_ids=["activity_303"],
    )
    a_recon = _make_recon("account_541", ResourceState.PRESENT, old_act_dt)

    policy_assessments = {"account_541": a_assess, "tombstone_999": t_assess}
    reconstructed_states = {"account_541": a_recon, "tombstone_999": t_recon}
    activity_by_res = {"account_541": []}
    obs_by_res = {}

    apply_account_tombstone_resolution(
        policy_assessments=policy_assessments,
        reconstructed_states=reconstructed_states,
        activity_by_res=activity_by_res,
        obs_by_res=obs_by_res,
        cluster=cluster,
    )

    assert policy_assessments["account_541"].observed_state == ResourceState.PRESENT
    assert policy_assessments["account_541"].policy_satisfied is False
