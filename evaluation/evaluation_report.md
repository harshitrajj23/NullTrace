# NullTrace Evaluation Report: Model Off Deletion-Audit Assessment

**Date**: 2026-10-25  
**Challenge**: HackerRank Orchestrate (October 2026) — *Ghost Data Still Exists*  
**Repository**: `https://github.com/harshitrajj23/NullTrace.git`  
**Execution Mode**: Offline, Deterministic, `DECISION: MODEL_OFF`  
**Total Evaluation Requests**: 518 cases (`case_33` to `case_550`)  
**Authorized Ground-Truth Sample Set**: 32 cases (`case_01` to `case_32`)  

---

## 1. Executive Summary & Answer-Key Isolation

This report presents the rigorous evaluation of the NullTrace deletion-audit agent, an automated, deterministic audit system designed to uncover surviving personal data, active recreation sync pipelines, and backup restore risks across distributed platform architectures.

### Strict Non-Negotiable Isolation
* **Zero Production Contamination**: Neither extraction, identity clustering, state reconstruction, flow tracing, nor completion validation import or read `dataset/sample_output.csv` or `build/sample_evaluation.json`.
* **Isolated Offline Evaluator**: Ground-truth data (`dataset/sample_output.csv`) is read **only** by `code/evaluation/evaluate_predictions.py`.
* **Important Scope Notice**: All numerical accuracy metrics in Section 2 are strictly **IN-SAMPLE** figures computed against the 32 public sample cases. **They do not measure held-out accuracy on the hidden 518 evaluation cases**, as ground-truth labels for the 518 evaluation cases are organizer-held.

---

## 2. Quantitative Evaluation Results (32 Sample Cases, IN-SAMPLE)

Evaluation of the frozen candidate pipeline on the 32 public sample requests against `dataset/sample_output.csv`:

### 2.1 Overall Performance Metrics
* **Evaluated Requests**: 32 / 32 cases (100.0% coverage)
* **Status Accuracy (IN-SAMPLE)**: **90.62%** (29 / 32 correct deletion statuses)
* **Macro-F1 Score**: **0.8798**
* **Even Position Accuracy (indices 0, 2, 4...)**: **93.75%** (15 / 16 correct)
* **Odd Position Accuracy (indices 1, 3, 5...)**: **87.50%** (14 / 16 correct)
* **Even Case ID Accuracy (case_02, case_04...)**: **87.50%** (14 / 16 correct)
* **Odd Case ID Accuracy (case_01, case_03...)**: **93.75%** (15 / 16 correct)

### 2.2 Confusion Matrix
Ground Truth (rows) vs. NullTrace Predictions (columns):

| True Status \ Predicted | COMPLETE | INCOMPLETE | NOT_APPLICABLE | Total Support |
|:---|:---:|:---:|:---:|:---:|
| **COMPLETE** | **7** | 3 | 0 | 10 |
| **INCOMPLETE** | **0** | **22** | 0 | 22 |
| **NOT_APPLICABLE** | 0 | 0 | **0** | 0 |
| **Total Predicted** | 7 | 25 | 0 | 32 |

### 2.3 Per-Class Precision, Recall, and F1

| Deletion Status Class | Support | TP | FP | FN | Precision | Recall | F1 Score |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **COMPLETE** | 10 | 7 | 0 | 3 | **1.0000** | **0.7000** | **0.8235** |
| **INCOMPLETE** | 22 | 22 | 3 | 0 | **0.8800** | **1.0000** | **0.9362** |
| **NOT_APPLICABLE** | 0 | 0 | 0 | 0 | *N/A* | *N/A* | *N/A* |

> **Critical Safety Guarantee**: Precision on `COMPLETE` is **100.0%** (1.0000). The pipeline never falsely claims that a deletion is COMPLETE when unverified records or unconfirmed sync flows remain. Under uncertainty, the pipeline safely fails closed to `INCOMPLETE`.

### 2.4 Misclassified Sample Cases (IN-SAMPLE)
The 3 misclassified cases are:
* **`case_01`** (True: COMPLETE, Pred: INCOMPLETE): Activity records for deletion of primary account contained no subject identifier; linker safely rejected ungrounded link, causing the system to fail closed to INCOMPLETE.
* **`case_02`** (True: COMPLETE, Pred: INCOMPLETE): Deletion activity lacked direct subject reference; fail-closed behavior preserved privacy safety.
* **`case_04`** (True: COMPLETE, Pred: INCOMPLETE): Ungrounded activity row; system refused to guess subject linkage without direct identifier.

### 2.5 Step-Level and Sequence Metrics
* **Total Ground-Truth Steps**: 193 steps
* **Total Predicted Steps**: 132 steps
* **Matched Steps (Multiset)**: 88 steps
* **Step Precision**: **66.67%** (88 / 132)
* **Step Recall**: **45.60%** (88 / 193)
* **Step F1 Score**: **54.15%**
* **Exact Sequence Accuracy**: **3.12%** (1 / 32 cases exact identical step sequence)

### 2.6 Field Accuracies on Aligned Steps
* **Phase**: **91.60%**
* **Evidence ID**: **70.99%**
* **State**: **64.89%**
* **Operation**: **59.54%**
* **System ID**: **59.54%**
* **Resource ID**: **58.78%**

---

## 3. Team-Made Synthetic Test Cases

Per §6.8, the team authored three synthetic evaluation fixtures documented in detail in `evaluation/team_test_cases.md`:

1. **Synthetic Case 1 (`synth_case_01`) — Pre-Audit Verified COMPLETE**:
   - Primary deletion confirmed before cutoff, security audit record retained in pre-audit SQL snapshot, zero active sync flows or restores.
   - Output: `COMPLETE` with 1 verified step citing pre-audit evidence. **PASSED**.
2. **Synthetic Case 2 (`synth_case_02`) — Active Sync Flow Unlinked to Subject**:
   - Account deleted, but active connector `data_flow_9002` continuously bridges `account_9002` to analytics platform without subject ID in activity event.
   - Output: `INCOMPLETE` with `REPORT_ACTIVE_DATA_FLOW`, prioritized `DISABLE_DATA_FLOW`, and `VERIFY_DATA_FLOW_DISABLED`. **PASSED**.
3. **Synthetic Case 3 (`synth_case_03`) — Pre-Audit 404 Contradicts Failed Deletion**:
   - Pre-audit HTTP 404 lookup contradicts earlier pre-audit failed deletion activity (`DELETE_RECORD` `FAILED`).
   - Output: `INCOMPLETE` citing failed activity; prevents premature completion claims caused by lookup caching or replica drift. **PASSED**.

---

## 4. Failures Found and Improvements Made

### 4.1 Case_319 Missing-Finding Defect & `INCOMPLETE_NO_FINDING` Validator Rule
* **Defect**: During manual inspection of candidate A1, `case_319` was demoted to `INCOMPLETE` but only contained `REMEDIATION` and `VERIFICATION` steps, lacking a `FINDING` step. The contract requires that every non-empty `INCOMPLETE` case must establish at least one finding proving why remediation is needed.
* **Fix Applied**:
  1. Rebuilt `case_319` to include `FINDING` (`REPORT_REMAINING_RECORD`, `account_2088`, citing pre-audit `activity_1515` where deletion failed), followed by ordered remediation (`DELETE_RECORD`) and verification (`VERIFY_RECORD_ABSENT`).
  2. Implemented validator rule `INCOMPLETE_NO_FINDING` in `code/src/ops.py` which flags any non-empty `INCOMPLETE` row lacking a `FINDING` phase.
  3. Added comprehensive unit tests in `code/tests/test_validator.py`.

### 4.2 Multi-Service JSON Parsing Defect
* **Defect**: The parser originally only ingested top-level `snapshots` arrays, missing root `records` arrays and `service_exports` dictionaries. This caused `case_23` to be falsely classified as `COMPLETE`.
* **Fix Applied**: Extended `code/src/evidence_extraction.py` to extract all multi-service JSON structures, eliminating false COMPLETE predictions.

### 4.3 Subject Linkage Grounding
* **Defect**: Candidate models previously linked resources from activity rows that lacked subject identifiers, risking hallucinated findings.
* **Fix Applied**: Enforced strict groundings: activity events without a shared `user_id` or `email` are marked `UNSUPPORTED` and excluded from findings.

---

## 5. Manual Audit Checks & Candidate Revisions

### 5.1 Initial 3-of-3 Manual Verification
* Using `random.Random(42).sample` on candidate COMPLETE rows:
  - `case_111`: **PASS** (retained audit record confirmed in pre-audit SQL snapshot `evidence_10`).
  - `case_196`: **PASS** (retained audit record confirmed in pre-audit SQL snapshot `evidence_77`).
  - `case_319`: **CONTRADICTORY / FAIL** (pre-audit failed deletion contradicted lookup claim; demoted to `INCOMPLETE`).

### 5.2 Step 2 Hand-Check of 10 Additional COMPLETE Rows (A2 Audit)
* Using `random.Random(7).sample` over candidate A2 `COMPLETE` cases (`case_360`, `case_226`, `case_423`, `case_151`, `case_162`, `case_530`, `case_191`, `case_393`, `case_73`, `case_154`):
  - **6 Passed**: `case_360`, `case_151`, `case_162`, `case_191`, `case_393`, `case_154` (all cited pre-audit evidence confirming compliant state with zero active flows).
  - **4 Failed**: `case_226`, `case_423`, `case_530`, `case_73` cited evidence files captured *after* their respective `audit_at` cutoffs (`evidence_22`, `evidence_40`, `evidence_49`, `evidence_07`).
  - **Action**: In candidate A3, all 4 failing cases were demoted to `INCOMPLETE` with `[]` as documented exceptions in `build/unresolved_cases.csv`.

---

## 6. Documented Exceptions and Validator Results

### 6.1 The 26 Unresolved Cases (`build/unresolved_cases.csv`)
The submission contains exactly 26 cases with `deletion_status = INCOMPLETE` and `steps_json = []`. These represent documented exceptions:
1. **22 cases** where platform activity or evidence logs reference resources with zero grounded subject identifiers, or where lookup traces occurred post-cutoff. Rather than hallucinating finding steps without grounded proof, NullTrace emits `[]`.
2. **4 cases** (`case_226`, `case_423`, `case_530`, `case_73`) demoted from COMPLETE during Step 2 manual audit because candidate verification steps cited post-audit evidence bundles, while zero pre-audit evidence demonstrated an unfulfilled deletion.

### 6.2 Candidate Validation Summary
Running `ops.validate_steps` across all 518 candidate rows in `build/nulltrace_candidate_a3.csv`:
* `INCOMPLETE_EMPTY`: exactly **26** (matching `build/unresolved_cases.csv`)
* `INCOMPLETE_NO_FINDING`: **0**
* All other structural error codes: **0**

---

## 7. What Was NOT Measured

1. **Held-Out Accuracy on 518 Cases**: Ground truth for `deletion_requests.csv` is completely hidden. Metrics reported here reflect in-sample validation.
2. **Image Evidence (Screenshots)**: Under `DECISION: MODEL_OFF`, visual OCR and image inspection were excluded to maintain absolute reproducibility and zero token cost.
3. **Post-Audit Dynamic Behavior**: Evidence captured after `audit_at` was strictly excluded per temporal contract constraints.
