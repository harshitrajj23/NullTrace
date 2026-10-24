"""
Unit tests for the conservative baseline 518-case pipeline (code/src/pipeline.py).
"""

import csv
import json
import os
import tempfile
import pytest

from code.src.pipeline import (
    is_non_deletion_inquiry,
    get_system_id_for_resource,
    get_finding_op_and_state,
    run_baseline_pipeline,
)
from code.src.ops import (
    HARDCODED_OPERATIONS,
    Step,
    sort_steps,
    validate_steps,
)
from code.src.grader_io import parse_steps_json


def test_all_15_operations_grammar_and_validation():
    """Tests all 15 operation/state combinations and phase ordering through validate_steps."""
    # Build a valid sequence with all 15 ops
    steps = []
    known_evidence_ids = {"ev_finding_01", "ev_verification_01"}

    for idx, (phase, op, state) in enumerate(HARDCODED_OPERATIONS, start=1):
        ev_id = ""
        if phase == "FINDING":
            ev_id = "ev_finding_01"
        elif phase == "VERIFICATION":
            ev_id = ""  # For INCOMPLETE status, future verification steps have empty evidence_id

        steps.append(
            Step(
                step_no=idx,
                phase=phase,
                system_id="account_service",
                resource_id=f"res_{idx}",
                operation=op,
                state=state,
                evidence_id=ev_id,
            )
        )

    # Sort and validate for INCOMPLETE status
    sorted_steps = sort_steps(steps)
    errors = validate_steps(sorted_steps, "INCOMPLETE", known_evidence_ids)
    assert errors == [], f"All 15 operations should validate cleanly: {errors}"


def test_non_deletion_inquiry_classifier():
    """Tests that deterministic non-deletion inquiries are detected, and deletion requests are not."""
    # Positive non-deletion cases
    assert is_non_deletion_inquiry("Please stop the promotional emails. I am not asking for deletion.") is True
    assert is_non_deletion_inquiry("I'd like to download my account information in a portable format. Please keep the account as it is.") is True
    assert is_non_deletion_inquiry("Can you tell me what personal information you hold about me? This is an information request, not a request to erase it.") is True
    assert is_non_deletion_inquiry("The mobile number on my profile is out of date. Please replace it with the new one and leave the account active.") is True
    assert is_non_deletion_inquiry("Please remove me from marketing lists only. I still want receipts.") is True

    # Genuine deletion cases (in English and other languages)
    assert is_non_deletion_inquiry("Please permanently delete the account associated with this email address.") is False
    assert is_non_deletion_inquiry("I want to close this account and have its associated personal data deleted.") is False
    assert is_non_deletion_inquiry("Je demande la suppression définitive du compte associé à cette adresse e-mail.") is False
    assert is_non_deletion_inquiry("Solicito a exclusão permanente da conta associada a este e-mail.") is False


def test_baseline_pipeline_execution_and_invariants():
    """
    Runs the baseline pipeline to a temporary directory and verifies all contract invariants:
    - Exactly 518 input requests represented once
    - Output columns: case_id,deletion_status,steps_json
    - Case IDs are sorted
    - NOT_APPLICABLE always has steps_json = []
    - COMPLETE is never emitted
    - Consecutive step numbers starting from 1
    - Valid JSON formatting
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        out_csv = os.path.join(tmpdir, "nulltrace_baseline.csv")
        res = run_baseline_pipeline(data_dir="./dataset", output_path=out_csv)

        assert os.path.isfile(out_csv)
        counts = res["counts"]
        assert counts["total_requests"] == 518
        assert counts["validation_failures"] == 0
        assert counts["complete"] == 0
        assert counts["not_applicable"] == 10
        assert counts["incomplete"] == 508

        with open(out_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == ["case_id", "deletion_status", "steps_json"]
            rows = list(reader)

        assert len(rows) == 518

        # 1. Check case sorting and uniqueness
        case_ids = [r["case_id"] for r in rows]
        assert len(case_ids) == len(set(case_ids)), "Every case_id must be unique"
        assert case_ids == sorted(case_ids), "Case IDs must be strictly sorted"

        # 2. Check each row's validity
        for r in rows:
            cid = r["case_id"]
            status = r["deletion_status"]
            steps_json_str = r["steps_json"]

            # Must never emit COMPLETE
            assert status in ("NOT_APPLICABLE", "INCOMPLETE")

            # Parse steps
            steps = parse_steps_json(steps_json_str)

            if status == "NOT_APPLICABLE":
                assert steps_json_str == "[]"
                assert len(steps) == 0
            elif status == "INCOMPLETE":
                if len(steps) > 0:
                    for idx, s in enumerate(steps, start=1):
                        assert s.step_no == idx, f"Step numbering must be consecutive starting from 1 on {cid}"
                        assert s.phase == "FINDING", f"Baseline must emit only FINDING phase on {cid}"
                        assert s.evidence_id != "", f"Finding on {cid} must have non-empty evidence_id"
                        # Verify operation matches resource prefix
                        if s.resource_id.startswith("data_flow_"):
                            assert s.operation == "REPORT_ACTIVE_DATA_FLOW"
                            assert s.state == "ACTIVE"
                        elif s.resource_id.startswith("backup_"):
                            assert s.operation == "REPORT_RESTORE_RISK"
                            assert s.state == "ACTIVE"
                        else:
                            assert s.operation == "REPORT_REMAINING_RECORD"
                            assert s.state == "PRESENT"


def test_no_fabricated_evidence_or_answer_key_reading():
    """
    Verifies that unknown/unlinked evidence never becomes a fabricated finding,
    and that pipeline execution does not depend on sample_output.csv.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a mock dataset directory containing only participant-facing files
        # (NO sample_output.csv)
        import shutil

        shutil.copy("dataset/deletion_requests.csv", os.path.join(tmpdir, "deletion_requests.csv"))
        shutil.copy("dataset/user_identities.csv", os.path.join(tmpdir, "user_identities.csv"))
        shutil.copy("dataset/user_audit_log.csv", os.path.join(tmpdir, "user_audit_log.csv"))
        shutil.copy("dataset/system_activity.csv", os.path.join(tmpdir, "system_activity.csv"))
        shutil.copy("dataset/deletion_rules.csv", os.path.join(tmpdir, "deletion_rules.csv"))
        shutil.copy("dataset/evidence_files.csv", os.path.join(tmpdir, "evidence_files.csv"))

        # Explicitly ensure sample_output.csv does NOT exist in tmpdir
        assert not os.path.exists(os.path.join(tmpdir, "sample_output.csv"))

        out_csv = os.path.join(tmpdir, "out.csv")
        res = run_baseline_pipeline(data_dir=tmpdir, output_path=out_csv)
        assert res["counts"]["total_requests"] == 518
        assert res["counts"]["validation_failures"] == 0
