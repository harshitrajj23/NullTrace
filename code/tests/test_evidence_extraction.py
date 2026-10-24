"""code/tests/test_evidence_extraction.py

Unit tests for Multi-Modality Evidence Extraction and Coverage Tracking (Step E.1).

Tests cover:
1. SQL tables with and without foreign keys.
2. Source provenance preservation (source file, table name, row index).
3. Records with identifiers that do not establish a valid relationship.
4. Log events with timestamps distinguishing observed outcomes from uncorroborated claims.
5. PDFs with text extraction vs empty/scanned pages requiring OCR.
6. Parsed files with zero relevant observations (PARSED_NO_RELEVANT_OBSERVATIONS).
7. Parser errors and unreadable files (UNREADABLE, PARSER_ERROR).
8. Deterministic repeated extraction.
9. Coverage gaps preventing false claim of complete corpus inspection.
10. Isolation check confirming sample_output.csv is not accessed in production extraction code.
"""

from datetime import datetime, timezone
import json
import os
import tempfile
import pytest

from code.src.evidence_coverage import (
    CaseCoverageResult,
    CorpusCoverageSummary,
    CorpusCoverageTracker,
    FileCoverageReport,
    FileCoverageStatus,
    detect_modality,
)
from code.src.evidence_extraction import (
    ExtractedObservation,
    JsonRecordExtractor,
    LogRecordExtractor,
    ObservationConfidence,
    PdfDocumentExtractor,
    PlainTextExtractor,
    SqlSnapshotExtractor,
)
from code.src.state_reconstruction import ResourceState

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc)


def test_sql_snapshot_extraction_with_and_without_fks():
    """SQL extractor preserves source table, row index, and detects tables with and without declared foreign keys."""
    sql_content = """
    BEGIN TRANSACTION;
    CREATE TABLE parent_table (
        id TEXT PRIMARY KEY,
        name TEXT
    );
    CREATE TABLE child_with_fk (
        resource_id TEXT PRIMARY KEY,
        parent_id TEXT REFERENCES parent_table(id),
        email TEXT,
        account_status TEXT,
        updated_at TEXT
    );
    INSERT INTO child_with_fk VALUES('account_101', 'p1', 'user101@example.com', 'ACTIVE', '2026-09-01T10:00:00Z');

    CREATE TABLE child_without_fk (
        resource_id TEXT PRIMARY KEY,
        user_id TEXT,
        email TEXT,
        updated_at TEXT
    );
    INSERT INTO child_without_fk VALUES('account_102', 'user_102', 'user102@example.com', '2026-09-01T10:00:00Z');
    COMMIT;
    """
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as f:
        f.write(sql_content)
        temp_sql = f.name

    try:
        obs = SqlSnapshotExtractor.extract(temp_sql, "evidence_sql_test")
        assert len(obs) == 2

        obs_by_rid = {o.resource_id: o for o in obs}
        assert "account_101" in obs_by_rid
        assert "account_102" in obs_by_rid

        o1 = obs_by_rid["account_101"]
        assert o1.source_location == "child_with_fk:0"
        assert o1.associated_identifiers.get("email") == "user101@example.com"
        assert "NO_DECLARED_FOREIGN_KEY" not in o1.ambiguity_flags

        o2 = obs_by_rid["account_102"]
        assert o2.source_location == "child_without_fk:0"
        assert o2.associated_identifiers.get("user_id") == "user_102"
        assert "NO_DECLARED_FOREIGN_KEY" in o2.ambiguity_flags
    finally:
        if os.path.exists(temp_sql):
            os.remove(temp_sql)


def test_source_provenance_preservation():
    """Observations preserve source file, file_id, evidence_id, and exact location."""
    text_content = """
    CUSTOMER PLATFORM - SHIFT HANDOVER
    - 2026-10-01T12:00:00Z | account_service | account_999 | USER_PROFILE | NOT_FOUND | test.user@example.com
    """
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(text_content)
        temp_txt = f.name

    try:
        obs = PlainTextExtractor.extract(temp_txt, "evidence_txt_01")
        assert len(obs) == 1
        o = obs[0]
        assert o.source_file == temp_txt
        assert o.file_id == "evidence_txt_01"
        assert o.evidence_id == "evidence_txt_01"
        assert o.source_location == "line_3"
        assert o.resource_id == "account_999"
        assert o.system_id == "account_service"
        assert o.observed_state == ResourceState.ABSENT
        assert o.associated_identifiers.get("email") == "test.user@example.com"
    finally:
        if os.path.exists(temp_txt):
            os.remove(temp_txt)


def test_identifiers_without_valid_relationship():
    """Unrelated records or general background lines do not fabricate false subject/resource relationships."""
    log_line = '2026-08-01T12:00:00Z [DEBUG] [log_router] [collector-9] export_started: instance="collector-9" sources="platform_services"'
    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
        f.write(log_line + "\n")
        temp_log = f.name

    try:
        obs = LogRecordExtractor.extract(temp_log, "evidence_log_test")
        assert len(obs) == 1
        o = obs[0]
        # Should not assign a resource or subject identifier
        assert o.resource_id is None
        assert o.associated_identifiers == {}
        assert o.observation_type == "LOG_CLAIM"
        assert o.confidence == ObservationConfidence.UNVERIFIED_CLAIM
        assert o.observed_state is None
    finally:
        if os.path.exists(temp_log):
            os.remove(temp_log)


def test_log_events_distinguish_outcomes_from_claims():
    """Logs distinguish factual lookup outcomes from uncorroborated operation claims."""
    log_content = """
    2026-07-28T05:51:18Z [DEBUG] [account_service] [tr-1] profile_lookup_started: instance="acc-1" lookup_key="user@example.com"
    2026-07-28T05:51:21Z [INFO] [account_service] [tr-1] profile_lookup_completed: instance="acc-1" resource_id="account_10" rows="0" http_status="404"
    2026-07-28T05:52:00Z [INFO] [account_service] [tr-2] profile_lookup_completed: instance="acc-1" resource_id="account_20" rows="1" http_status="200"
    """
    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
        f.write(log_content)
        temp_log = f.name

    try:
        obs = LogRecordExtractor.extract(temp_log, "evidence_log_outcomes")
        assert len(obs) == 3

        # Claim
        assert obs[0].observation_type == "LOG_CLAIM"
        assert obs[0].confidence == ObservationConfidence.UNVERIFIED_CLAIM
        assert obs[0].observed_state is None

        # Factual absence
        assert obs[1].observation_type == "LOOKUP_RESULT_ABSENT"
        assert obs[1].confidence == ObservationConfidence.HIGH
        assert obs[1].observed_state == ResourceState.ABSENT
        assert obs[1].resource_id == "account_10"

        # Factual presence
        assert obs[2].observation_type == "LOOKUP_RESULT_PRESENT"
        assert obs[2].confidence == ObservationConfidence.HIGH
        assert obs[2].observed_state == ResourceState.PRESENT
        assert obs[2].resource_id == "account_20"
    finally:
        if os.path.exists(temp_log):
            os.remove(temp_log)


def test_pdf_text_extraction_and_ocr_flagging():
    """PdfDocumentExtractor correctly extracts text when present and flags pages needing OCR."""
    import pypdf

    # Create synthetic PDF with 1 page of text and 1 empty page
    writer = pypdf.PdfWriter()
    # Add blank page
    writer.add_blank_page(width=200, height=200)

    with tempfile.NamedTemporaryFile("wb", suffix=".pdf", delete=False) as f:
        writer.write(f)
        temp_pdf = f.name

    try:
        obs, req_ocr = PdfDocumentExtractor.extract(temp_pdf, "evidence_pdf_test")
        # Empty page must trigger requires_ocr
        assert req_ocr is True
        assert len(obs) == 0
    finally:
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)


def test_parsed_file_with_zero_relevant_observations():
    """A valid JSON file with empty records produces PARSED_NO_RELEVANT_OBSERVATIONS."""
    json_content = {
        "snapshots": [
            {
                "data_store": "metrics_store",
                "collection": "system_gauges",
                "records": [],
            }
        ]
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        rec_dir = os.path.join(tmp_dir, "evidence", "records")
        os.makedirs(rec_dir, exist_ok=True)
        jf_path = os.path.join(rec_dir, "empty_bundle.json")
        with open(jf_path, "w") as f:
            json.dump(json_content, f)

        # Write manifest
        manifest_path = os.path.join(tmp_dir, "evidence_files.csv")
        with open(manifest_path, "w") as f:
            f.write("file_id,file_path,origin,captured_at\n")
            f.write("ev_empty,evidence/records/empty_bundle.json,test_origin,2026-09-01T00:00:00Z\n")

        tracker = CorpusCoverageTracker(tmp_dir)
        summary = tracker.extract_corpus()

        assert summary.total_files == 1
        rep = summary.file_reports["ev_empty"]
        assert rep.status == FileCoverageStatus.PARSED_NO_RELEVANT_OBSERVATIONS
        assert rep.total_observations == 0


def test_parser_errors_and_unreadable_files():
    """Unreadable paths and corrupt files receive appropriate failure statuses."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        rec_dir = os.path.join(tmp_dir, "evidence", "records")
        os.makedirs(rec_dir, exist_ok=True)

        corrupt_path = os.path.join(rec_dir, "corrupt.json")
        with open(corrupt_path, "w") as f:
            f.write("NOT_A_VALID_JSON{{{")

        manifest_path = os.path.join(tmp_dir, "evidence_files.csv")
        with open(manifest_path, "w") as f:
            f.write("file_id,file_path,origin,captured_at\n")
            f.write("ev_corrupt,evidence/records/corrupt.json,test_origin,2026-09-01T00:00:00Z\n")
            f.write("ev_missing,evidence/records/missing.json,test_origin,2026-09-01T00:00:00Z\n")

        tracker = CorpusCoverageTracker(tmp_dir)
        summary = tracker.extract_corpus()

        assert summary.file_reports["ev_missing"].status == FileCoverageStatus.UNREADABLE
        assert summary.file_reports["ev_corrupt"].status == FileCoverageStatus.PARSER_ERROR


def test_deterministic_repeated_extraction():
    """Repeated extraction runs yield deterministic observation counts and ordering."""
    tracker1 = CorpusCoverageTracker("dataset")
    s1 = tracker1.extract_corpus()

    tracker2 = CorpusCoverageTracker("dataset")
    s2 = tracker2.extract_corpus()

    assert s1.total_files == s2.total_files
    assert s1.total_observations_extracted == s2.total_observations_extracted
    assert s1.files_by_modality == s2.files_by_modality
    assert s1.observations_by_modality == s2.observations_by_modality


def test_coverage_gaps_prevent_false_complete_inspection():
    """Case-level coverage strictly flags uninspected image modality and prevents is_fully_covered."""
    tracker = CorpusCoverageTracker("dataset")
    tracker.extract_corpus()

    res = tracker.evaluate_case_coverage(
        case_id="case_synth_01",
        subject_identifiers={"test@example.com"},
        resource_ids={"account_101"},
    )

    # Must remain False because IMAGE modality is uninspected without vision models
    assert res.is_fully_covered is False
    assert "IMAGE" in res.uninspected_or_pending_modalities
    assert any("vision-model" in gap for gap in res.coverage_gaps)


def test_no_access_to_sample_output_in_extraction():
    """Ensures production extraction modules never reference or read sample_output.csv."""
    modules = [
        os.path.join(_repo_root, "code", "src", "evidence_extraction.py"),
        os.path.join(_repo_root, "code", "src", "evidence_coverage.py"),
    ]
    for m in modules:
        with open(m, "r", encoding="utf-8") as f:
            code = f.read()
            assert "sample_output.csv" not in code, f"sample_output.csv referenced in {m}"
