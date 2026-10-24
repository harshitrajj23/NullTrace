"""code/tests/test_synthetic_pipeline_cases.py

Team-made synthetic end-to-end evaluation test cases for HackerRank Orchestrate:
Ghost Data Still Exists.

Tests the actual integrated pipeline (run_integrated_pipeline) on 3 realistic failure modes:
1. Primary record absent but replica still contains personal data (replication drift).
2. Primary deletion reported successful but active synchronization path may recreate data.
3. Tombstone retains permitted internal reference but also exposes prohibited direct PII.

All cases use entirely synthetic identifiers and values.
Does not insert anything into dataset/ or modify production data.
"""

import csv
from datetime import datetime, timezone
import json
import os
import sqlite3
import sys
import tempfile
import pytest

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

if "code" in sys.modules and not hasattr(sys.modules["code"], "src"):
    del sys.modules["code"]

from code.src.models import DeletionRequest, SourceRef
from code.src.pipeline import run_integrated_pipeline


def _create_synthetic_environment(tmpdir: str):
    """Sets up a complete, isolated synthetic dataset environment in tmpdir."""
    ds_dir = os.path.join(tmpdir, "dataset")
    ev_dir = os.path.join(ds_dir, "evidence")
    db_dir = os.path.join(ev_dir, "databases")
    rec_dir = os.path.join(ev_dir, "records")
    os.makedirs(db_dir, exist_ok=True)
    os.makedirs(rec_dir, exist_ok=True)

    # 1. deletion_rules.csv
    rules_csv = os.path.join(ds_dir, "deletion_rules.csv")
    with open(rules_csv, "w", encoding="utf-8") as f:
        f.write("rule_id,data_category,condition,required_action\n")
        f.write("rule_01,USER_PROFILE,default,DELETE\n")
        f.write("rule_02,ACCOUNT_TOMBSTONE,default,REDACT\n")
        f.write("rule_03,LEGAL_HOLD_RECORD,default,RETAIN\n")
        f.write("rule_04,SEARCH_INDEX_ENTRY,default,DELETE\n")
        f.write("rule_05,EXPORT_ARCHIVE,default,DELETE\n")

    # 2. user_identities.csv
    ident_csv = os.path.join(ds_dir, "user_identities.csv")
    with open(ident_csv, "w", encoding="utf-8") as f:
        f.write("user_id,full_name,email,phone,email_hash,updated_at\n")
        f.write("user_synth_01,Replica Drift User,synth.drift@example.org,+1 555 0101,hash_synth_01,2026-08-01T10:00:00Z\n")
        f.write("user_synth_02,Active Sync User,synth.sync@example.org,+1 555 0102,hash_synth_02,2026-08-01T10:00:00Z\n")
        f.write("user_synth_03,Tombstone Leak User,synth.tombstone@example.org,+1 555 0103,hash_synth_03,2026-08-01T10:00:00Z\n")

    # 3. user_audit_log.csv
    audit_csv = os.path.join(ds_dir, "user_audit_log.csv")
    with open(audit_csv, "w", encoding="utf-8") as f:
        f.write("audit_id,user_id,changed_field,old_value,new_value,recorded_at\n")

    # 4. system_activity.csv
    act_csv = os.path.join(ds_dir, "system_activity.csv")
    with open(act_csv, "w", encoding="utf-8") as f:
        f.write("activity_id,event_time,event_type,source_system,target_system,resource_id,reported_result,details\n")
        # Case 2 has an active sync flow event
        f.write("act_sync_01,2026-09-01T10:00:00Z,SYNC_RECORD,account_service,analytics_platform,data_flow_synth_202,SUCCESS,Continuous profile bridge for user_synth_02 active.\n")

    # 5. evidence_files.csv
    ev_csv = os.path.join(ds_dir, "evidence_files.csv")
    with open(ev_csv, "w", encoding="utf-8") as f:
        f.write("file_id,file_path,origin,captured_at\n")
        f.write("evidence_replica_db,evidence/databases/replica.sql,database_failover,2026-09-10T12:00:00Z\n")
        f.write("evidence_connector_json,evidence/records/connectors.json,integration_service,2026-09-10T12:00:00Z\n")
        f.write("evidence_tombstone_json,evidence/records/tombstone.json,identity_service,2026-09-10T12:00:00Z\n")

    # 6. Database evidence for Case 1 (replica drift: absent in primary, present in failover)
    sql_path = os.path.join(db_dir, "replica.sql")
    with open(sql_path, "w", encoding="utf-8") as f:
        f.write("-- Ghost Data Still Exists: point-in-time database snapshot\n")
        f.write("-- Captured at: 2026-09-10T12:00:00Z\n")
        f.write("BEGIN TRANSACTION;\n")
        f.write("CREATE TABLE customer_profiles_primary (resource_id TEXT PRIMARY KEY, user_id TEXT, email TEXT);\n")
        f.write("CREATE TABLE customer_profiles_failover_replica (resource_id TEXT PRIMARY KEY, user_id TEXT, email TEXT);\n")
        # Primary is deleted (no row for user_synth_01), but failover replica still has it!
        f.write("INSERT INTO customer_profiles_failover_replica VALUES ('account_synth_replica_01', 'user_synth_01', 'synth.drift@example.org');\n")
        f.write("COMMIT;\n")

    # 7. Connector JSON evidence for Case 2 (active sync connector enabled: true)
    conn_json_path = os.path.join(rec_dir, "connectors.json")
    with open(conn_json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "exported_at": "2026-09-10T12:00:00Z",
                "origin": "integration_service",
                "collection": "connector_configurations",
                "records": [
                    {
                        "recorded_at": "2026-09-10T11:00:00Z",
                        "system": "integration_service",
                        "resource_id": "data_flow_synth_202",
                        "customer_reference": "user_synth_02",
                        "customer_email": "synth.sync@example.org",
                        "destination": "analytics_platform",
                        "result": "ACTIVE",
                        "enabled": True,
                    }
                ],
            },
            f,
        )

    # 8. Tombstone JSON evidence for Case 3 (retains internal ID but leaks prohibited direct email PII)
    tb_json_path = os.path.join(rec_dir, "tombstone.json")
    with open(tb_json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "exported_at": "2026-09-10T12:00:00Z",
                "source": "identity_service",
                "snapshots": [
                    {
                        "captured_at": "2026-09-10T12:00:00Z",
                        "data_store": "identity_store",
                        "collection": "deleted_customer_references",
                        "records": [
                            {
                                "resource_id": "tombstone_synth_303",
                                "subject_reference": "user_synth_03",
                                "email": "synth.tombstone@example.org",
                                "email_hash": "hash_synth_03",
                            }
                        ],
                    }
                ],
            },
            f,
        )

    # 9. deletion_requests.csv (dummy template for loader)
    del_req_csv = os.path.join(ds_dir, "deletion_requests.csv")
    with open(del_req_csv, "w", encoding="utf-8") as f:
        f.write("case_id,email,requested_at,reported_status,reported_at,audit_at,request_text\n")

    return ds_dir


def _make_request(case_id: str, email: str, req_time: str, rep_time: str, aud_time: str, text: str) -> DeletionRequest:
    return DeletionRequest(
        case_id=case_id,
        email_raw=email,
        email_norm=email.lower().strip(),
        requested_at_raw=req_time,
        requested_at=datetime.fromisoformat(req_time.replace("Z", "+00:00")),
        reported_status="COMPLETE",
        reported_at_raw=rep_time,
        reported_at=datetime.fromisoformat(rep_time.replace("Z", "+00:00")),
        audit_at_raw=aud_time,
        audit_at=datetime.fromisoformat(aud_time.replace("Z", "+00:00")),
        request_text=text,
        source=SourceRef("synthetic", 1),
    )


def test_synthetic_case_replica_drift():
    """Synthetic Case 1: Primary record absent but replica still contains personal data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ds_dir = _create_synthetic_environment(tmpdir)
        out_csv = os.path.join(tmpdir, "output.csv")

        req = _make_request(
            case_id="case_synth_01",
            email="synth.drift@example.org",
            req_time="2026-09-01T09:00:00Z",
            rep_time="2026-09-05T10:00:00Z",
            aud_time="2026-09-15T12:00:00Z",
            text="Please delete all personal data and cancel my account completely.",
        )

        res = run_integrated_pipeline(data_dir=ds_dir, output_path=out_csv, requests=[req])
        results = res["results"]
        assert len(results) == 1
        r0 = results[0]

        # Expected: INCOMPLETE due to surviving replica record
        assert r0["deletion_status"] == "INCOMPLETE"
        steps = json.loads(r0["steps_json"])
        assert len(steps) >= 3

        # Finding: REPORT_REMAINING_RECORD with replica evidence
        finding = steps[0]
        assert finding["phase"] == "FINDING"
        assert finding["resource_id"] == "account_synth_replica_01"
        assert finding["operation"] == "REPORT_REMAINING_RECORD"
        assert finding["state"] == "PRESENT"
        assert finding["evidence_id"] == "evidence_replica_db"

        # Remediation: DELETE_RECORD with empty evidence ID
        remed = [s for s in steps if s["phase"] == "REMEDIATION"][0]
        assert remed["resource_id"] == "account_synth_replica_01"
        assert remed["operation"] == "DELETE_RECORD"
        assert remed["state"] == "ABSENT"
        assert remed["evidence_id"] == ""

        # Verification: VERIFY_RECORD_ABSENT with empty evidence ID
        verif = [s for s in steps if s["phase"] == "VERIFICATION"][0]
        assert verif["resource_id"] == "account_synth_replica_01"
        assert verif["operation"] == "VERIFY_RECORD_ABSENT"
        assert verif["state"] == "ABSENT"
        assert verif["evidence_id"] == ""


def test_synthetic_case_active_sync_resurrection():
    """Synthetic Case 2: Primary deletion reported complete but active sync connector may recreate data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ds_dir = _create_synthetic_environment(tmpdir)
        out_csv = os.path.join(tmpdir, "output.csv")

        req = _make_request(
            case_id="case_synth_02",
            email="synth.sync@example.org",
            req_time="2026-09-01T09:00:00Z",
            rep_time="2026-09-05T10:00:00Z",
            aud_time="2026-09-15T12:00:00Z",
            text="Please delete my account and ensure no background services sync my information.",
        )

        res = run_integrated_pipeline(data_dir=ds_dir, output_path=out_csv, requests=[req])
        results = res["results"]
        assert len(results) == 1
        r0 = results[0]

        # Expected: INCOMPLETE due to active sync data flow
        assert r0["deletion_status"] == "INCOMPLETE"
        steps = json.loads(r0["steps_json"])

        # Finding: REPORT_ACTIVE_DATA_FLOW
        finding = [s for s in steps if s["phase"] == "FINDING" and s["operation"] == "REPORT_ACTIVE_DATA_FLOW"]
        assert len(finding) >= 1
        f0 = finding[0]
        assert f0["resource_id"] == "data_flow_synth_202"
        assert f0["state"] == "ACTIVE"
        assert f0["evidence_id"] == "evidence_connector_json"

        # Remediation: DISABLE_DATA_FLOW
        remed = [s for s in steps if s["phase"] == "REMEDIATION" and s["operation"] == "DISABLE_DATA_FLOW"]
        assert len(remed) >= 1
        assert remed[0]["resource_id"] == "data_flow_synth_202"
        assert remed[0]["state"] == "DISABLED"
        assert remed[0]["evidence_id"] == ""

        # Verification: VERIFY_DATA_FLOW_DISABLED
        verif = [s for s in steps if s["phase"] == "VERIFICATION" and s["operation"] == "VERIFY_DATA_FLOW_DISABLED"]
        assert len(verif) >= 1
        assert verif[0]["resource_id"] == "data_flow_synth_202"
        assert verif[0]["state"] == "DISABLED"
        assert verif[0]["evidence_id"] == ""


def test_synthetic_case_tombstone_pii_leakage():
    """Synthetic Case 3: Tombstone retains permitted internal ID but exposes prohibited direct PII."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ds_dir = _create_synthetic_environment(tmpdir)
        out_csv = os.path.join(tmpdir, "output.csv")

        req = _make_request(
            case_id="case_synth_03",
            email="synth.tombstone@example.org",
            req_time="2026-09-01T09:00:00Z",
            rep_time="2026-09-05T10:00:00Z",
            aud_time="2026-09-15T12:00:00Z",
            text="I want my personal information deleted. Maintain whatever compliance reference you need.",
        )

        res = run_integrated_pipeline(data_dir=ds_dir, output_path=out_csv, requests=[req])
        results = res["results"]
        assert len(results) == 1
        r0 = results[0]

        # Expected: INCOMPLETE due to exposed PII on tombstone
        assert r0["deletion_status"] == "INCOMPLETE"
        steps = json.loads(r0["steps_json"])

        # Finding: REPORT_EXPOSED_PII on tombstone
        finding = [s for s in steps if s["phase"] == "FINDING" and s["operation"] == "REPORT_EXPOSED_PII"]
        assert len(finding) >= 1
        f0 = finding[0]
        assert f0["resource_id"] == "tombstone_synth_303"
        assert f0["state"] == "PRESENT"
        assert f0["evidence_id"] == "evidence_tombstone_json"

        # Remediation: REDACT_RECORD
        remed = [s for s in steps if s["phase"] == "REMEDIATION" and s["operation"] == "REDACT_RECORD"]
        assert len(remed) >= 1
        assert remed[0]["resource_id"] == "tombstone_synth_303"
        assert remed[0]["state"] == "REDACTED"
        assert remed[0]["evidence_id"] == ""

        # Verification: VERIFY_RECORD_REDACTED
        verif = [s for s in steps if s["phase"] == "VERIFICATION" and s["operation"] == "VERIFY_RECORD_REDACTED"]
        assert len(verif) >= 1
        assert verif[0]["resource_id"] == "tombstone_synth_303"
        assert verif[0]["state"] == "REDACTED"
        assert verif[0]["evidence_id"] == ""
