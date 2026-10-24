"""code/tests/test_resurrection_detector.py

Unit tests for Resurrection and Restore-Risk Detector (Step G).

Tests cover:
1. Active sync from a surviving source to a deleted target.
2. Disabled flow (safe state).
3. Blocked restore (safe state).
4. Logged restore attempt without corroboration (UNCORROBORATED_CLAIM).
5. Events before, at, and after audit_at cutoff (temporal boundaries).
6. Multi-hop source-to-target paths in TemporalFlowGraph.
7. Unrelated system activity not attributed to request.
8. Deterministic repeated execution.
"""

from datetime import datetime, timezone
import pytest

from code.src.models import SourceRef, SystemActivity
from code.src.state_reconstruction import EvidenceObservation, ResourceState
from code.src.resurrection_detector import (
    FlowEdge,
    FlowStatus,
    ResurrectionRiskFinding,
    RiskCategory,
    TemporalFlowGraph,
    TimeRelation,
    build_temporal_flow_graph,
    detect_case_resurrection_risks,
    determine_time_relation,
)


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


# 1. Active sync from a surviving source to a deleted target
def test_active_sync_from_surviving_source_to_deleted_target():
    audit_at = _dt("2026-08-15T12:00:00Z")
    case_id = "case_sync_test"
    dummy_source = SourceRef("system_activity.csv", 10)

    # Surviving source profile syncing to search_service
    act_sync = SystemActivity(
        activity_id="act_sync_01",
        event_time_raw="2026-08-10T10:00:00Z",
        event_time=_dt("2026-08-10T10:00:00Z"),
        event_type="SYNC_RECORD",
        source_system="account_service",
        target_system="search_service",
        resource_id="account_10",
        reported_result="SUCCESS",
        details="Customer profile synchronization processed search_55.",
        source=dummy_source,
    )

    graph = build_temporal_flow_graph([act_sync])
    findings = detect_case_resurrection_risks(
        case_id=case_id,
        audit_at=audit_at,
        linked_resource_ids={"account_10"},
        graph=graph,
    )

    assert len(findings) == 1
    f = findings[0]
    assert f.risk_category == RiskCategory.SYNC_REPLICATION_RISK
    assert f.implicated_resource == "account_10"
    assert f.source_system == "account_service"
    assert f.target_system == "search_service"
    assert f.flow_status == FlowStatus.ACTIVE
    assert f.time_relation == TimeRelation.PRIOR_TO_AUDIT


# 2. Disabled flow (safe state)
def test_disabled_flow():
    audit_at = _dt("2026-08-15T12:00:00Z")
    case_id = "case_disabled_test"
    dummy_source = SourceRef("system_activity.csv", 12)

    # Flow was checked active on Aug 1, but disabled on Aug 10
    act_check = SystemActivity(
        activity_id="act_fl_01",
        event_time_raw="2026-08-01T10:00:00Z",
        event_time=_dt("2026-08-01T10:00:00Z"),
        event_type="CHECK_DATA_FLOW",
        source_system="deletion_worker",
        target_system="integration_service",
        resource_id="data_flow_20",
        reported_result="SUCCESS",
        details="Connector check confirmed enabled.",
        source=dummy_source,
    )
    act_disable = SystemActivity(
        activity_id="act_fl_02",
        event_time_raw="2026-08-10T10:00:00Z",
        event_time=_dt("2026-08-10T10:00:00Z"),
        event_type="DISABLE_DATA_FLOW",
        source_system="deletion_worker",
        target_system="integration_service",
        resource_id="data_flow_20",
        reported_result="SUCCESS",
        details="Policy action completed for data_flow_20.",
        source=dummy_source,
    )

    graph = build_temporal_flow_graph([act_check, act_disable])
    findings = detect_case_resurrection_risks(
        case_id=case_id,
        audit_at=audit_at,
        linked_resource_ids={"data_flow_20"},
        graph=graph,
    )

    # Disabled flow must NOT emit an active risk finding
    active_risks = [f for f in findings if f.risk_category == RiskCategory.ACTIVE_DATA_FLOW]
    assert len(active_risks) == 0


# 3. Blocked restore (safe state)
def test_blocked_restore():
    audit_at = _dt("2026-08-15T12:00:00Z")
    case_id = "case_blocked_test"
    dummy_source = SourceRef("system_activity.csv", 15)

    act_block = SystemActivity(
        activity_id="act_bk_01",
        event_time_raw="2026-08-05T10:00:00Z",
        event_time=_dt("2026-08-05T10:00:00Z"),
        event_type="BLOCK_RESTORE",
        source_system="deletion_worker",
        target_system="backup_service",
        resource_id="backup_30",
        reported_result="SUCCESS",
        details="Policy action completed for backup_30.",
        source=dummy_source,
    )

    graph = build_temporal_flow_graph([act_block])
    findings = detect_case_resurrection_risks(
        case_id=case_id,
        audit_at=audit_at,
        linked_resource_ids={"backup_30"},
        graph=graph,
    )

    active_restores = [f for f in findings if f.risk_category == RiskCategory.RESTORE_RISK]
    assert len(active_restores) == 0


# 4. Logged restore attempt without corroboration
def test_logged_restore_attempt_without_corroboration():
    audit_at = _dt("2026-08-15T12:00:00Z")
    case_id = "case_uncorroborated_test"
    dummy_source = SourceRef("system_activity.csv", 20)

    # Logged RESTORE_BACKUP without repopulated resource details
    act_unverified = SystemActivity(
        activity_id="act_res_01",
        event_time_raw="2026-08-10T10:00:00Z",
        event_time=_dt("2026-08-10T10:00:00Z"),
        event_type="RESTORE_BACKUP",
        source_system="backup_service",
        target_system="search_service",
        resource_id="backup_40",
        reported_result="SUCCESS",
        details="Restore routine invoked.",
        source=dummy_source,
    )

    graph = build_temporal_flow_graph([act_unverified])
    findings = detect_case_resurrection_risks(
        case_id=case_id,
        audit_at=audit_at,
        linked_resource_ids={"backup_40"},
        graph=graph,
    )

    assert len(findings) == 1
    f = findings[0]
    assert f.confidence == "UNCORROBORATED_CLAIM"
    assert len(f.unresolved_gaps) > 0
    assert "lacked corroborating" in f.unresolved_gaps[0]


# 5. Events before, at, and after audit_at
def test_events_before_at_after_audit_at():
    audit_at = _dt("2026-08-15T12:00:00Z")

    # Time classification
    assert determine_time_relation(_dt("2026-08-14T00:00:00Z"), audit_at) == TimeRelation.PRIOR_TO_AUDIT
    assert determine_time_relation(_dt("2026-08-15T12:00:00Z"), audit_at) == TimeRelation.AT_AUDIT
    assert determine_time_relation(_dt("2026-08-16T00:00:00Z"), audit_at) == TimeRelation.POST_AUDIT

    case_id = "case_temporal_test"
    dummy_source = SourceRef("system_activity.csv", 25)

    # Restore event occurred AFTER audit cutoff (post-audit resurrection)
    act_post_restore = SystemActivity(
        activity_id="act_post_01",
        event_time_raw="2026-08-20T10:00:00Z",
        event_time=_dt("2026-08-20T10:00:00Z"),
        event_type="RESTORE_BACKUP",
        source_system="backup_service",
        target_system="search_service",
        resource_id="backup_50",
        reported_result="SUCCESS",
        details="Restore job repopulated downstream resource search_999.",
        source=dummy_source,
    )

    graph = build_temporal_flow_graph([act_post_restore])
    findings = detect_case_resurrection_risks(
        case_id=case_id,
        audit_at=audit_at,
        linked_resource_ids={"backup_50"},
        graph=graph,
    )

    assert len(findings) == 1
    f = findings[0]
    assert f.time_relation == TimeRelation.POST_AUDIT
    assert f.is_post_audit_resurrection is True
    assert "POST-AUDIT RESURRECTION" in f.reason


# 6. Multi-hop source-to-target paths in TemporalFlowGraph
def test_multi_hop_source_to_target_paths():
    graph = TemporalFlowGraph()
    # Hop 1: account_service -> integration_service
    edge1 = FlowEdge(
        edge_id="e1",
        source_system="account_service",
        target_system="integration_service",
        resource_id="account_01",
        event_type="CONNECTOR_LINK",
        timestamp=_dt("2026-08-01T00:00:00Z"),
        status=FlowStatus.ACTIVE,
        is_direct_observation=True,
        provenance_evidence_id="ev_1",
        source_path="snap.json",
    )
    # Hop 2: integration_service -> search_service
    edge2 = FlowEdge(
        edge_id="e2",
        source_system="integration_service",
        target_system="search_service",
        resource_id="data_flow_01",
        event_type="SYNC_RECORD",
        timestamp=_dt("2026-08-02T00:00:00Z"),
        status=FlowStatus.ACTIVE,
        is_direct_observation=True,
        provenance_evidence_id="ev_2",
        source_path="snap.json",
    )
    graph.add_edge(edge1)
    graph.add_edge(edge2)

    paths = graph.find_multi_hop_paths("account_service", "search_service", max_hops=3)
    assert len(paths) >= 1
    # Check that the two-hop path is found
    path = paths[0]
    assert len(path) == 2
    assert path[0].source_system == "account_service"
    assert path[0].target_system == "integration_service"
    assert path[1].source_system == "integration_service"
    assert path[1].target_system == "search_service"


# 7. Unrelated system activity not attributed to request
def test_unrelated_system_activity_not_attributed():
    audit_at = _dt("2026-08-15T12:00:00Z")
    case_id = "case_isolation_test"
    dummy_source = SourceRef("system_activity.csv", 30)

    # Activity for UNRELATED resource data_flow_unrelated
    act_unrelated = SystemActivity(
        activity_id="act_unrelated_999",
        event_time_raw="2026-08-10T10:00:00Z",
        event_time=_dt("2026-08-10T10:00:00Z"),
        event_type="CHECK_DATA_FLOW",
        source_system="deletion_worker",
        target_system="integration_service",
        resource_id="data_flow_unrelated",
        reported_result="SUCCESS",
        details="Connector check confirmed enabled.",
        source=dummy_source,
    )

    graph = build_temporal_flow_graph([act_unrelated])
    # The case is linked only to data_flow_related
    findings = detect_case_resurrection_risks(
        case_id=case_id,
        audit_at=audit_at,
        linked_resource_ids={"data_flow_related"},
        graph=graph,
    )

    # Unrelated activity MUST NOT produce findings for this case
    assert len(findings) == 0


# 8. Deterministic repeated execution
def test_deterministic_repeated_execution():
    audit_at = _dt("2026-08-15T12:00:00Z")
    case_id = "case_repeat_test"
    dummy_source = SourceRef("system_activity.csv", 40)

    act = SystemActivity(
        activity_id="act_rep_01",
        event_time_raw="2026-08-10T10:00:00Z",
        event_time=_dt("2026-08-10T10:00:00Z"),
        event_type="CHECK_DATA_FLOW",
        source_system="deletion_worker",
        target_system="integration_service",
        resource_id="data_flow_77",
        reported_result="SUCCESS",
        details="Connector check confirmed enabled.",
        source=dummy_source,
    )

    graph1 = build_temporal_flow_graph([act])
    res1 = detect_case_resurrection_risks(case_id, audit_at, {"data_flow_77"}, graph1)

    graph2 = build_temporal_flow_graph([act])
    res2 = detect_case_resurrection_risks(case_id, audit_at, {"data_flow_77"}, graph2)

    assert len(res1) == len(res2)
    assert res1[0] == res2[0]
