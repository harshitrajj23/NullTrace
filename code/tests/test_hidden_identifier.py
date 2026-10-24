"""
code/tests/test_hidden_identifier.py

Unit tests for hidden identifier candidate discovery, image reconciliation,
and strict answer-key isolation under Step H.1.
"""

import json
import os
import sqlite3
import tempfile
import pytest

from code.evaluation.hidden_identifier_scan import (
    classify_value,
    is_path_excluded,
    reconcile_images_and_files,
    find_hidden_identifier_candidates
)


def test_synthetic_sql_row_with_hidden_identifier_key():
    """
    Synthetic SQL file with a custom table and record_json containing
    an identifier-shaped value under a key other than user_id/email/phone.
    Expects the key to be discovered as a candidate field.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_dir = os.path.join(tmpdir, "evidence/databases")
        os.makedirs(db_dir, exist_ok=True)
        sql_path = os.path.join(db_dir, "custom_audit.sql")

        json_payload = json.dumps({
            "resource_id": "custom_audit_01",
            "client_tracking_id": "user_7777",
            "session_ticket": "CS-12345",
            "device_mode": "desktop"
        })

        sql_content = f"""
        CREATE TABLE custom_audit_table (
            resource_id TEXT PRIMARY KEY,
            record_json TEXT NOT NULL
        );
        INSERT INTO custom_audit_table VALUES ('custom_audit_01', '{json_payload}');
        """
        with open(sql_path, "w", encoding="utf-8") as f:
            f.write(sql_content)

        # Create dummy user_identities.csv so loader works
        with open(os.path.join(tmpdir, "user_identities.csv"), "w", encoding="utf-8") as f:
            f.write("user_id,name,email,phone,email_hash,updated_at\nuser_7777,Test User,test@example.com,+1 555 123 4567,abc,2026-01-01T00:00:00Z\n")
        with open(os.path.join(tmpdir, "user_audit_log.csv"), "w", encoding="utf-8") as f:
            f.write("audit_id,user_id,event_time,field_name,old_value,new_value\n")

        _, candidate_fields = find_hidden_identifier_candidates(tmpdir)
        field_names = [cf["field_name"] for cf in candidate_fields]

        assert "client_tracking_id" in field_names
        client_field = next(cf for cf in candidate_fields if cf["field_name"] == "client_tracking_id")
        assert "user_7777" in client_field["sample_values"]
        assert client_field["in_identities_or_audit"] is True


def test_evaluation_and_docs_files_excluded_from_scan():
    """
    Asserts that files under code/evaluation/ and code/docs/ are strictly excluded,
    along with answer-key templates.
    """
    assert is_path_excluded("code/evaluation/hidden_identifier_report.md")
    assert is_path_excluded("code/evaluation/hidden_identifier_scan.py")
    assert is_path_excluded("code/evaluation/sql_join_report.md")
    assert is_path_excluded("code/docs/SPEC_EXTRACTED.md")
    assert is_path_excluded("dataset/sample_output.csv")
    assert is_path_excluded("dataset/output.csv")
    assert is_path_excluded("output.csv")

    # Allowed dataset paths
    assert not is_path_excluded("dataset/evidence/databases/customer_data_inventory_20260524.sql")
    assert not is_path_excluded("dataset/evidence/images/account_admin_console_20260926.png")
    assert not is_path_excluded("dataset/system_activity.csv")


def test_image_and_file_count_reconciliation():
    """
    Asserts exact reconciliation:
    - 11 disk images matching 11 manifest rows
    - 94 evidence files on disk
    - 101 total scanned files (94 evidence + 7 allowed root CSVs)
    """
    recon = reconcile_images_and_files("./dataset")
    assert len(recon["disk_images"]) == 11
    assert len(recon["manifest_png_rows"]) == 11
    assert recon["total_evidence_files"] == 94
    assert recon["total_scanned_files"] == 101
