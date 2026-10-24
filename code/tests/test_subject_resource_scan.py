"""code/tests/test_subject_resource_scan.py

Tests for evidence content scanning, subject-to-resource co-occurrence analysis,
and Answer-Key Exclusion Rule enforcement.
"""

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
    from code.evaluation.subject_resource_scan import (
        is_path_excluded,
        extract_resource_ids,
        extract_subject_identifiers,
        scan_evidence_files,
        recheck_unfound_ids,
    )
except ImportError:
    from evaluation.subject_resource_scan import (
        is_path_excluded,
        extract_resource_ids,
        extract_subject_identifiers,
        scan_evidence_files,
        recheck_unfound_ids,
    )


def test_answer_key_exclusions():
    """Asserts that answer keys and diagnostic directories are strictly excluded."""
    assert is_path_excluded("dataset/sample_output.csv") is True
    assert is_path_excluded("/repo/dataset/sample_output.csv") is True
    assert is_path_excluded("dataset/output.csv") is True
    assert is_path_excluded("output.csv") is True
    assert is_path_excluded("code/evaluation/resource_link_report.md") is True
    assert is_path_excluded("code/docs/SPEC_EXTRACTED.md") is True

    # Allowed evidence files must NOT be excluded
    assert is_path_excluded("dataset/evidence/databases/replica.sql") is False
    assert is_path_excluded("dataset/evidence/documents/report.pdf") is False
    assert is_path_excluded("dataset/system_activity.csv") is False
    assert is_path_excluded("dataset/user_identities.csv") is False


def test_synthetic_fixture_cooccurrence(tmp_path):
    """
    Fixture test: a small synthetic evidence file with one subject, two resource_ids
    on separate lines, and one unrelated resource_id. Expect exactly the two correct co-occurrences.
    """
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    sample_file = evidence_dir / "test_records.log"
    content = (
        "2026-08-01 10:00:00 [account_service] Primary account account_101 assigned to user_555 (email: alice@example.com)\n"
        "2026-08-01 10:05:00 [search_service] Search index search_202 updated for user_555\n"
        "2026-08-01 10:10:00 [backup_service] Backup backup_999 created for unrelated user_888\n"
    )
    sample_file.write_text(content, encoding="utf-8")

    file_statuses, cooccurrences, all_found_rids = scan_evidence_files(data_dir=str(tmp_path))

    assert "account_101" in all_found_rids
    assert "search_202" in all_found_rids
    assert "backup_999" in all_found_rids

    user_555_pairs = [c for c in cooccurrences if c.subject_val in ("user_555", "alice@example.com")]
    user_555_rids = set(c.resource_id for c in user_555_pairs)

    assert user_555_rids == {"account_101", "search_202"}
    assert "backup_999" not in user_555_rids


def test_recheck_unfound_ids_with_answer_key_isolation():
    """Asserts that recheck_unfound_ids finds support_001 in PDF, and zero matches for the other 3."""
    findings = recheck_unfound_ids(
        target_ids=["account_004", "support_001", "audit_record_5569", "audit_record_6645"],
        data_dir="./dataset",
    )

    # support_001 is inside delivery_correction_attachment.pdf
    assert len(findings["support_001"]) >= 1
    assert any("delivery_correction_attachment.pdf" in m["file"] for m in findings["support_001"])

    # The other 3 do not exist in participant-facing files
    assert len(findings["account_004"]) == 0
    assert len(findings["audit_record_5569"]) == 0
    assert len(findings["audit_record_6645"]) == 0
