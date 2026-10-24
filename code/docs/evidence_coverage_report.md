# NullTrace — Evidence Extraction Coverage Report

**Document Version:** 1.0  
**Phase:** Step E.1 Evidence Extraction Expansion and Coverage Tracking  
**Date:** 2026-10-25  

---

## 1. Inventory by Modality

The evidence corpus contains **94 files** mapped in `dataset/evidence_files.csv`. The breakdown by modality is:

| Modality | File Extension | File Count | Source Origins | Extractor Component |
| :--- | :---: | :---: | :--- | :--- |
| **JSON Records** | `.json` | 28 | `records_assurance_snapshot_bundle`, `object_storage` | `JsonRecordExtractor` |
| **Structured Logs** | `.log` | 26 | `central_observability_export`, `search_index_service` | `LogRecordExtractor` |
| **SQL Snapshots** | `.sql` | 24 | `customer_data_read_replica_capture`, `customer_data_primary`, `failover_replica` | `SqlSnapshotExtractor` |
| **Admin Screenshots** | `.png` | 11 | `account_admin_portal`, `search_index_admin`, `integration_admin`, `backup_service`, etc. | Vision Model Adapter (Pending Step J) |
| **PDF Documents** | `.pdf` | 4 | `account_history_service`, `legal_compliance`, `security_operations` | `PdfDocumentExtractor` (using `pypdf`) |
| **Plain Text** | `.txt` | 1 | `customer_account_service` (Shift handover) | `PlainTextExtractor` |
| **Total** | | **94** | | |

---

## 2. Extraction Results & File-Level Parsing Status

Executing `CorpusCoverageTracker.extract_corpus()` yields the following extraction outcomes:

| Coverage Status | Count | Description |
| :--- | :---: | :--- |
| **`PARSED_WITH_OBSERVATIONS`** | 45 | Files successfully parsed with grounded observations extracted (SQL, logs, records, text, PDF). |
| **`PARSED_NO_RELEVANT_OBSERVATIONS`** | 38 | Files successfully parsed, but containing no relevant subject/resource rows (or general background metrics). |
| **`REQUIRES_OCR`** | 11 | The 11 administrative console screenshots (`.png`) that require visual interpretation. |
| **`UNREADABLE`** | 0 | Zero files were unreadable or corrupt. |
| **`PARSER_ERROR`** | 0 | Zero parsing errors encountered across all 94 files. |
| **Total Files** | **94** | |

### Observations Extracted by Modality:
- **Relational SQL Snapshots:** 969 direct observations (customer profiles, primary/replica comparisons, tombstones, audit events).
- **Structured Event Logs:** 651 observations (lookup completions, active flow events, 404/200 HTTP statuses).
- **JSON Snapshot Bundles:** 485 observations (operational histories, connector configs, backup catalogs, tombstones).
- **Plain-Text Handover:** 41 observations (shift handover verified account checks).
- **PDF Documents:** 7 observations (account statements, tax compliance records).
- **Total Factual Observations Extracted:** **2,153 observations**.

---

## 3. Extraction Limitations

1. **SQL Relational Snapshot Scoping:**
   - Database tables are SQLite-compatible point-in-time exports. Some tables contain raw JSON columns (`record_json`) requiring embedded JSON schema unpacking.
   - Tables without declared foreign keys cannot have relational linkage inferred from coincidental text matches.
2. **Log Record Distinctions:**
   - Log entries capture operations in flight. While `profile_lookup_completed` with `rows="0"` or `http_status="404"` factually confirms absence, events like `export_started` or `profile_lookup_started` are logged claims that do not establish operational success.
3. **PDF Text Extraction:**
   - Text extracted via `pypdf` provides statement reference numbers, order timelines, and customer identifiers, but lacks layout structure. Pages with minimal text are flagged for OCR.
4. **Administrative Console Screenshots:**
   - Local OCR is unavailable. Administrative dashboards with UI toggles, color-coded badges, and complex grid tables require multimodal vision interpretation.

---

## 4. Case-Level Coverage Limitations

- **No Proof of Absence from Unmatched Parsed Files:** A successfully parsed file with no matching subject identifier is **NOT** proof that the subject's data has been deleted across the platform.
- **Corpus Incompleteness Guard:** Because the 11 administrative console screenshots have not yet been processed by a vision model, no deletion request case can legitimately claim 100% corpus inspection completeness.
- **Fail-Closed Assurance:** `CaseCoverageResult.is_fully_covered` strictly returns `False` whenever uninspected modalities remain, preventing any premature or ungrounded `COMPLETE` determination.

---

## 5. Remaining Vision-Extraction Requirements

1. Implement the vision extraction caching and invocation pipeline adhering to `code/docs/vision_extraction_readiness.md`.
2. Extract the 11 administrative console screenshots into structured JSON observations.
3. Cross-reference vision-extracted identifiers against the subject universe (`user_identities.csv`).
4. Record full token usage and costs for `evaluation/usage_report.md`.

---

## 6. Tests Executed

Unit tests in `code/tests/test_evidence_extraction.py`:
1. SQL snapshots with and without declared foreign keys.
2. Source provenance preservation (source file, table name, row index).
3. Ambiguous records that do not establish valid relationships.
4. Log events with timestamps distinguishing observed outcomes from uncorroborated claims.
5. PDFs with text extraction vs empty pages requiring OCR.
6. Parsed files with zero relevant observations (`PARSED_NO_RELEVANT_OBSERVATIONS`).
7. Parser errors and unreadable file handling (`UNREADABLE`, `PARSER_ERROR`).
8. Deterministic repeated extraction.
9. Coverage gaps preventing false claims of complete corpus inspection.
10. Isolation check confirming `dataset/sample_output.csv` is never accessed in extraction code.
