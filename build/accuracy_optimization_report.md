# NullTrace — Step M: Requirement-Driven Accuracy & Final Deliverables Report

**Date:** 2026-10-25  
**Harness / Tool:** antigravity-ide  
**Model:** Gemini 3.8 Flash (Medium)  
**Execution Mode:** Deterministic Offline Execution (`DECISION: MODEL_OFF`, 0 external API calls, 0 network requests, $0.00 spend)  
**Artifact Path:** `build/accuracy_optimization_report.md`  

---

## 1. Executive Summary

This report documents the completion of **Step M: Requirement-Driven Accuracy & Final Deliverables** for the HackerRank Orchestrate challenge: *Ghost Data Still Exists*.

Our objective was to maximize fidelity and compliance with the official challenge specification across all dimensions—status classification, remediation/verification steps, grounded evidence references, identity resolution, temporal state reconstruction, packaging, and deliverable integrity—without targeting or optimizing for an arbitrary number of `COMPLETE` cases.

### Verified Delivery Metrics

| Dimension | Initial Baseline (Step K/L) | Previous Baseline (Step L Report) | Step M Final Output |
|---|---|---|---|
| **Total Evaluation Cases** | 518 | 518 | **518** |
| **COMPLETE Cases** | 105 (20.3%) | 113 (21.8%) | **137** (26.45%) |
| **INCOMPLETE Cases** | 403 (77.8%) | 395 (76.3%) | **371** (71.62%) |
| **NOT_APPLICABLE Cases** | 10 (1.9%) | 10 (1.9%) | **10** (1.93%) |
| **Total Steps Emitted** | 1,311 | 1,353 | **1,582** |
| **Average Steps / Request** | 2.53 | 2.61 | **3.05** |
| **Automated Tests Passing** | 137 / 137 | 146 / 146 | **152 / 152** (100%) |
| **Structural / Semantic Errors** | 0 | 0 | **0** |
| **Root `output.csv` Status** | Baseline Template | Baseline Template | **Fully Verified & Synchronized** |
| **Packaging `code.zip`** | Not Packaged | Not Packaged | **Validated (83 files, 343 KB)** |
| **Financial / API Spend** | $0.00 | $0.00 | **$0.00** |

---

## 2. Priority 1: Verified Challenge Requirements & Compliance Matrix

Every challenge requirement from `problem_statement.md` and `AGENTS.md` was audited against the current implementation:

### 2.1 Required Output Files & Exact Schema
1. **Specification**: Output file must be `output.csv` at repository root with exact header `case_id,deletion_status,steps_json`. Exactly 518 data rows sorted by `case_id`. No extra columns, trailing commas, or malformed quoting.
2. **Implementation**: Implemented in `code/src/grader_io.py:write_output_csv` and `code/src/pipeline.py`.
3. **Testing**: Tested in `code/tests/test_contract_roundtrip.py` and full validation runner in `code/tests/test_validator.py`.
4. **Compliance Status**: **VERIFIED**. Exactly 518 rows sorted ascending from `case_000` to `case_542`, zero duplicate IDs, exact required columns.

### 2.2 Allowed Status Values
1. **Specification**: `deletion_status` must strictly be one of `COMPLETE`, `INCOMPLETE`, or `NOT_APPLICABLE`.
2. **Implementation**: Enforced in `code/src/completion_validator.py:ValidationDecision` and `code/src/ops.py:validate_steps`.
3. **Testing**: Tested in `code/tests/test_validator.py:test_invalid_status_rejected`.
4. **Compliance Status**: **VERIFIED**. 100% of rows use only permitted status enum values.

### 2.3 Status Decision Rules
1. **Specification**:
   - `NOT_APPLICABLE` for non-deletion requests with `steps_json = []`.
   - `COMPLETE` only when all copies have policy-required treatment, retained records contain only permitted identifiers, retained audit records remain available, and no active sync/restore path can recreate data. Emits only verification steps citing real evidence proving state at `audit_at`.
   - `INCOMPLETE` when data remains or recreation risks exist. Emits findings citing evidence, remediation plan (`evidence_id: ""`), and future verification checks (`evidence_id: ""`).
2. **Implementation**: Implemented in `code/src/completion_validator.py:validate_case_completion` (10 strict criteria) and `code/src/planner.py:plan_case`.
3. **Testing**: Tested in `code/tests/test_completion_validator.py`, `code/tests/test_synthetic_pipeline_cases.py`, and `code/tests/test_evidence_intelligence.py`.
4. **Compliance Status**: **VERIFIED**. Fail-closed semantics strictly enforced.

### 2.4 Required Step Phases, Numbering, Operations, and States
1. **Specification**:
   - `step_no`: 1-indexed, consecutive with 0 gaps.
   - `phase`: strictly `FINDING`, `REMEDIATION`, `VERIFICATION`.
   - Allowed 15 operations and exact states defined in problem statement table.
   - Phase ordering: `FINDING` -> `REMEDIATION` -> `VERIFICATION`.
   - Sorting within phase: spec table operation order, then `system_id` ascending, then `resource_id` ascending.
2. **Implementation**: Implemented in `code/src/ops.py:sort_steps`, `OPERATIONS`, `OPERATION_RANK`, `PHASE_RANK`.
3. **Testing**: Tested in `code/tests/test_validator.py` and `code/tests/test_planner.py`.
4. **Compliance Status**: **VERIFIED**. Automatically applied to all emitted steps.

### 2.5 Evidence Reference Rules
1. **Specification**:
   - `FINDING` steps: must cite a participant-visible `file_id`, `activity_id`, or `audit_id`.
   - `COMPLETE` verification steps: must cite a real `file_id`, `activity_id`, or `audit_id`.
   - `INCOMPLETE` remediation and future verification steps: must have `evidence_id = ""`.
   - Zero citations of organizer-only truth or post-audit evidence.
2. **Implementation**: Implemented in `code/src/completion_validator.py:build_evidence_backed_verification_steps` and `code/src/planner.py:plan_case`.
3. **Testing**: Tested in `code/tests/test_validator.py` and `code/tests/test_evidence_intelligence.py`.
4. **Compliance Status**: **VERIFIED**. All evidence IDs verified against `evidence_files.csv`, `system_activity.csv`, and `user_audit_log.csv`.

### 2.6 Identity & Resource Linkage Rules
1. **Specification**: Reconstruct current and historical identifiers. Match account tombstones (preserve stable internal `user_id`, remove name, email, phone, email hash). Reject ambiguous or conflicting identities.
2. **Implementation**: Implemented in `code/src/identity.py:resolve_all`, `code/src/resource_link.py:check_canonical_account_corroboration`, and `code/src/rule_engine.py:assess_resource_policy`.
3. **Testing**: Tested in `code/tests/test_identity.py`, `code/tests/test_canonical_account_link.py`, and `code/tests/test_evidence_intelligence.py`.
4. **Compliance Status**: **VERIFIED**. Zero cross-user identity conflations.

### 2.7 Temporal & Cross-System Reconstruction
1. **Specification**: Establish state at `audit_at` cutoff. Later events cannot prove earlier state. Prioritize flow and restore disablement before record actions.
2. **Implementation**: Implemented in `code/src/state_reconstruction.py:reconstruct_resource_state` and `code/src/resurrection_detector.py`.
3. **Testing**: Tested in `code/tests/test_state_and_rules.py` and `code/tests/test_resurrection_detector.py`.
4. **Compliance Status**: **VERIFIED**. Events after `audit_at` isolated.

### 2.8 Required Packaging & Deliverables
1. **Specification**: Root `output.csv`, `code.zip` containing runnable solution, prompts, configs, `README.md`, and `evaluation/` folder (`evaluation_report.md` and `usage_report.md`), and `log.txt`.
2. **Implementation**: Packaged via standard zip compressor; reports generated in both `code/evaluation/` and `evaluation/`.
3. **Testing**: Tested via automated archive inspection and schema validation.
4. **Compliance Status**: **VERIFIED**.

---

## 3. Priority 2 & 3: Confirmed Defects Audited and Fixed

### A. Evidence Extraction Blindspots (Fixed in `code/src/evidence_extraction.py`)
- **SQL Alternative Column Mappings**: `SqlSnapshotExtractor` previously looked only for `user_id` and `email`. SQLite tables like `security_audit_records` utilized `subject_reference`, and tables like `backup_restore_entries`, `connector_subscriptions`, `support_records`, and `customer_exports` utilized `customer_email`, `owner_email`, `requester_email`, `owner_phone`, `requester_phone`, and `email_hash`. Added multi-column extraction, recovering 78 grounded observations.
- **Table-Specific State Semantics**: Direct SQLite tables previously defaulted all rows to `ResourceState.PRESENT`. For `backup_restore_entries`, column `restore_allowed` (0/1) now determines `BLOCKED` vs `ACTIVE`. For `connector_subscriptions`, column `enabled` (0/1) determines `DISABLED` vs `ACTIVE`.
- **Log Outcome Verification**: `LogRecordExtractor` previously ignored readback operational results. Readback lines with `result="NOT_FOUND"` now verify `ABSENT` account deletion state.
- **PDF Regex Extension**: Added `data_flow` and `analytics` prefixes to PDF regex scanners.

### B. Identity and Resource Linkage Safety (Verified in `code/src/resource_link.py`)
- Preserved Step L's canonical account derivation (`account_XXX` with leading zero preservation) and strict corroboration safeguards (`check_canonical_account_corroboration`).
- Confirmed that candidate account links with conflicting identifiers are rejected.

### C. Temporal Correlation Safety (Audited & Speculative Window Rejected)
- Audited 1,466 deletion-worker events in `dataset/system_activity.csv`.
- Confirmed that multi-tenant batches contain interleaved, unrelated user records within identical minute windows (e.g., 2026-01-09 contains 7 distinct unrelated accounts in the same batch).
- **Decision**: Rejected speculative temporal correlation without explicit identifier corroboration to prevent cross-user contamination.

### D. Step Ordering and System ID Normalization (Fixed in `code/src/pipeline.py` & `code/src/main.py`)
- Standardized `get_system_id_for_resource` in `code/src/pipeline.py` to delegate to `get_canonical_system_id` from `code/src/rule_engine.py`, ensuring consistent system names across all 15 resource types.
- Enhanced `code/main.py` CLI to support running the full integrated pipeline by default (satisfying the `README.md` and `AGENTS.md` entry point contract).

---

## 4. Source Files Changed & Test Suite Results

### Modified / Created Files
1. `code/src/evidence_extraction.py`: Extended SQL schema column matching, table-specific state inference, log result parsing.
2. `code/src/pipeline.py`: Delegated system ID mapping to canonical rule engine.
3. `code/src/main.py`: Added default integrated pipeline execution and CLI options.
4. `code/evaluation/main.py`: Created standard CLI entry point for evaluation reporting.
5. `code/evaluation/evaluation_report.md` & `code/evaluation/usage_report.md`: Updated with Step M verified metrics.
6. `evaluation/`: Mirrored evaluation and usage reports for submission packaging.
7. `output.csv`: Updated with latest approved predictions (SHA-256 verified).
8. `code.zip`: Generated root submission archive (83 entries, 343 KB).

### Test Suite Results
All 152 automated tests in `code/tests/` pass with zero failures:
- `code/tests/test_evidence_intelligence.py` (6 tests): **PASSED**
- `code/tests/test_canonical_account_link.py` (5 tests): **PASSED**
- `code/tests/test_support_ticket_redaction.py` (4 tests): **PASSED**
- `code/tests/test_synthetic_pipeline_cases.py` (3 tests): **PASSED**
- `code/tests/test_completion_validator.py` (14 tests): **PASSED**
- `code/tests/test_state_and_rules.py` (7 tests): **PASSED**
- `code/tests/test_resurrection_detector.py` (7 tests): **PASSED**
- `code/tests/test_planner.py` (10 tests): **PASSED**
- `code/tests/test_validator.py` (22 tests): **PASSED**
- `code/tests/test_identity.py` (14 tests): **PASSED**
- `code/tests/test_loader.py` (11 tests): **PASSED**
- `code/tests/test_evidence_extraction.py` (12 tests): **PASSED**
- `code/tests/test_local_vision.py` (6 tests): **PASSED**
- `code/tests/test_vision_extraction.py` (8 tests): **PASSED**
- `code/tests/test_pipeline.py` (8 tests): **PASSED**
- `code/tests/test_resource_link.py` (7 tests): **PASSED**
- `code/tests/test_audit_consumption.py` (3 tests): **PASSED**
- `code/tests/test_contract_roundtrip.py` (2 tests): **PASSED**
- `code/tests/test_integration_pipeline.py` (3 tests): **PASSED**

**Full Test Suite Summary:** `152 passed in 20.30s` (0 failures, 0 warnings).

---

## 5. Prediction Distribution & Case Transition Details

### Status Distribution

| Status | Count | Percentage |
|---|---|---|
| **COMPLETE** | 137 | 26.45% |
| **INCOMPLETE** | 371 | 71.62% |
| **NOT_APPLICABLE** | 10 | 1.93% |
| **Total** | 518 | 100.0% |

### Detailed Status Transitions from Baseline
- **25 Newly Verified COMPLETE Cases**:
  - `case_64`, `case_69`, `case_70`, `case_213`, `case_215`, `case_218`, `case_219`, `case_221`, `case_243`, `case_244`, `case_294`, `case_295`, `case_297`, `case_299`, `case_336`, `case_339`, `case_393`, `case_395`, `case_398`, `case_448`, `case_452`, `case_493`, `case_494`, `case_497`, `case_502`.
  - *Evidence Grounding*: In these cases, previously ignored SQL columns or table states proved compliant absence, blocked restore access (`restore_allowed = 0`), disabled data flows (`enabled = 0`), or readback log verification (`result="NOT_FOUND"`).
- **1 COMPLETE $\rightarrow$ INCOMPLETE Safety Correction**:
  - `case_123`.
  - *Evidence Grounding*: In `evidence_22` (`backup_restore_entries`), `backup_8742` had `restore_allowed: 1` at `audit_at`. Previously unparsed, this active restore risk was correctly flagged, preventing an unsupported COMPLETE classification.
- **Net Delta**: +24 COMPLETE cases.

### Breakdown of Remaining 371 INCOMPLETE Cases
1. **Surviving Records / Direct PII (150 cases)**: True policy violations (primary DB records, unredacted support tickets, unpurged exports).
2. **Missing Evidence Observations (103 cases)**: No participant evidence records associated with the subject in supplied evidence.
3. **Active Sync Connectors (49 cases)**: Active data flow pipelines capable of recreating deleted data.
4. **Unknown / Ambiguous Resource States (18 cases)**: Conflicting or uncorroborated claims at `audit_at`.
5. **Missing Verification Snapshots (17 cases)**: Accounts deleted without post-audit verification logs or snapshots.
6. **Active Restore Risks (15 cases)**: Backup restore permissions active without controls.
7. **Missing Retained Audit Records (10 cases)**: Legitimate audit logs required for retention were purged.
8. **Tombstone Direct PII Leaks (4 cases)**: Retained account tombstone retains direct identifiers (name/email/phone).
9. **Multi-Factor Risk Combinations (5 cases)**: Combined flow and restore risks.

---

## 6. Deliverable Verification & Packaging

### 6.1 Root `output.csv`
- **Location**: `./output.csv`
- **Rows**: Exactly 518 data rows + 1 header row (519 lines total).
- **Header**: `case_id,deletion_status,steps_json`
- **SHA-256 Checksum**: `788302aaea25bf22e1d84ce376b7450700285712dc356fb1b90ee5fc4927a650`
- **Integrity**: Byte-for-byte identical to `build/nulltrace_integrated.csv`.
- **Validation**: 0 structural errors, 0 schema errors, 0 invalid evidence IDs.

### 6.2 Submission Archive `code.zip`
- **Location**: `./code.zip`
- **Size**: 343,082 bytes
- **Total Entries**: 83 files
- **Required Inclusions Verified**:
  - `code/main.py`: Present
  - `README.md`: Present
  - `AGENTS.md`: Present
  - `evaluation/evaluation_report.md`: Present
  - `evaluation/usage_report.md`: Present
  - `code/evaluation/evaluation_report.md`: Present
  - `code/evaluation/usage_report.md`: Present
  - `code/src/`: All modules present
  - `code/tests/`: All 152 tests present
- **Strict Exclusions Verified**:
  - `dataset/`: Completely excluded (0 files)
  - `.git/`: Completely excluded (0 files)
  - `.env`: Completely excluded (0 files)
  - `__pycache__`: Completely excluded (0 files)
  - `.pytest_cache`: Completely excluded (0 files)

### 6.3 Audit Log `log.txt`
- **Location**: `./log.txt`
- **Session History**: All turns faithfully recorded in accordance with `AGENTS.md` §5.2.
- **Context Verified**: `tool=antigravity-ide`, `model=Gemini 3.8 Flash (Medium)`.
- **Secrets / Real PII**: 0 logged.

---

## 7. Submission Readiness Assessment

| Deliverable | Requirement | Status | Notes |
|---|---|---|---|
| `output.csv` | Exactly 518 cases, sorted, schema valid | **READY** | Verified with 0 errors |
| `code.zip` | Source, tests, README, evaluation reports | **READY** | 83 files, dataset/ excluded |
| `log.txt` | Per-turn agent interaction transcript | **READY** | Up-to-date with §5.2 format |
| Challenge URL | Official submission link in AGENTS.md §4.1 | **READY** | https://www.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists |

NullTrace is fully verified, self-contained, and ready for submission.
