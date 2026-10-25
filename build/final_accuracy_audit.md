# NullTrace — Step N: Final Accuracy Audit Report

**Date:** 2026-10-25  
**Harness / Tool:** antigravity-ide  
**Model:** Gemini 3.8 Flash (Medium)  
**Execution Mode:** Deterministic Offline Execution (`DECISION: MODEL_OFF`, 0 external API calls, 0 network requests, $0.00 spend)  
**Artifact Path:** `build/final_accuracy_audit.md`  

---

## 1. Executive Summary and Baseline Verification

In Step N, we conducted the final comprehensive accuracy audit of the NullTrace deletion-audit agent against the official HackerRank Orchestrate challenge requirements (*Ghost Data Still Exists*).

Our objective was to determine how close the current implementation is to maximum achievable accuracy without making unsubstantiated assumptions or compromising correctness.

### Verified System State

| Dimension | Baseline (Start of Step N) | Verified Current State | Notes |
|---|---|---|---|
| **Total Evaluation Requests** | 518 | 518 | Exact match |
| **COMPLETE Cases** | 137 | 137 (26.45%) | Evidence-grounded |
| **INCOMPLETE Cases** | 371 | 371 (71.62%) | Policy violations / unverified |
| **NOT_APPLICABLE Cases** | 10 | 10 (1.93%) | Non-deletion inquiries |
| **Total Steps Emitted** | 1,582 | 1,582 | 0 gaps, consecutively ordered |
| **Average Steps / Request** | 3.05 | 3.05 | Consistent |
| **Automated Tests Passing** | 152 passed | **153 passed** | 100% in 20.14s |
| **Validation Failures** | 0 | **0** | Ops validator clean |
| **Root `output.csv` Match** | Verified | **Byte-for-byte verified** | SHA-256 identical |
| **`code.zip` Archive** | Packaged | **Re-packaged & Verified** | 83 files, 343 KB |
| **External API Spend** | $0.00 | **$0.00** | Strict `MODEL_OFF` |

---

## 2. Requirement-by-Requirement Compliance Matrix

Every applicable requirement from `problem_statement.md` and `AGENTS.md` was audited:

| Requirement | Responsible Component | Regression Coverage | Compliance Status | Audit Finding |
|---|---|---|---|---|
| **Output File & Schema** | `code/src/grader_io.py:write_output_csv` | `test_contract_roundtrip.py`, `test_validator.py` | **Fully Verified** | Exactly 518 data rows sorted by `case_id`, exact columns `case_id,deletion_status,steps_json`. |
| **Allowed Status Values** | `code/src/completion_validator.py` | `test_validator.py:test_invalid_status_rejected` | **Fully Verified** | Only `COMPLETE`, `INCOMPLETE`, and `NOT_APPLICABLE` emitted. |
| **NOT_APPLICABLE Semantics** | `code/src/pipeline.py:is_non_deletion_inquiry` | `test_pipeline.py`, `test_synthetic_pipeline_cases.py` | **Fully Verified** | Non-deletion inquiries emit `steps_json = []`. |
| **COMPLETE Criteria** | `code/src/completion_validator.py:validate_case_completion` | `test_completion_validator.py` (14 tests) | **Fully Verified** | 10 strict criteria enforced. Verification-only steps citing real evidence proving state at `audit_at`. |
| **INCOMPLETE Planning** | `code/src/planner.py:plan_case` | `test_planner.py` (10 tests) | **Fully Verified** | Emits findings (citing evidence), complete remediation plan (`evidence_id: ""`), and future verification (`evidence_id: ""`). |
| **Phase & Operation Sequence** | `code/src/ops.py:sort_steps` | `test_validator.py` (22 tests) | **Fully Verified** | Strictly ordered `FINDING` $\rightarrow$ `REMEDIATION` $\rightarrow$ `VERIFICATION`. Secondary sort: spec table order $\rightarrow$ `system_id` $\rightarrow$ `resource_id`. Step numbers consecutive from 1. |
| **Evidence Citations** | `code/src/completion_validator.py`, `code/src/planner.py` | `test_validator.py`, `test_evidence_intelligence.py` | **Fully Verified** | All cited evidence IDs match known `file_id`, `activity_id`, or `audit_id`. Zero future/inferred IDs cited in findings. |
| **Account Tombstones** | `code/src/rule_engine.py:assess_resource_policy` | `test_state_and_rules.py`, `test_synthetic_pipeline_cases.py` | **Fully Verified** | Permitted stable `user_id` preserved while requiring redaction of direct identifiers (name, email, phone, hash). |
| **Temporal Isolation** | `code/src/state_reconstruction.py:reconstruct_resource_state` | `test_state_and_rules.py` | **Fully Verified** | Events after `audit_at` isolated; never used as proof of earlier state. |
| **Resurrection & Restore Risks** | `code/src/resurrection_detector.py` | `test_resurrection_detector.py` (7 tests) | **Fully Verified** | Graph traces active sync connectors and restore risks; mitigations prioritized before record actions. |
| **Multi-Modality Ingestion** | `code/src/evidence_extraction.py` | `test_evidence_extraction.py`, `test_local_vision.py` | **Fully Verified** | Ingests SQL snapshots, multi-service JSON, structured logs, PDFs, and local OCR screenshots. |
| **Packaging & Deliverables** | `code.zip`, `README.md`, `AGENTS.md` | Automated archive inspection | **Fully Verified** | Root `output.csv`, `code.zip` (with `evaluation/` reports), `log.txt` all complete. |

---

## 3. Confirmed Defects Audited and Fixed in Step M / N

1. **`parse_timestamp_to_utc` Datetime Handling (`code/src/state_reconstruction.py`)**:
   - *Defect*: `parse_timestamp_to_utc` failed with `AttributeError: 'datetime.datetime' object has no attribute 'strip'` when passed an already-parsed `datetime` instance (e.g., from pre-loaded models).
   - *Fix*: Added type check `if isinstance(ts_str, datetime): return ensure_utc(ts_str)`.
   - *Regression Test*: Added `test_parse_timestamp_to_utc_supports_datetime_and_iso` in `code/tests/test_state_and_rules.py`.

2. **System ID Normalization (`code/src/pipeline.py`)**:
   - *Defect*: Baseline fallback `get_system_id_for_resource` in `pipeline.py` lacked mappings for `cache_`, `marketing_`, `secondary_`, `telemetry_`, `legal_hold_`, returning `unknown_system`.
   - *Fix*: Standardized `get_system_id_for_resource` to delegate to canonical `get_canonical_system_id` in `code/src/rule_engine.py`.

3. **Entry Point Execution (`code/main.py`)**:
   - *Defect*: Running `python3 code/main.py` directly without subcommands only printed help text, whereas `README.md` and `AGENTS.md` specify it as the executable solution entry point.
   - *Fix*: Configured default execution to run the integrated pipeline and write to `--output` (`./output.csv`).

4. **SQL Snapshot Schema Blindspots (`code/src/evidence_extraction.py`)**:
   - *Defect*: Ignored column names `subject_reference`, `customer_email`, `owner_email`, `requester_email`, `owner_phone`, `requester_phone`, `email_hash` across direct tables, missing 78 observations.
   - *Fix*: Mapped alternative column names in `SqlSnapshotExtractor`. Added table state inference (`restore_allowed = 0` $\rightarrow$ `BLOCKED`, `enabled = 0` $\rightarrow$ `DISABLED`).

5. **Readback Log Verification (`code/src/evidence_extraction.py`)**:
   - *Defect*: Readback log operational results were unparsed.
   - *Fix*: Mapped `result="NOT_FOUND"` $\rightarrow$ `ABSENT`, verifying account deletion where ground-truth readback logs exist.

---

## 4. Empirical Evaluation Against Authorized Ground Truth

Evaluation was performed using the standalone evaluation utility (`code/evaluation/evaluate_predictions.py`) on the 32 authorized sample cases (`case_01` to `case_32`):

### 4.1 Overall Performance Metrics
* **Total Sample Cases**: 32 requests
* **Status Accuracy**: **84.38%** (27 / 32 correct deletion statuses)
* **Macro-F1 Score**: **0.7823**
* **False COMPLETE Rate**: **0.0%** (Zero false positive COMPLETE predictions)

### 4.2 Status Confusion Matrix
The confusion matrix below compares ground truth (rows) against NullTrace predictions (columns):

| True Status \ Predicted | COMPLETE | INCOMPLETE | NOT_APPLICABLE | Total Support |
|:---|:---:|:---:|:---:|:---:|
| **COMPLETE** | **5** | 5 | 0 | 10 |
| **INCOMPLETE** | 0 | **22** | 0 | 22 |
| **NOT_APPLICABLE** | 0 | 0 | **0** | 0 |
| **Total Predicted** | 5 | 27 | 0 | 32 |

### 4.3 Per-Class Precision, Recall, and F1

| Class | Support | TP | FP | FN | Precision | Recall | F1 Score |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **COMPLETE** | 10 | 5 | 0 | 5 | **1.0000 (100%)** | 0.5000 | 0.6667 |
| **INCOMPLETE** | 22 | 22 | 5 | 0 | **0.8148 (81.5%)** | **1.0000 (100%)** | 0.8980 |
| **NOT_APPLICABLE** | 0 | 0 | 0 | 0 | *Undefined* | *Undefined* | *Undefined* |

### 4.4 Step-Level and Sequence Quality Metrics
* **Ground-Truth Steps**: 193 steps across 32 sample cases
* **Predicted Steps**: 115 steps across 32 sample cases
* **Matched Steps (Exact Multiset)**: 64 steps
* **Step Precision**: **55.65%** (64 / 115)
* **Step Recall**: **33.16%** (64 / 193)
* **Step F1 Score**: **41.56%**
* **Field Accuracies (Aligned Positions)**:
  - Phase: **79.09%**
  - Evidence ID: **65.45%**
  - Resource ID: **58.18%**
  - State: **57.27%**
  - Operation: **53.64%**
  - System ID: **51.82%**

---

## 5. Remaining Uncertainty and Limitations

1. **Organizer-Held Ground Truth for Evaluation Cases (`case_33`..`case_550`)**:
   - Ground truth is published only for the 32 sample cases. Full-dataset ground truth is held exclusively by the organizer.
   - The 84.38% status accuracy measured on the 32 sample cases is indicative but does **not** prove 100% accuracy on the full 518 cases.
2. **Missing Evidence Observations (103 cases)**:
   - 103 evaluation cases have no corresponding data records in the participant-visible evidence files.
   - Per the challenge specification ("A lack of findings is not evidence of deletion"), the pipeline safely fails closed to `INCOMPLETE`.
3. **Temporal Proximity vs. Batch Interleaving**:
   - Analysis of 1,466 deletion-worker events proved that multiple unrelated users are interleaved within identical batch timestamps. Speculative temporal correlation without explicit identifier corroboration was rejected to avoid catastrophic cross-user data conflation.

---

## 6. Deliverable Verification & Packaging Summary

### 6.1 Root `output.csv`
- **Path**: `./output.csv`
- **Total Lines**: 519 (518 data rows + 1 header row)
- **Header**: `case_id,deletion_status,steps_json`
- **SHA-256 Checksum**: `788302aaea25bf22e1d84ce376b7450700285712dc356fb1b90ee5fc4927a650`
- **Integrity**: Byte-for-byte identical to `build/nulltrace_integrated.csv`.
- **Validation**: 0 structural errors, 0 schema errors, 0 invalid evidence IDs.

### 6.2 Submission Archive `code.zip`
- **Path**: `./code.zip`
- **Size**: 343,236 bytes
- **Total Entries**: 83 files
- **Required Inclusions**:
  - `code/main.py`: Present
  - `README.md`: Present
  - `AGENTS.md`: Present
  - `evaluation/evaluation_report.md`: Present
  - `evaluation/usage_report.md`: Present
  - `code/evaluation/evaluation_report.md`: Present
  - `code/evaluation/usage_report.md`: Present
  - `code/src/`: All modules present
  - `code/tests/`: All 153 tests present
- **Strict Exclusions**:
  - `dataset/`: 0 files (completely excluded)
  - `.git/`: 0 files (completely excluded)
  - `.env`: 0 files (completely excluded)
  - `__pycache__`: 0 files (completely excluded)

### 6.3 Audit Log `log.txt`
- **Path**: `./log.txt`
- **Session History**: All turns faithfully recorded in accordance with `AGENTS.md` §5.2.
- **Context Verified**: `tool=antigravity-ide`, `model=Gemini 3.8 Flash (Medium)`.

### 6.4 Official Challenge and Submission Link
https://www.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists

---

## 7. Submission Readiness Verdict

NullTrace has completed all verification, diagnostic, accuracy improvement, and packaging phases. All 153 automated tests pass, the output validator reports zero errors, root `output.csv` is synchronized and verified, and `code.zip` satisfies all challenge constraints.

**Submission Status: READY TO SUBMIT**.
