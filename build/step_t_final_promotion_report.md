# NullTrace — Step T: Approved Candidate Promotion & Final Validation Report

## Executive Summary
This report documents the final verification, baseline backup, promotion, and delivery packaging for the approved Step R/S candidate in the HackerRank Orchestrate (October 2026) challenge, *Ghost Data Still Exists*.

All verification checks have passed unconditionally:
1. **Candidate Provenance & Integrity**: Verified candidate checksum `c2173c42197e503ba349eb2cad214b1f9276c6caa9a9e9308bae836e3c109d24`.
2. **Baseline Preservation**: The verified Step Q baseline is preserved in `build/root_output_backup_step_q.csv` (`788302aaea25bf22e1d84ce376b7450700285712dc356fb1b90ee5fc4927a650`).
3. **Promotion**: Candidate copied to root `output.csv` and verified byte-for-byte identical via binary comparison (`cmp -s`).
4. **Validation**: Zero schema or semantic errors across all 518 cases via `ops.validate_steps`.
5. **Testing**: 158/158 automated unit and regression tests pass (100% pass rate).
6. **Package Integrity**: Rebuilt clean `code.zip` (90 entries, 0 errors, no cache or dataset artifacts).
7. **Zero Cost**: `DECISION: MODEL_OFF` maintained ($0.00 spend, 0 API calls).

---

## 1. Candidate Checksum & Provenance Verification

* **Promoted File**: `build/nulltrace_candidate_step_r.csv`
* **Promoted Target**: Root `output.csv`
* **Promoted SHA-256**: `c2173c42197e503ba349eb2cad214b1f9276c6caa9a9e9308bae836e3c109d24`
* **Recoverable Baseline**: `build/root_output_backup_step_q.csv`
* **Baseline SHA-256**: `788302aaea25bf22e1d84ce376b7450700285712dc356fb1b90ee5fc4927a650`
* **Byte-for-Byte Check**: `cmp -s build/nulltrace_candidate_step_r.csv output.csv` -> **IDENTICAL**

---

## 2. Exact Case Coverage & Ordering

* **Total Lines in `output.csv`**: 519 (1 header row + exactly 518 data rows)
* **Header**: `case_id,deletion_status,steps_json` (exact required order)
* **Unique Case IDs**: Exactly 518 unique IDs
* **Case ID Set**: Exactly matches all 518 IDs from `dataset/deletion_requests.csv`
* **Ordering**: Strictly sorted by `case_id` ascending string order, in full accordance with AGENTS.md §6.3.

---

## 3. Baseline-versus-Candidate Transitions

| Status Transition | Count | Reconciled Cause |
| :--- | :---: | :--- |
| **INCOMPLETE → COMPLETE** | 30 | Multi-format log recovery extracted unbracketed readback logs (404 account lookups, retained audit records without PII) previously missed by rigid regex, establishing deletion completion. |
| **COMPLETE → INCOMPLETE** | 5 | Multi-format log recovery uncovered active data flows (`enabled=true`) and restore candidates previously missed, correcting false complete certifications. |
| **NOT_APPLICABLE Changes** | 0 | Non-deletion inquiry identification remained 100% stable. |
| **Total Status Changes** | **35** | Net change: `137 + 30 - 5 = 162 COMPLETE` |

---

## 4. Final Status Distribution & Emitted Steps

| Deletion Status | Count | Percentage |
| :--- | :---: | :---: |
| **INCOMPLETE** | 346 | 66.80% |
| **COMPLETE** | 162 | 31.27% |
| **NOT_APPLICABLE** | 10 | 1.93% |
| **Total Cases** | **518** | **100.00%** |

* **Total Emitted Steps in `output.csv`**: 2,037 steps
  - `FINDING` steps: 777
  - `REMEDIATION` steps: 601
  - `VERIFICATION` steps: 659
  - Average steps per deletion case: 4.01

---

## 5. Grader Contract & Semantic Validation

All 518 cases in promoted `output.csv` were verified with `code/src/ops.py:validate_steps`:
- **Validation Failures**: **0**
- **Phase Ordering**: Strictly `FINDING` → `REMEDIATION` → `VERIFICATION`
- **Step Numbering**: Strictly consecutive from 1 per case
- **Grammar & State**: 100% compliant operation/state pairings
- **Evidence IDs**: Every cited evidence ID is a valid participant-visible identifier in `evidence_files.csv`, `system_activity.csv`, or `user_audit_log.csv`. Zero uncorroborated, post-audit, or placeholder IDs.

---

## 6. Automated Test Suite Results

* **Command**: `pytest code/tests/ -q`
* **Total Tests**: 158
* **Passed**: **158**
* **Failed**: 0
* **Execution Time**: 21.26s

---

## 7. Authorized Public-Sample Evaluation Metrics

Evaluated independently against `dataset/sample_output.csv` on the 32 public sample cases under strict Answer-Key Isolation:

* **Overall Status Accuracy**: **87.50% (28/32)** (Baseline: 84.38%, +3.12% gain)
* **Macro-F1**: **0.8333** (Baseline: 0.7823, +0.051 gain)
* **COMPLETE Precision**: **100.0% (6/6)** (0 false COMPLETE predictions)
* **COMPLETE Recall**: **60.0% (6/10)** (recovered `case_03`)
* **INCOMPLETE Recall**: **100.0% (22/22)** (`case_12` and `case_15` correctly kept INCOMPLETE)
* **Step Precision**: **65.15% (86/132)** (Baseline: 55.65%, +9.50% gain)
* **Step Recall**: **44.56% (86/193)** (Baseline: 33.16%, +11.40% gain)
* **Step F1**: **52.92%** (Baseline: 41.56%, +11.36% gain)
* **Exact Sequence Accuracy**: **3.12% (1/32)** (Baseline: 3.12%)
* **Field Accuracies**:
  - Phase: 91.60%
  - Evidence ID: 70.99%
  - State: 64.89%
  - Operation: 59.54%
  - System ID: 59.54%
  - Resource ID: 58.78%

*Scope Note*: These metrics reflect measured accuracy on the 32 public sample requests. Because ground-truth labels for evaluation requests (`case_33`..`case_550`) are organizer-held, full-dataset accuracy cannot be stated as 100% without authorized ground-truth labels.

---

## 8. Final Submission Deliverables & Archive Integrity

| Artifact | Location | Checksum / Size | Status |
| :--- | :--- | :--- | :---: |
| **Predictions** | `output.csv` | SHA-256: `c2173c42197e503ba349eb2cad214b1f9276c6caa9a9e9308bae836e3c109d24` | **PROMOTED & VERIFIED** |
| **Code Package** | `code.zip` | 90 entries, 334,449 bytes compressed (0 errors) | **REBUILT & VERIFIED** |
| **Transcript** | `log.txt` | Complete per-turn audit log with required metadata | **UPDATED & VERIFIED** |
| **Baseline Backup** | `build/root_output_backup_step_q.csv` | SHA-256: `788302aaea25bf22e1d84ce376b7450700285712dc356fb1b90ee5fc4927a650` | **SAFELY PRESERVED** |

### Submission URL
Per AGENTS.md §4.1:
https://www.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists

---

## 9. Final Promotion Recommendation: **COMPLETE & READY FOR SUBMISSION**
All promotion criteria, safety gates, validator checks, and package requirements are satisfied. There are zero remaining blockers.
