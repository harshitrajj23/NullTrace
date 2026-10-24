"""code/tests/test_audit_consumption.py

Regression tests asserting that every row in user_audit_log.csv is either
cited by an identity link or recorded with an explicit reason in the diagnostic.
Asserts that no audit row is silently dropped.
Uses the real dataset read-only.
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
    from code.src.loader import load_dataset
    from code.evaluation.audit_consumption import check_audit_consumption
    from code.evaluation.locate_resources import locate_resources
except ImportError:
    from src.loader import load_dataset
    from evaluation.audit_consumption import check_audit_consumption
    from evaluation.locate_resources import locate_resources


def test_every_audit_row_cited_or_explained():
    """Asserts that every row in user_audit_log.csv is either cited or has an explicit diagnostic reason."""
    dataset_dir = os.path.join(_repo_root, "dataset")
    dataset = load_dataset(dataset_dir)
    report = check_audit_consumption(dataset_dir)

    total_rows = len(dataset.user_audit_log)
    assert report.total_audit_rows == total_rows
    assert report.total_audit_rows == 306

    # Every single row must be either cited or in uncited_rows
    assert report.cited_audit_rows + report.uncited_audit_rows_count == total_rows
    assert report.cited_audit_rows == 293
    assert report.uncited_audit_rows_count == 13

    # Assert no row is silently dropped and every uncited row has an explicit reason
    uncited_ids = set()
    for row in report.uncited_rows:
        assert row.reason is not None and len(row.reason.strip()) > 0
        assert "never submitted a deletion request" in row.reason
        uncited_ids.add(row.audit_id)

    assert len(uncited_ids) == 13

    # Verify that all 306 audit events are mapped to either cited or uncited
    all_audit_ids = set(a.audit_id for a in dataset.user_audit_log)
    assert uncited_ids.issubset(all_audit_ids)


def test_identity_rows_consumption():
    """Asserts that all requesting users are consumed into clusters."""
    dataset_dir = os.path.join(_repo_root, "dataset")
    report = check_audit_consumption(dataset_dir)

    assert report.total_identity_rows == 850
    assert report.consumed_identity_rows == 517
    assert report.unconsumed_identity_rows == 333
    assert report.consumed_identity_rows + report.unconsumed_identity_rows == 850


def test_sample_resource_classification():
    """Asserts that all 111 sample resource_ids are partitioned into valid diagnostic classes."""
    dataset_dir = os.path.join(_repo_root, "dataset")
    loc_res = locate_resources(dataset_dir)

    assert loc_res["total_distinct_rids"] == 111
    counts = loc_res["classification_counts"]
    assert counts["DIRECT_IN_ACTIVITY"] == 85
    assert counts["DIRECT_IN_EVIDENCE_MANIFEST"] == 0
    assert counts["IN_EVIDENCE_CONTENT"] == 22
    assert counts["NOT_FOUND_IN_DATASET"] == 4

    assert set(loc_res["rids_by_class"]["NOT_FOUND_IN_DATASET"]) == {
        "account_004",
        "audit_record_5569",
        "audit_record_6645",
        "support_001",
    }
