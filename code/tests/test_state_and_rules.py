"""code/tests/test_state_and_rules.py

Unit tests for State Reconstruction and Deterministic Rule Engine (Step F).

Tests cover:
1. Before/at/after audit_at event handling (temporal isolation).
2. Reported success without corroborating evidence (uncorroborated claims yield UNKNOWN).
3. Conflicting observations yield UNKNOWN.
4. Each treatment category (DELETE, REDACT, RETAIN, ACCOUNT_TOMBSTONE, ANONYMIZE).
5. Tombstone retaining allowed internal user_id while removing prohibited direct identifiers.
6. Missing/ambiguous rule matches (explicit policy gaps).
7. Deterministic repeated results.
"""

from datetime import datetime, timezone
import pytest

from code.src.models import DeletionRule, SourceRef, SystemActivity
from code.src.state_reconstruction import (
    EvidenceObservation,
    ReconstructedState,
    ResourceState,
    reconstruct_resource_state,
)
from code.src.rule_engine import (
    PolicyAssessment,
    assess_resource_policy,
    match_resource_category,
)


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


@pytest.fixture
def sample_deletion_rules():
    """Provides a synthetic rule set matching deletion_rules.csv."""
    dummy_source = SourceRef("deletion_rules.csv", 2)
    return [
        DeletionRule("rule_01", "USER_PROFILE", "Always", "DELETE", dummy_source),
        DeletionRule("rule_02", "SECONDARY_IDENTIFIER", "Always", "DELETE", dummy_source),
        DeletionRule("rule_03", "SEARCH_INDEX_ENTRY", "Always", "DELETE", dummy_source),
        DeletionRule("rule_04", "CACHE_ENTRY", "Always", "DELETE", dummy_source),
        DeletionRule("rule_05", "SUPPORT_MESSAGE", "Shared context retained", "REDACT", dummy_source),
        DeletionRule("rule_06", "SUPPORT_ATTACHMENT", "Subject only", "DELETE", dummy_source),
        DeletionRule("rule_07", "ANALYTICS_PROFILE", "Attributable", "ANONYMIZE", dummy_source),
        DeletionRule("rule_08", "PRODUCT_TELEMETRY", "Attributable", "ANONYMIZE", dummy_source),
        DeletionRule("rule_09", "USER_EXPORT", "Always", "DELETE", dummy_source),
        DeletionRule("rule_10", "MARKETING_PROFILE", "Always", "DELETE", dummy_source),
        DeletionRule("rule_11", "EMAIL_DELIVERY_LOG", "Contains user email", "REDACT", dummy_source),
        DeletionRule("rule_12", "SECURITY_AUDIT_LOG", "Within retention", "RETAIN", dummy_source),
        DeletionRule("rule_13", "LEGAL_HOLD_RECORD", "Active legal hold", "RETAIN", dummy_source),
        DeletionRule("rule_14", "BACKUP_ARCHIVE", "Restore access blocked", "RETAIN", dummy_source),
        DeletionRule("rule_15", "ACCOUNT_TOMBSTONE", "Stable user_id needed", "REDACT", dummy_source),
    ]


# 1. Before/At/After audit_at event handling
def test_before_at_after_audit_at():
    audit_at = _dt("2026-08-15T12:00:00+00:00")
    rid = "account_101"

    # Observation BEFORE audit_at: PRESENT
    obs_before = EvidenceObservation(
        resource_id=rid,
        observed_state=ResourceState.PRESENT,
        timestamp=_dt("2026-08-10T10:00:00+00:00"),
        evidence_id="evidence_01",
        source_path="evidence/records/snap1.json",
        is_direct=True,
    )
    # Observation AFTER audit_at: ABSENT (must NOT affect audit_at state!)
    obs_after = EvidenceObservation(
        resource_id=rid,
        observed_state=ResourceState.ABSENT,
        timestamp=_dt("2026-08-16T10:00:00+00:00"),
        evidence_id="evidence_02",
        source_path="evidence/records/snap2.json",
        is_direct=True,
    )

    state = reconstruct_resource_state(
        resource_id=rid,
        audit_at=audit_at,
        direct_observations=[obs_before, obs_after],
    )
    # Must reflect state at audit_at (PRESENT), ignoring obs_after
    assert state.state == ResourceState.PRESENT
    assert state.provenance_evidence_id == "evidence_01"
    assert state.post_audit_events_count == 1

    # Observation EXACTLY AT audit_at: ABSENT
    obs_exact = EvidenceObservation(
        resource_id=rid,
        observed_state=ResourceState.ABSENT,
        timestamp=_dt("2026-08-15T12:00:00+00:00"),
        evidence_id="evidence_03",
        source_path="evidence/records/snap3.json",
        is_direct=True,
    )
    state_exact = reconstruct_resource_state(
        resource_id=rid,
        audit_at=audit_at,
        direct_observations=[obs_before, obs_exact],
    )
    assert state_exact.state == ResourceState.ABSENT
    assert state_exact.provenance_evidence_id == "evidence_03"


# 2. Reported success without corroborating evidence
def test_reported_success_without_corroboration():
    audit_at = _dt("2026-08-15T12:00:00+00:00")
    rid = "account_202"

    dummy_source = SourceRef("system_activity.csv", 10)
    # Activity claims DELETE_RECORD SUCCESS
    act_claim = SystemActivity(
        activity_id="activity_88",
        event_time_raw="2026-08-12T10:00:00Z",
        event_time=_dt("2026-08-12T10:00:00+00:00"),
        event_type="DELETE_RECORD",
        source_system="account_service",
        target_system="account_service",
        resource_id=rid,
        reported_result="SUCCESS",
        details="Deletion worker reported account_202 deleted.",
        source=dummy_source,
    )

    # Without direct evidence, claim is uncorroborated -> UNKNOWN
    state = reconstruct_resource_state(
        resource_id=rid,
        audit_at=audit_at,
        direct_observations=[],
        activity_events=[act_claim],
    )
    assert state.state == ResourceState.UNKNOWN
    assert state.is_uncorroborated_claim is True
    assert "Uncorroborated" in state.rationale

    # With corroborating direct evidence (operational history shows NOT_FOUND)
    corroborating_obs = EvidenceObservation(
        resource_id=rid,
        observed_state=ResourceState.ABSENT,
        timestamp=_dt("2026-08-13T10:00:00+00:00"),
        evidence_id="evidence_99",
        source_path="evidence/records/history.json",
        is_direct=True,
    )
    state_corroborated = reconstruct_resource_state(
        resource_id=rid,
        audit_at=audit_at,
        direct_observations=[corroborating_obs],
        activity_events=[act_claim],
    )
    assert state_corroborated.state == ResourceState.ABSENT
    assert state_corroborated.is_uncorroborated_claim is False


# 3. Conflicting observations -> UNKNOWN
def test_conflicting_observations_yields_unknown():
    audit_at = _dt("2026-08-15T12:00:00+00:00")
    rid = "search_303"
    t = _dt("2026-08-14T10:00:00+00:00")

    obs1 = EvidenceObservation(
        resource_id=rid,
        observed_state=ResourceState.PRESENT,
        timestamp=t,
        evidence_id="evidence_10",
        source_path="evidence/records/primary.json",
        is_direct=True,
    )
    obs2 = EvidenceObservation(
        resource_id=rid,
        observed_state=ResourceState.ABSENT,
        timestamp=t,
        evidence_id="evidence_11",
        source_path="evidence/records/replica.json",
        is_direct=True,
    )

    state = reconstruct_resource_state(
        resource_id=rid,
        audit_at=audit_at,
        direct_observations=[obs1, obs2],
    )
    assert state.state == ResourceState.UNKNOWN
    assert state.has_conflict is True
    assert "Conflicting" in state.rationale


# 4. Each treatment category (DELETE, REDACT, RETAIN, ACCOUNT_TOMBSTONE, ANONYMIZE)
def test_treatment_categories_compliance(sample_deletion_rules):
    # A. DELETE (USER_PROFILE): satisfied if ABSENT, violated if PRESENT
    del_absent = ReconstructedState(
        resource_id="account_01",
        state=ResourceState.ABSENT,
        provenance_evidence_id="ev_01",
        source_path="snap.json",
        timestamp=_dt("2026-08-01T00:00:00Z"),
        is_direct=True,
        rationale="Record not found",
    )
    p_del_absent = assess_resource_policy(del_absent, sample_deletion_rules)
    assert p_del_absent.policy_satisfied is True
    assert p_del_absent.required_action == "DELETE"

    del_present = ReconstructedState(
        resource_id="account_01",
        state=ResourceState.PRESENT,
        provenance_evidence_id="ev_01",
        source_path="snap.json",
        timestamp=_dt("2026-08-01T00:00:00Z"),
        is_direct=True,
        rationale="Record found",
    )
    p_del_present = assess_resource_policy(del_present, sample_deletion_rules)
    assert p_del_present.policy_satisfied is False

    # B. REDACT (SUPPORT_MESSAGE): satisfied if REDACTED, violated if PRESENT
    red_redacted = ReconstructedState(
        resource_id="support_55",
        state=ResourceState.REDACTED,
        provenance_evidence_id="ev_02",
        source_path="snap.json",
        timestamp=_dt("2026-08-01T00:00:00Z"),
        is_direct=True,
        rationale="PII removed",
    )
    p_red_ok = assess_resource_policy(red_redacted, sample_deletion_rules)
    assert p_red_ok.policy_satisfied is True
    assert p_red_ok.required_action == "REDACT"

    red_present = ReconstructedState(
        resource_id="support_55",
        state=ResourceState.PRESENT,
        provenance_evidence_id="ev_02",
        source_path="snap.json",
        timestamp=_dt("2026-08-01T00:00:00Z"),
        is_direct=True,
        rationale="Contains user email",
    )
    p_red_bad = assess_resource_policy(red_present, sample_deletion_rules)
    assert p_red_bad.policy_satisfied is False

    # C. RETAIN (SECURITY_AUDIT_LOG): satisfied if PRESENT, violated if ABSENT
    ret_present = ReconstructedState(
        resource_id="audit_record_90",
        state=ResourceState.PRESENT,
        provenance_evidence_id="ev_03",
        source_path="snap.json",
        timestamp=_dt("2026-08-01T00:00:00Z"),
        is_direct=True,
        rationale="Audit log present",
    )
    p_ret_ok = assess_resource_policy(ret_present, sample_deletion_rules)
    assert p_ret_ok.policy_satisfied is True
    assert p_ret_ok.required_action == "RETAIN"

    # D. ANONYMIZE (ANALYTICS_PROFILE): satisfied if ANONYMIZED, violated if PRESENT
    anon_ok = ReconstructedState(
        resource_id="analytics_42",
        state=ResourceState.ANONYMIZED,
        provenance_evidence_id="ev_04",
        source_path="snap.json",
        timestamp=_dt("2026-08-01T00:00:00Z"),
        is_direct=True,
        rationale="Unlinked metrics",
    )
    p_anon_ok = assess_resource_policy(anon_ok, sample_deletion_rules)
    assert p_anon_ok.policy_satisfied is True
    assert p_anon_ok.required_action == "ANONYMIZE"

    # E. BACKUP_ARCHIVE (RETAIN with condition 'Restore access can be blocked'):
    # satisfied if BLOCKED, violated if ACTIVE
    backup_blocked = ReconstructedState(
        resource_id="backup_12",
        state=ResourceState.BLOCKED,
        provenance_evidence_id="ev_05",
        source_path="snap.json",
        timestamp=_dt("2026-08-01T00:00:00Z"),
        is_direct=True,
        rationale="Restore access blocked",
    )
    p_bk_ok = assess_resource_policy(backup_blocked, sample_deletion_rules)
    assert p_bk_ok.policy_satisfied is True

    backup_active = ReconstructedState(
        resource_id="backup_12",
        state=ResourceState.ACTIVE,
        provenance_evidence_id="ev_05",
        source_path="snap.json",
        timestamp=_dt("2026-08-01T00:00:00Z"),
        is_direct=True,
        rationale="Restore access allowed",
    )
    p_bk_bad = assess_resource_policy(backup_active, sample_deletion_rules)
    assert p_bk_bad.policy_satisfied is False

    # F. DATA_FLOW: satisfied if DISABLED, violated if ACTIVE
    flow_disabled = ReconstructedState(
        resource_id="data_flow_07",
        state=ResourceState.DISABLED,
        provenance_evidence_id="ev_06",
        source_path="snap.json",
        timestamp=_dt("2026-08-01T00:00:00Z"),
        is_direct=True,
        rationale="Connector disabled",
    )
    p_flow_ok = assess_resource_policy(flow_disabled, sample_deletion_rules)
    assert p_flow_ok.policy_satisfied is True

    flow_active = ReconstructedState(
        resource_id="data_flow_07",
        state=ResourceState.ACTIVE,
        provenance_evidence_id="ev_06",
        source_path="snap.json",
        timestamp=_dt("2026-08-01T00:00:00Z"),
        is_direct=True,
        rationale="Connector enabled",
    )
    p_flow_bad = assess_resource_policy(flow_active, sample_deletion_rules)
    assert p_flow_bad.policy_satisfied is False


# 5. Tombstone retaining allowed internal user_id while removing prohibited direct identifiers
def test_account_tombstone_pii_vs_internal_id(sample_deletion_rules):
    # Compliant tombstone: stable reference preserved, all direct PII is None
    clean_tombstone = ReconstructedState(
        resource_id="tombstone_777",
        state=ResourceState.REDACTED,
        provenance_evidence_id="ev_tomb",
        source_path="evidence/records/tombstone.json",
        timestamp=_dt("2026-08-10T00:00:00Z"),
        is_direct=True,
        rationale="Tombstone record",
        raw_details={
            "resource_id": "tombstone_777",
            "subject_reference": "user_456",
            "name": None,
            "email": None,
            "phone": None,
            "email_hash": None,
            "account_status": "DELETED",
        },
    )
    p_clean = assess_resource_policy(clean_tombstone, sample_deletion_rules)
    assert p_clean.is_tombstone is True
    assert p_clean.tombstone_internal_id_preserved is True
    assert p_clean.tombstone_direct_pii_removed is True
    assert p_clean.policy_satisfied is True

    # Non-compliant tombstone: stable reference preserved, but email and phone still exposed
    exposed_tombstone = ReconstructedState(
        resource_id="tombstone_888",
        state=ResourceState.PRESENT,
        provenance_evidence_id="ev_tomb2",
        source_path="evidence/records/tombstone.json",
        timestamp=_dt("2026-08-10T00:00:00Z"),
        is_direct=True,
        rationale="Tombstone record with exposed PII",
        raw_details={
            "resource_id": "tombstone_888",
            "subject_reference": "user_456",
            "name": "Jane Doe",
            "email": "jane.doe@example.com",
            "phone": "+12025550199",
            "email_hash": "abc123hash",
            "account_status": "DELETED",
        },
    )
    p_exposed = assess_resource_policy(exposed_tombstone, sample_deletion_rules)
    assert p_exposed.is_tombstone is True
    assert p_exposed.tombstone_internal_id_preserved is True
    assert p_exposed.tombstone_direct_pii_removed is False
    assert p_exposed.policy_satisfied is False


# 6. Missing and ambiguous rule matches
def test_missing_and_ambiguous_rules(sample_deletion_rules):
    # Unknown prefix/category
    unknown_res = ReconstructedState(
        resource_id="mysterious_device_001",
        state=ResourceState.PRESENT,
        provenance_evidence_id="ev_unk",
        source_path="custom.json",
        timestamp=_dt("2026-08-01T00:00:00Z"),
        is_direct=True,
        rationale="Found device",
    )
    p_unknown = assess_resource_policy(unknown_res, sample_deletion_rules)
    assert p_unknown.policy_satisfied is False
    assert p_unknown.gap_reason is not None
    assert "No matching category" in p_unknown.gap_reason

    # Known category but empty rule set (missing rule)
    account_no_rules = ReconstructedState(
        resource_id="account_99",
        state=ResourceState.ABSENT,
        provenance_evidence_id="ev_acc",
        source_path="snap.json",
        timestamp=_dt("2026-08-01T00:00:00Z"),
        is_direct=True,
        rationale="Absent",
    )
    p_no_rules = assess_resource_policy(account_no_rules, [])
    assert p_no_rules.policy_satisfied is False
    assert p_no_rules.gap_reason is not None
    assert "No rule found" in p_no_rules.gap_reason


# 7. Deterministic repeated results
def test_deterministic_repeated_results(sample_deletion_rules):
    audit_at = _dt("2026-08-15T12:00:00+00:00")
    rid = "export_404"

    obs = EvidenceObservation(
        resource_id=rid,
        observed_state=ResourceState.PRESENT,
        timestamp=_dt("2026-08-05T00:00:00Z"),
        evidence_id="evidence_exp",
        source_path="evidence/records/exports.json",
        is_direct=True,
    )

    state1 = reconstruct_resource_state(rid, audit_at, direct_observations=[obs])
    assessment1 = assess_resource_policy(state1, sample_deletion_rules)

    state2 = reconstruct_resource_state(rid, audit_at, direct_observations=[obs])
    assessment2 = assess_resource_policy(state2, sample_deletion_rules)

    assert state1 == state2
    assert assessment1 == assessment2


# 8. parse_timestamp_to_utc supports datetime and iso
def test_parse_timestamp_to_utc_supports_datetime_and_iso():
    from code.src.state_reconstruction import parse_timestamp_to_utc
    dt_now = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
    res_dt = parse_timestamp_to_utc(dt_now)
    assert res_dt == dt_now
    assert res_dt.tzinfo == timezone.utc

    res_str = parse_timestamp_to_utc("2026-08-15T12:00:00Z")
    assert res_str == dt_now
    assert parse_timestamp_to_utc(None) is None
