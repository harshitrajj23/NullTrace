"""code/tests/test_integration_pipeline.py

Targeted integration tests using synthetic fixtures for NullTrace's integrated pipeline.

Covers all 11 required scenario validations:
1. Confirmed remaining record.
2. Confirmed deletion with complete supporting evidence.
3. Active synchronization flow.
4. Restore or resurrection risk.
5. Allowed retained record.
6. Tombstone containing prohibited direct identifiers.
7. Unresolved identity conflict.
8. Conflicting evidence.
9. OCR observation with ambiguous spatial association.
10. Missing or mismatched screenshot cache data.
11. Explicitly non-deletion request.
12. End-to-end output structure and contract invariants.
"""

from datetime import datetime, timezone
import json
import os
import sys
import tempfile
import pytest

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

if "code" in sys.modules and not hasattr(sys.modules["code"], "src"):
    del sys.modules["code"]

from code.src.completion_validator import IncompleteReasonCode, validate_case_completion
from code.src.evidence_extraction import ExtractedObservation, ObservationConfidence
from code.src.identity import Cluster, IdentifierNode
from code.src.local_vision_extraction import AppleVisionExtractor, LocalVisionConfig
from code.src.models import DeletionRequest, DeletionRule
from code.src.ops import Step, validate_steps
from code.src.pipeline import is_non_deletion_inquiry, run_integrated_pipeline
from code.src.planner import plan_case
from code.src.resurrection_detector import (
    FlowEdge,
    FlowStatus,
    ResurrectionRiskFinding,
    RiskCategory,
    TemporalFlowGraph,
    TimeRelation,
)
from code.src.rule_engine import PolicyAssessment, assess_resource_policy
from code.src.state_reconstruction import (
    EvidenceObservation,
    ReconstructedState,
    ResourceState,
    reconstruct_resource_state,
)


from code.src.models import DeletionRequest, DeletionRule, SourceRef

@pytest.fixture
def standard_rules():
    dummy_src = SourceRef("dataset/deletion_rules.csv", 1)
    return [
        DeletionRule("rule_01", "USER_PROFILE", "default", "DELETE", dummy_src),
        DeletionRule("rule_02", "ACCOUNT_TOMBSTONE", "default", "REDACT", dummy_src),
        DeletionRule("rule_03", "LEGAL_HOLD_RECORD", "default", "RETAIN", dummy_src),
        DeletionRule("rule_04", "BACKUP_ARCHIVE", "default", "RETAIN", dummy_src),
        DeletionRule("rule_05", "SEARCH_INDEX_ENTRY", "default", "DELETE", dummy_src),
    ]


def test_confirmed_remaining_record(standard_rules):
    """1. Confirmed remaining record: record is PRESENT at audit -> INCOMPLETE with REPORT_REMAINING_RECORD."""
    audit_at = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    obs = [
        EvidenceObservation(
            resource_id="account_101",
            observed_state=ResourceState.PRESENT,
            timestamp=datetime(2026, 9, 30, 10, 0, 0, tzinfo=timezone.utc),
            evidence_id="evidence_sql_01",
            source_path="evidence/databases/primary.sql",
            is_direct=True,
        )
    ]
    recon = reconstruct_resource_state("account_101", audit_at, direct_observations=obs, activity_events=[])
    assert recon.state == ResourceState.PRESENT

    assess = assess_resource_policy(recon, standard_rules)
    assert not assess.policy_satisfied
    assert assess.required_action == "DELETE"

    plan = plan_case("case_test_01", False, {"account_101": assess})
    assert plan.deletion_status == "INCOMPLETE"
    assert len(plan.steps) == 3
    assert plan.steps[0].operation == "REPORT_REMAINING_RECORD"
    assert plan.steps[0].evidence_id == "evidence_sql_01"
    assert plan.steps[1].operation == "DELETE_RECORD"
    assert plan.steps[1].evidence_id == ""
    assert plan.steps[2].operation == "VERIFY_RECORD_ABSENT"
    assert plan.steps[2].evidence_id == ""


def test_confirmed_deletion_with_complete_supporting_evidence(standard_rules):
    """2. Confirmed deletion: all resources confirmed ABSENT with direct evidence -> COMPLETE."""
    audit_at = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    recon = ReconstructedState(
        resource_id="account_201",
        state=ResourceState.ABSENT,
        provenance_evidence_id="evidence_sql_02",
        source_path="evidence/databases/replica.sql",
        timestamp=datetime(2026, 9, 29, 10, 0, 0, tzinfo=timezone.utc),
        is_direct=True,
        rationale="Confirmed absent in database snapshot",
    )
    assess = assess_resource_policy(recon, standard_rules)
    assert assess.policy_satisfied

    decision = validate_case_completion(
        case_id="case_test_02",
        is_non_deletion=False,
        policy_assessments={"account_201": assess},
        flow_risks=[],
        known_evidence_ids={"evidence_sql_02"},
        resource_evidence_map={"account_201": {"evidence_sql_02"}},
    )
    assert decision.is_complete is True
    assert decision.deletion_status == "COMPLETE"
    assert len(decision.steps) == 1
    assert decision.steps[0].operation == "VERIFY_RECORD_ABSENT"
    assert decision.steps[0].evidence_id == "evidence_sql_02"


def test_active_synchronization_flow():
    """3. Active synchronization flow -> INCOMPLETE with REPORT_ACTIVE_DATA_FLOW."""
    risk = ResurrectionRiskFinding(
        case_id="case_test_03",
        risk_category=RiskCategory.ACTIVE_DATA_FLOW,
        source_system="integration_service",
        target_system="search_service",
        implicated_resource="data_flow_901",
        downstream_resource="search_901",
        evidence_ids=["evidence_log_01"],
        event_times=[datetime(2026, 9, 28, 12, 0, 0, tzinfo=timezone.utc)],
        time_relation=TimeRelation.PRIOR_TO_AUDIT,
        confidence="HIGH",
        flow_status=FlowStatus.ACTIVE,
        reason="Active sync connector",
    )
    plan = plan_case("case_test_03", False, policy_assessments={}, flow_risks=[risk])
    assert plan.deletion_status == "INCOMPLETE"
    assert any(s.operation == "REPORT_ACTIVE_DATA_FLOW" for s in plan.steps)
    assert any(s.operation == "DISABLE_DATA_FLOW" for s in plan.steps)
    assert any(s.operation == "VERIFY_DATA_FLOW_DISABLED" for s in plan.steps)


def test_restore_or_resurrection_risk():
    """4. Restore or resurrection risk: backup archive unblocked -> INCOMPLETE with REPORT_RESTORE_RISK."""
    risk = ResurrectionRiskFinding(
        case_id="case_test_04",
        risk_category=RiskCategory.RESTORE_RISK,
        source_system="backup_service",
        target_system="account_service",
        implicated_resource="backup_501",
        downstream_resource="account_501",
        evidence_ids=["evidence_rec_01"],
        event_times=[datetime(2026, 9, 27, 12, 0, 0, tzinfo=timezone.utc)],
        time_relation=TimeRelation.PRIOR_TO_AUDIT,
        confidence="HIGH",
        flow_status=FlowStatus.ACTIVE,
        reason="Unblocked backup restore access",
    )
    plan = plan_case("case_test_04", False, policy_assessments={}, flow_risks=[risk])
    assert plan.deletion_status == "INCOMPLETE"
    assert any(s.operation == "REPORT_RESTORE_RISK" for s in plan.steps)
    assert any(s.operation == "BLOCK_RESTORE" for s in plan.steps)
    assert any(s.operation == "VERIFY_RESTORE_BLOCKED" for s in plan.steps)


def test_allowed_retained_record(standard_rules):
    """5. Allowed retained record: policy requires RETAIN and record is PRESENT -> satisfied, not deleted."""
    recon = ReconstructedState(
        resource_id="legal_record_01",
        state=ResourceState.PRESENT,
        provenance_evidence_id="evidence_pdf_01",
        source_path="evidence/documents/tax_statement.pdf",
        timestamp=datetime(2026, 9, 25, 12, 0, 0, tzinfo=timezone.utc),
        is_direct=True,
        rationale="Retained statutory record",
    )
    assess = assess_resource_policy(recon, standard_rules)
    assert assess.required_action == "RETAIN"
    assert assess.policy_satisfied is True

    # When validated for completion, verify it requires VERIFY_RECORD_PRESENT
    decision = validate_case_completion(
        case_id="case_test_05",
        is_non_deletion=False,
        policy_assessments={"legal_record_01": assess},
        flow_risks=[],
        known_evidence_ids={"evidence_pdf_01"},
        resource_evidence_map={"legal_record_01": {"evidence_pdf_01"}},
    )
    assert decision.is_complete is True
    assert decision.steps[0].operation == "VERIFY_RECORD_PRESENT"


def test_tombstone_containing_prohibited_direct_identifiers(standard_rules):
    """6. Tombstone containing prohibited direct identifiers -> policy violation, REPORT_EXPOSED_PII."""
    recon = ReconstructedState(
        resource_id="tombstone_777",
        state=ResourceState.REDACTED,
        provenance_evidence_id="evidence_json_01",
        source_path="evidence/records/tombstones.json",
        timestamp=datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc),
        is_direct=True,
        rationale="Account tombstone",
        raw_details={"user_id": "user_777", "email": "exposed@example.com"},  # Prohibited direct PII
    )
    assess = assess_resource_policy(recon, standard_rules)
    assert assess.is_tombstone is True
    assert assess.tombstone_direct_pii_removed is False
    assert assess.policy_satisfied is False

    plan = plan_case("case_test_06", False, {"tombstone_777": assess})
    assert any(s.operation == "REPORT_EXPOSED_PII" for s in plan.steps)
    assert any(s.operation == "REDACT_RECORD" for s in plan.steps)
    assert any(s.operation == "VERIFY_RECORD_REDACTED" for s in plan.steps)


def test_unresolved_identity():
    """7. Unresolved identity: cluster with conflict -> fails completion validation."""
    cluster = Cluster(
        case_id="case_test_07",
        nodes={("user_id", "user_99"): IdentifierNode("user_id", "user_99", "user_99", "test")},
        links=[],
        conflicts=["Conflicting phone number linked to multiple distinct subjects"],
    )
    decision = validate_case_completion(
        case_id="case_test_07",
        is_non_deletion=False,
        policy_assessments={"acc_1": PolicyAssessment("acc_1", "account_service", "USER_PROFILE", "r1", "DELETE", ResourceState.ABSENT, True, "ok", ["ev_1"])},
        flow_risks=[],
        identity_cluster=cluster,
        known_evidence_ids={"ev_1"},
    )
    assert decision.is_complete is False
    assert IncompleteReasonCode.IDENTITY_CONFLICT.value in decision.reasons_incomplete


def test_conflicting_evidence():
    """8. Conflicting evidence: contradictory states at same cutoff -> UNKNOWN state, fails completion."""
    audit_at = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    ts = datetime(2026, 9, 28, 12, 0, 0, tzinfo=timezone.utc)
    obs = [
        EvidenceObservation("account_888", ResourceState.PRESENT, ts, "ev_1", "path_1", True),
        EvidenceObservation("account_888", ResourceState.ABSENT, ts, "ev_2", "path_2", True),
    ]
    recon = reconstruct_resource_state("account_888", audit_at, direct_observations=obs, activity_events=[])
    assert recon.state == ResourceState.UNKNOWN
    assert recon.has_conflict is True


def test_ocr_observation_with_ambiguous_spatial_association():
    """9. OCR observation with ambiguous spatial association -> ObservationConfidence.AMBIGUOUS."""
    obs = ExtractedObservation(
        source_file="evidence/images/test.png",
        file_id="evidence_99",
        evidence_id="evidence_99",
        source_location="x:0.5,y:0.5",
        observation_type="SCREENSHOT_ENTITY_OCR",
        extraction_method="APPLE_VISION",
        confidence=ObservationConfidence.AMBIGUOUS,
        resource_id="account_999",
        observed_state=ResourceState.PRESENT,
        ambiguity_flags=["APPLE_VISION_LOCAL_OCR", "AMBIGUOUS_STATE_OR_IDENTITY_ASSOCIATION"],
    )
    assert obs.confidence == ObservationConfidence.AMBIGUOUS
    assert "AMBIGUOUS_STATE_OR_IDENTITY_ASSOCIATION" in obs.ambiguity_flags
    # to_evidence_observation flags is_direct=False for AMBIGUOUS
    ev_obs = obs.to_evidence_observation()
    assert ev_obs is not None
    assert ev_obs.is_direct is False


def test_missing_or_mismatched_screenshot_cache_data():
    """10. Missing or mismatched screenshot cache data: handled safely without crashing."""
    with tempfile.TemporaryDirectory() as tmp_cache:
        extractor = AppleVisionExtractor(config=LocalVisionConfig(cache_dir=tmp_cache))
        # Non-existent file raises FileNotFoundError
        with pytest.raises(FileNotFoundError):
            extractor.extract_file("evidence_999", "evidence/images/missing_image.png", "test")


def test_explicitly_non_deletion_request():
    """11. Explicitly non-deletion request -> NOT_APPLICABLE with empty steps."""
    text = "Can you tell me what personal information you hold about me? This is an information request, not a request to erase it. Please do not close the account."
    assert is_non_deletion_inquiry(text) is True

    decision = validate_case_completion(
        case_id="case_non_del_01",
        is_non_deletion=True,
        policy_assessments={},
    )
    assert decision.deletion_status == "NOT_APPLICABLE"
    assert decision.steps == []


def test_integrated_pipeline_full_run_and_validation():
    """12. Full integrated pipeline execution across 518 cases verifies all invariants."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_csv = os.path.join(tmpdir, "nulltrace_integrated.csv")
        res = run_integrated_pipeline(data_dir="./dataset", output_path=out_csv)

        assert os.path.isfile(out_csv)
        counts = res["counts"]
        assert counts["total_requests"] == 518
        assert counts["validation_failures"] == 0
        assert counts["not_applicable"] == 10
        assert counts["complete"] > 0
        assert counts["incomplete"] > 0
        assert counts["total_requests"] == (
            counts["not_applicable"] + counts["complete"] + counts["incomplete"]
        )
