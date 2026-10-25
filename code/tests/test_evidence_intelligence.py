"""code/tests/test_evidence_intelligence.py

Regression test suite for Step M: Evidence Intelligence & COMPLETE Recovery.
Covers:
1. SQL snapshot direct column parsing and state determination (backup_restore_entries, connector_subscriptions, support_records, security_audit_records).
2. Log record readback result and subject reference parsing (NOT_FOUND -> ABSENT, FOUND -> PRESENT, IDENTIFIABLE -> PRESENT, ACTIVE -> ACTIVE, BLOCKED -> BLOCKED).
3. Negative tests: Ambiguous identity mappings and conflicting identities rejected.
4. Conflicting and stale evidence resolution.
5. Missing snapshots do not imply deletion (absence != deleted).
6. Post-deletion resurrection cannot be overlooked.
"""

import os
import sys
import tempfile
import sqlite3
from datetime import datetime, timezone

import pytest

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if "code" in sys.modules and not hasattr(sys.modules["code"], "src"):
    del sys.modules["code"]

from code.src.evidence_extraction import SqlSnapshotExtractor, LogRecordExtractor, PdfDocumentExtractor
from code.src.state_reconstruction import ResourceState, reconstruct_resource_state, EvidenceObservation
from code.src.rule_engine import assess_resource_policy, DeletionRule
from code.src.completion_validator import validate_case_completion, IncompleteReasonCode
from code.src.resurrection_detector import (
    TemporalFlowGraph,
    detect_case_resurrection_risks,
    FlowStatus,
    RiskCategory,
)
from code.src.models import SourceRef, SystemActivity
from code.src.identity import Cluster, IdentifierNode


def test_sql_snapshot_direct_columns_and_state():
    """Verify SqlSnapshotExtractor parses alternative column names and determines table-specific states."""
    sql = """
    CREATE TABLE backup_restore_entries (
        resource_id TEXT, customer_email TEXT, customer_reference TEXT, restore_allowed INTEGER, updated_at TEXT
    );
    INSERT INTO backup_restore_entries VALUES ('backup_001', 'user@example.com', 'user_100', 0, '2026-06-01T10:00:00Z');
    INSERT INTO backup_restore_entries VALUES ('backup_002', 'user2@example.com', 'user_101', 1, '2026-06-01T10:00:00Z');

    CREATE TABLE connector_subscriptions (
        resource_id TEXT, customer_email TEXT, customer_reference TEXT, enabled INTEGER, updated_at TEXT
    );
    INSERT INTO connector_subscriptions VALUES ('data_flow_001', 'user@example.com', 'user_100', 0, '2026-06-01T10:00:00Z');
    INSERT INTO connector_subscriptions VALUES ('data_flow_002', 'user2@example.com', 'user_101', 1, '2026-06-01T10:00:00Z');

    CREATE TABLE security_audit_records (
        resource_id TEXT, subject_reference TEXT, event_code TEXT, retention_until TEXT, updated_at TEXT
    );
    INSERT INTO security_audit_records VALUES ('audit_record_001', 'user_100', 'ACCOUNT_DELETED', '2031-12-31T23:59:59Z', '2026-06-01T10:00:00Z');

    CREATE TABLE support_records (
        resource_id TEXT, requester_email TEXT, requester_phone TEXT, requester_name TEXT, message_excerpt TEXT, updated_at TEXT
    );
    INSERT INTO support_records VALUES ('support_001', NULL, NULL, NULL, '[REDACTED]', '2026-06-01T10:00:00Z');
    INSERT INTO support_records VALUES ('support_002', 'exposed@example.com', '+1234567890', 'Exposed Name', 'Please help me', '2026-06-01T10:00:00Z');
    """
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as f:
        f.write(sql)
        f_path = f.name

    try:
        obs = SqlSnapshotExtractor.extract(f_path, "evidence_test")
        obs_by_rid = {o.resource_id: o for o in obs}

        # Backup entries
        assert obs_by_rid["backup_001"].observed_state == ResourceState.BLOCKED
        assert obs_by_rid["backup_001"].associated_identifiers["email"] == "user@example.com"
        assert obs_by_rid["backup_001"].associated_identifiers["user_id"] == "user_100"

        assert obs_by_rid["backup_002"].observed_state == ResourceState.ACTIVE

        # Connector entries
        assert obs_by_rid["data_flow_001"].observed_state == ResourceState.DISABLED
        assert obs_by_rid["data_flow_002"].observed_state == ResourceState.ACTIVE

        # Security audit entries
        assert obs_by_rid["audit_record_001"].observed_state == ResourceState.PRESENT
        assert obs_by_rid["audit_record_001"].associated_identifiers["user_id"] == "user_100"

        # Support records
        assert obs_by_rid["support_001"].observed_state == ResourceState.REDACTED
        assert obs_by_rid["support_002"].observed_state == ResourceState.PRESENT
    finally:
        os.remove(f_path)


def test_log_record_result_and_subject_reference():
    """Verify LogRecordExtractor parses subject_reference, match_key, and result outcomes."""
    log_text = """2026-06-01T12:00:00Z [INFO] [account_service] [tr-100] profile_readback: resource_id="account_100" subject_reference="test@example.com" result="NOT_FOUND"
2026-06-01T12:00:01Z [INFO] [account_service] [tr-101] profile_readback: resource_id="account_101" subject_ref="user_101" result="FOUND"
2026-06-01T12:00:02Z [INFO] [analytics_platform] [tr-102] analytics_check: resource_id="analytics_100" match_key="test@example.com" result="IDENTIFIABLE"
2026-06-01T12:00:03Z [INFO] [backup_service] [tr-103] backup_check: resource_id="backup_100" subject_reference="test@example.com" result="ACTIVE"
"""
    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
        f.write(log_text)
        f_path = f.name

    try:
        obs = LogRecordExtractor.extract(f_path, "evidence_log_test")
        obs_by_rid = {o.resource_id: o for o in obs}

        assert obs_by_rid["account_100"].observed_state == ResourceState.ABSENT
        assert obs_by_rid["account_100"].associated_identifiers["email"] == "test@example.com"

        assert obs_by_rid["account_101"].observed_state == ResourceState.PRESENT
        assert obs_by_rid["account_101"].associated_identifiers["user_id"] == "user_101"

        assert obs_by_rid["analytics_100"].observed_state == ResourceState.PRESENT

        assert obs_by_rid["backup_100"].observed_state == ResourceState.ACTIVE
    finally:
        os.remove(f_path)


def test_negative_ambiguous_identity_mapping_rejected():
    """Verify ambiguous or uncorroborated identity mapping causes fail-closed INCOMPLETE."""
    from code.src.identity import Conflict
    cluster = Cluster(
        case_id="case_conflict_test",
        nodes={
            ("email", "test@example.com"): IdentifierNode(kind="email", value_raw="test@example.com", value_norm="test@example.com", role="current"),
            ("user_id", "user_999"): IdentifierNode(kind="user_id", value_raw="user_999", value_norm="user_999", role="current"),
        },
        conflicts=[Conflict("EMAIL_CONFLICT", "Conflicting owner", [], SourceRef("test", 1))],
    )

    decision = validate_case_completion(
        case_id="case_conflict_test",
        is_non_deletion=False,
        policy_assessments={},
        identity_cluster=cluster,
    )
    assert not decision.is_complete
    assert IncompleteReasonCode.IDENTITY_CONFLICT.value in decision.reasons_incomplete


def test_conflicting_and_stale_evidence():
    """Verify conflicting evidence observations resolve to UNKNOWN and fail completion."""
    audit_dt = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    ev_time = datetime(2026, 5, 20, 10, 0, 0, tzinfo=timezone.utc)

    # Conflicting observations at the same timestamp
    obs_present = EvidenceObservation(
        resource_id="account_999",
        observed_state=ResourceState.PRESENT,
        timestamp=ev_time,
        evidence_id="ev_1",
        source_path="evidence/records/snap1.json",
        is_direct=True,
    )
    obs_absent = EvidenceObservation(
        resource_id="account_999",
        observed_state=ResourceState.ABSENT,
        timestamp=ev_time,
        evidence_id="ev_2",
        source_path="evidence/records/snap2.json",
        is_direct=True,
    )

    recon = reconstruct_resource_state(
        resource_id="account_999",
        audit_at=audit_dt,
        direct_observations=[obs_present, obs_absent],
    )
    assert recon.state == ResourceState.UNKNOWN
    assert recon.has_conflict is True

    rule = DeletionRule(
        rule_id="r1",
        data_category="ACCOUNT_DATA",
        condition="ACCOUNT_DELETION_REQUESTED",
        required_action="DELETE",
        source=SourceRef("deletion_rules.csv", 1),
    )
    assess = assess_resource_policy(recon, [rule])
    assert not assess.policy_satisfied

    decision = validate_case_completion(
        case_id="case_conflict",
        is_non_deletion=False,
        policy_assessments={"account_999": assess},
    )
    assert not decision.is_complete
    assert IncompleteReasonCode.UNKNOWN_RESOURCE_STATE.value in decision.reasons_incomplete


def test_missing_snapshots_do_not_imply_deletion():
    """Verify absence of a record from a snapshot does not infer deletion."""
    audit_dt = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    # No direct observations (missing snapshot)
    recon = reconstruct_resource_state(
        resource_id="account_888",
        audit_at=audit_dt,
        direct_observations=[],
        activity_events=[],
    )
    assert recon.state == ResourceState.UNKNOWN

    rule = DeletionRule(
        rule_id="r1",
        data_category="ACCOUNT_DATA",
        condition="ACCOUNT_DELETION_REQUESTED",
        required_action="DELETE",
        source=SourceRef("deletion_rules.csv", 1),
    )
    assess = assess_resource_policy(recon, [rule])
    assert not assess.policy_satisfied


def test_post_deletion_resurrection_not_overlooked():
    """Verify active sync or unblocked restore after deletion retains INCOMPLETE."""
    from code.src.resurrection_detector import FlowEdge
    audit_dt = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    graph = TemporalFlowGraph()
    # Add an active sync edge
    graph.add_edge(
        FlowEdge(
            edge_id="edge_1",
            source_system="integration_service",
            target_system="analytics_platform",
            resource_id="data_flow_001",
            event_type="CHECK_DATA_FLOW",
            timestamp=datetime(2026, 5, 25, tzinfo=timezone.utc),
            status=FlowStatus.ACTIVE,
            is_direct_observation=True,
            provenance_evidence_id="activity_sync_1",
            source_path="system_activity.csv",
        )
    )

    risks = detect_case_resurrection_risks(
        case_id="case_resurrect_test",
        audit_at=audit_dt,
        linked_resource_ids={"data_flow_001"},
        graph=graph,
    )

    # Even if resource is observed absent, active flow retains INCOMPLETE
    assess = assess_resource_policy(
        reconstruct_resource_state("data_flow_001", audit_dt, direct_observations=[
            EvidenceObservation("data_flow_001", ResourceState.ACTIVE, datetime(2026, 5, 20, tzinfo=timezone.utc), "ev_1", "evidence/records/snap1.json", True)
        ]),
        [DeletionRule("r1", "CONNECTOR_CONFIGURATION", "ACCOUNT_DELETION_REQUESTED", "DISABLE", SourceRef("deletion_rules.csv", 1))]
    )

    decision = validate_case_completion(
        case_id="case_resurrect_test",
        is_non_deletion=False,
        policy_assessments={"data_flow_001": assess},
        flow_risks=risks,
    )
    assert not decision.is_complete
    assert IncompleteReasonCode.ACTIVE_DATA_FLOW.value in decision.reasons_incomplete
