"""code/tests/test_resource_link.py

Tests for subject-to-resource activity linkage.
Uses small hand-built fixtures only (no real dataset dependency).
"""

from datetime import datetime
import os
import sys
import pytest

# Ensure repository root is on sys.path
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

# Standard library module 'code' conflict resolution
if "code" in sys.modules and not hasattr(sys.modules["code"], "src"):
    del sys.modules["code"]

try:
    from code.src.models import SourceRef, SystemActivity
    from code.src.loader import Dataset, LoaderReport
    from code.src.identity import Cluster, IdentifierNode
    from code.src.resource_link import link_cluster_resources, link_all_clusters, CandidateResource
except ImportError:
    from src.models import SourceRef, SystemActivity
    from src.loader import Dataset, LoaderReport
    from src.identity import Cluster, IdentifierNode
    from src.resource_link import link_cluster_resources, link_all_clusters, CandidateResource


def _build_dummy_dataset(activities):
    """Helper to construct a minimal Dataset fixture."""
    return Dataset(
        data_dir="./dummy",
        deletion_requests=[],
        sample_deletion_requests=[],
        sample_output=[],
        user_identities=[],
        user_audit_log=[],
        system_activity=activities,
        deletion_rules=[],
        evidence_files=[],
        report=LoaderReport(),
    )


def test_handbuilt_fixture_two_matching_and_one_unrelated():
    """
    Hand-built fixture: one subject with two activity rows under the same user_id
    and one unrelated row. Expect two candidates, correct reason codes, and no candidate
    for the unrelated row.
    """
    cluster = Cluster(case_id="case_test_01")
    node_u = IdentifierNode(
        kind="user_id",
        value_raw="user_999",
        value_norm="user_999",
        role="current",
        source=[SourceRef("user_identities.csv", 2)],
    )
    cluster.add_node(node_u)

    act1 = SystemActivity(
        activity_id="act_01",
        event_time_raw="2026-08-01T10:00:00Z",
        event_time=datetime.fromisoformat("2026-08-01T10:00:00+00:00"),
        event_type="DELETE_RECORD",
        source_system="deletion_worker",
        target_system="account_service",
        resource_id="account_999",
        reported_result="SUCCESS",
        details="Deletion worker processed account_999 for user_999.",
        source=SourceRef("system_activity.csv", 2),
    )
    act2 = SystemActivity(
        activity_id="act_02",
        event_time_raw="2026-08-01T11:00:00Z",
        event_time=datetime.fromisoformat("2026-08-01T11:00:00+00:00"),
        event_type="INDEX_RECORD",
        source_system="account_service",
        target_system="search_service",
        resource_id="search_999",
        reported_result="SUCCESS",
        details="Search refresh cataloged search_999 for user_999.",
        source=SourceRef("system_activity.csv", 3),
    )
    act3_unrelated = SystemActivity(
        activity_id="act_03",
        event_time_raw="2026-08-01T12:00:00Z",
        event_time=datetime.fromisoformat("2026-08-01T12:00:00+00:00"),
        event_type="DELETE_RECORD",
        source_system="deletion_worker",
        target_system="account_service",
        resource_id="account_888",
        reported_result="SUCCESS",
        details="Processed account_888 for unrelated user_888.",
        source=SourceRef("system_activity.csv", 4),
    )

    dataset = _build_dummy_dataset([act1, act2, act3_unrelated])
    candidates = link_cluster_resources(cluster, dataset)

    assert len(candidates) == 2
    c_rids = [c.resource_id for c in candidates]
    assert "account_999" in c_rids
    assert "search_999" in c_rids
    assert "account_888" not in c_rids

    for c in candidates:
        assert c.reason_code == "SUBJECT_USER_ID_MATCH"
        assert c.strength == "CONFIRMED"
        assert c.source.file == "system_activity.csv"


def test_determinism_and_ordering():
    """Asserts that running the linker repeatedly yields identical candidates and deterministic sorting."""
    cluster = Cluster(case_id="case_det_01")
    cluster.add_node(
        IdentifierNode(
            kind="user_id",
            value_raw="user_777",
            value_norm="user_777",
            role="current",
            source=[SourceRef("user_identities.csv", 10)],
        )
    )

    # Out of order timestamps
    act_late = SystemActivity(
        activity_id="act_late",
        event_time_raw="2026-09-02T12:00:00Z",
        event_time=datetime.fromisoformat("2026-09-02T12:00:00+00:00"),
        event_type="DELETE_RECORD",
        source_system="worker",
        target_system="account_service",
        resource_id="res_late",
        reported_result="SUCCESS",
        details="User user_777 late event",
        source=SourceRef("system_activity.csv", 100),
    )
    act_early = SystemActivity(
        activity_id="act_early",
        event_time_raw="2026-09-01T10:00:00Z",
        event_time=datetime.fromisoformat("2026-09-01T10:00:00+00:00"),
        event_type="INDEX_RECORD",
        source_system="worker",
        target_system="search_service",
        resource_id="res_early",
        reported_result="SUCCESS",
        details="User user_777 early event",
        source=SourceRef("system_activity.csv", 50),
    )

    dataset = _build_dummy_dataset([act_late, act_early])

    run1 = link_cluster_resources(cluster, dataset)
    run2 = link_cluster_resources(cluster, dataset)

    assert run1 == run2
    assert [c.resource_id for c in run1] == ["res_early", "res_late"]


def test_every_candidate_has_reason_code_and_sourceref():
    """Asserts every candidate has a non-empty reason code, valid strength, and valid SourceRef."""
    cluster = Cluster(case_id="case_inv_01")
    cluster.add_node(
        IdentifierNode(
            kind="email",
            value_raw="person@domain.com",
            value_norm="person@domain.com",
            role="current",
            source=[SourceRef("user_identities.csv", 5)],
        )
    )

    act_email = SystemActivity(
        activity_id="act_email_01",
        event_time_raw="2026-08-10T10:00:00Z",
        event_time=datetime.fromisoformat("2026-08-10T10:00:00+00:00"),
        event_type="LINK_RESOURCE_IDENTITY",
        source_system="catalog",
        target_system="identity",
        resource_id="res_email_linked",
        reported_result="SUCCESS",
        details="Linked res_email_linked to person@domain.com",
        source=SourceRef("system_activity.csv", 20),
    )

    dataset = _build_dummy_dataset([act_email])
    candidates = link_cluster_resources(cluster, dataset)

    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.reason_code == "SUBJECT_EMAIL_MATCH"
    assert cand.strength == "PROBABLE"  # D3: non-user_id match is PROBABLE
    assert cand.source == SourceRef("system_activity.csv", 20)
    assert cand.source.row_number == 20
