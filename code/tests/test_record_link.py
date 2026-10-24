"""
Unit tests for JSON record-level linkage and activity-to-record bridge diagnostic (Step I).
"""

import json
import os
import tempfile
import pytest

from code.evaluation.record_link_scan import (
    extract_all_json_records,
    find_record_cooccurrences,
    find_activity_bridge_candidates,
    is_path_excluded,
)
from code.evaluation.subject_resource_scan import extract_resource_ids, extract_subject_identifiers


def test_multiline_json_record_cooccurrence_fixture():
    """
    Fixture test: a multi-line JSON object with a user identifier on one line
    and a resource_id on another.
    Expects a RECORD_COOCCURRENCE candidate, and no candidate from the line-level scanner.
    """
    json_content = """{
        "records": [
            {
                "resource_id": "account_9999",
                "service": "account_service",
                "email": "synthetic.user@example.com",
                "status": "ACTIVE"
            }
        ]
    }"""

    # 1. Line-level scanner test
    line_candidates = []
    for line_idx, line in enumerate(json_content.splitlines()):
        rids = extract_resource_ids(line)
        subjects = extract_subject_identifiers(line)
        for r in rids:
            for s in subjects:
                line_candidates.append((r, s))

    # Line-level scanner must find NO candidates because resource_id and email are on different lines
    assert len(line_candidates) == 0, "Line-level scanner should not link tokens on different lines"

    # 2. Record-level scanner test
    data = json.loads(json_content)
    records = extract_all_json_records(data, "synthetic_records.json")
    assert len(records) == 1

    cands = find_record_cooccurrences(records)
    assert len(cands) == 1
    assert cands[0]["resource_id"] == "account_9999"
    assert cands[0]["identifier_value"] == "synthetic.user@example.com"
    assert cands[0]["identifier_type"] == "email"
    assert cands[0]["reason_code"] == "RECORD_COOCCURRENCE"


def test_activity_bridge_fixture():
    """
    Fixture test: a bridge case where subject identifier appears only on record B,
    and record B shares a resource_id with activity row A.
    Expects one BRIDGE_VIA_RESOURCE candidate, and no second hop.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create synthetic JSON record B: connects user_8888 with data_flow_1111
        json_data = {
            "records": [
                {
                    "resource_id": "data_flow_1111",
                    "user_id": "user_8888",
                    "type": "CONNECTOR"
                }
            ]
        }
        records = extract_all_json_records(json_data, "synthetic.json")
        record_cands = find_record_cooccurrences(records)
        assert len(record_cands) == 1
        assert record_cands[0]["resource_id"] == "data_flow_1111"

        # Create synthetic system_activity.csv: row A connects data_flow_1111 to search_2222
        # And another row connects search_2222 to export_3333 (second hop that should NOT be traversed)
        act_csv_path = os.path.join(tmpdir, "system_activity.csv")
        with open(act_csv_path, "w", newline="", encoding="utf-8") as f:
            f.write("activity_id,event_time,event_type,source_system,target_system,resource_id,reported_result,details\n")
            f.write("act_01,2026-05-01T10:00:00Z,SYNC_RECORD,connector,search,data_flow_1111,SUCCESS,Connector synced downstream search_2222.\n")
            f.write("act_02,2026-05-01T11:00:00Z,EXPORT_JOB,search,export,search_2222,SUCCESS,Export processed export_3333.\n")

        bridge_cands = find_activity_bridge_candidates(record_cands, tmpdir)
        assert len(bridge_cands) == 1
        bridge = bridge_cands[0]
        assert bridge["reason_code"] == "BRIDGE_VIA_RESOURCE"
        assert bridge["identifier_value"] == "user_8888"
        assert bridge["resource_id"] == "search_2222"
        assert bridge["bridge_resource_id"] == "data_flow_1111"
        assert bridge["activity_id"] == "act_01"

        # Ensure no 2nd hop to export_3333
        target_rids = {b["resource_id"] for b in bridge_cands}
        assert "export_3333" not in target_rids, "Bridge must not chain more than 1 hop"


def test_answer_key_and_eval_paths_excluded():
    """
    Test that code/evaluation/, code/docs/, sample_output.csv, and output.csv
    are strictly excluded by is_path_excluded.
    """
    assert is_path_excluded("dataset/sample_output.csv") is True
    assert is_path_excluded("dataset/output.csv") is True
    assert is_path_excluded("code/evaluation/record_cooccurrence.csv") is True
    assert is_path_excluded("code/evaluation/hidden_identifier_report.md") is True
    assert is_path_excluded("code/docs/SPEC_EXTRACTED.md") is True
    assert is_path_excluded("dataset/evidence/records/connector_configurations_20260812.json") is False
