# NullTrace Final Submission Readiness Report

**Challenge**: HackerRank Orchestrate (October 2026) — *Ghost Data Still Exists*  
**Step**: FINAL — Candidate Verification & Readiness Audit  
**Mode**: `DECISION: MODEL_OFF` ($0.00 cost, zero external API calls, 100% deterministic local execution)  
**Status**: Submission Candidate Verified; Promotion to root `output.csv` Pending Explicit User Instruction  
**Timestamp**: 2026-10-25T09:17:00+05:30  

---

## 1. File Integrity & SHA-256 Checksums

The submission candidate `build/nulltrace_final.csv` is an exact, unedited copy of `build/nulltrace_step_z3.csv`. The approved root `output.csv` remains unpromoted and untampered:

| File | SHA-256 Checksum | Verification Status |
| :--- | :--- | :--- |
| `output.csv` (Root Baseline) | `c2173c42197e503ba349eb2cad214b1f9276c6caa9a9e9308bae836e3c109d24` | **Untouched / Preserved** |
| `build/nulltrace_final.csv` | `5e8b0175360887114a25381628814136fe0f349e7189aeefc2aaf0f519e72445` | **Final Candidate (Verified)** |
| `build/nulltrace_step_z3.csv` | `5e8b0175360887114a25381628814136fe0f349e7189aeefc2aaf0f519e72445` | Identical to final candidate |
| `build/unresolved_cases.csv` | `fd2c9af983cf54fe6f5236eb155fdc7dc2c4a37171d403b71366247d9ae2157a` | Documentation of 22 open cases |

---

## 2. Row Structure & Status Counts

Validation of `build/nulltrace_final.csv`:
- **Total Data Rows**: Exactly **518** rows (plus 1 header line: `case_id,deletion_status,steps_json`).
- **Sorting**: Strictly ordered by `case_id` ascending with zero duplicates; 100% bijective match against `dataset/deletion_requests.csv`.
- **JSON Conformance**: Every row parses as valid JSON; consecutive 1-indexed `step_no`; strict phase progression (`FINDING` -> `REMEDIATION` -> `VERIFICATION`); grammar-validated operation/state pairs.
- **Evidence Field Invariants**: Every `REMEDIATION` and `VERIFICATION` step in `INCOMPLETE` rows has `evidence_id = ""`. Every `FINDING` and `COMPLETE` verification step cites valid non-empty evidence.
- **NOT_APPLICABLE Invariants**: All 10 non-deletion inquiry rows have `steps_json = []`.

### Deletion Status Breakdown:
| Deletion Status | Count | Percentage |
| :--- | :---: | :---: |
| **`COMPLETE`** | 162 | 31.27% |
| **`INCOMPLETE`** | 346 | 66.80% |
| **`NOT_APPLICABLE`** | 10 | 1.93% |
| **Total Cases** | **518** | **100.0%** |

*Emitted Step Counts*: 590 `FINDING`, 590 `REMEDIATION`, 869 `VERIFICATION` = **2,049 total steps**.

---

## 3. Validator Results

Executing `validate_steps` (with newly implemented `INCOMPLETE_EMPTY` enforcement) across all 518 rows of `build/nulltrace_final.csv`:
- **Total Cases Evaluated**: 518
- **Cases with 0 Validation Errors**: **496**
- **Cases with `INCOMPLETE_EMPTY` Error**: **22** (100% match with `build/unresolved_cases.csv`)
- **Other Errors (Grammar, Phase, Numbering, Unknown Evidence)**: **0**

---

## 4. Spot-Check of 10 COMPLETE Rows (Seed 42)

Ten `COMPLETE` cases were randomly selected using fixed `seed=42`. Every cited `evidence_id` and resource was verified via direct inspection and `grep` in `dataset/evidence_files.csv`, evidence artifacts, and `dataset/system_activity.csv`:

| Case ID | Verified Steps | Evidence ID & File Path | Resource Grounding (Grep / Line) | Verdict |
| :--- | :--- | :--- | :--- | :---: |
| `case_111` | `VERIFY_RECORD_PRESENT` (`audit_record_8933`, PRESENT) | `evidence_10` (`customer_data_read_replica_20260827.sql`) | Line 28: `audit_record_8933` | **PASS** |
| `case_178` | `VERIFY_RECORD_PRESENT` (`audit_record_8521`, PRESENT) | `evidence_17` (`customer_data_snapshot_bundle_20260725.json`) | Line 343: `audit_record_8521` | **PASS** |
| `case_193` | 1. `VERIFY_RECORD_ABSENT` (`account_1065`, ABSENT)<br>2. `VERIFY_RECORD_PRESENT` (`audit_record_1839`, PRESENT) | `evidence_82` (`resource_lookup_trace_20260713_093359.log`) | Line 28: `account_1065`<br>Line 38: `audit_record_1839` | **PASS** |
| `case_196` | 1. `VERIFY_RECORD_ABSENT` (`account_5599`, ABSENT)<br>2. `VERIFY_RECORD_PRESENT` (`audit_record_6389`, PRESENT) | `evidence_82` (`resource_lookup_trace_20260713_093359.log`) | Line 12: `account_5599`<br>Line 36: `audit_record_6389` | **PASS** |
| `case_215` | 1. `VERIFY_RECORD_ABSENT` (`account_1956`, ABSENT)<br>2. `VERIFY_RECORD_PRESENT` (`audit_record_1718`, PRESENT) | `evidence_21` (`operations_stream_eu_central_20260705.log`) | Line 20: `account_1956`<br>Line 8: `audit_record_1718` | **PASS** |
| `case_276` | `VERIFY_RECORD_PRESENT` (`audit_record_8323`, PRESENT) | `evidence_26` (`customer_data_snapshot_bundle_20260605.json`) | Line 290: `audit_record_8323` | **PASS** |
| `case_295` | `VERIFY_RECORD_PRESENT` (`audit_record_1269`, PRESENT) | `evidence_75` (`customer_data_inventory_20260524.sql`) | Line 37: `audit_record_1269` | **PASS** |
| `case_319` | 1. `VERIFY_RECORD_ABSENT` (`account_2088`, ABSENT)<br>2. `VERIFY_RECORD_PRESENT` (`audit_record_7337`, PRESENT) | `evidence_30` (`service_events_sa_east_20260516.log`) | Line 92: `account_2088`<br>Line 97: `audit_record_7337` | **PASS** |
| `case_524` | `VERIFY_RECORD_PRESENT` (`audit_record_5429`, PRESENT) | `evidence_49` (`customer_data_snapshot_bundle_20260131.json`) | Line 315: `audit_record_5429` | **PASS** |
| `case_70` | 1. `VERIFY_RECORD_ABSENT` (`account_6633`, ABSENT)<br>2. `VERIFY_RECORD_PRESENT` (`audit_record_1738`, PRESENT) | `evidence_06` (`structured_service_events_eu_west_20260918.log`) | Line 4: `account_6633`<br>Line 20: `audit_record_1738` | **PASS** |

**Summary**: 10 out of 10 cases (**100%**) passed independent spot-check verification.

---

## 5. List of 22 Known Violations (`INCOMPLETE_EMPTY`)

The following 22 cases are preserved as `steps_json = []` by conscious design decision. Attributing uncorroborated resources from activity entries lacking subject identifiers or post-audit records would constitute hallucinated evidence:

| Case ID | Root Cause / Reason for Leaving as [] | Category |
|---|---|---|
| `case_127` | activity_3113 mentions account_6805 with zero subject identifiers; snapshot is post-audit cutoff | Unsupported Activity (No Subject ID) |
| `case_168` | activity_2811 mentions export_4102 with zero subject identifiers | Unsupported Activity (No Subject ID) |
| `case_170` | search_3619 trace log is post-audit cutoff; no pre-audit evidence exists | Post-Audit Activity Only |
| `case_175` | activity_2642 mentions account_246 with zero subject identifiers | Unsupported Activity (No Subject ID) |
| `case_264` | activity_2116, 2117, 2118 mention support_9996, data_flow_4885, backup_3250 with zero subject identifiers | Unsupported Activity (No Subject ID) |
| `case_288` | activity_1909 mentions export_7906 with zero subject identifiers | Unsupported Activity (No Subject ID) |
| `case_292` | activity_1848 mentions backup_1825 with zero subject identifiers | Unsupported Activity (No Subject ID) |
| `case_345` | account_343 activity (activity_2093) is post-audit cutoff; no pre-audit evidence exists | Post-Audit Activity Only |
| `case_372` | activity_1239 mentions export_5081 with zero subject identifiers | Unsupported Activity (No Subject ID) |
| `case_408` | account_406 activity (activity_3055) is post-audit cutoff; no pre-audit evidence exists | Post-Audit Activity Only |
| `case_412` | account_410 activity (activity_3662) is post-audit cutoff; no pre-audit evidence exists | Post-Audit Activity Only |
| `case_413` | activity_858 mentions analytics_4523 with zero subject identifiers | Unsupported Activity (No Subject ID) |
| `case_414` | activity_859 mentions support_3768 with zero subject identifiers | Unsupported Activity (No Subject ID) |
| `case_416` | Keiko Sato: zero resources in activity or evidence (only ephemeral debug lookup logs with resource_id=None) | Ephemeral Logs Only (No Resources) |
| `case_417` | Soo-jin Kim: zero resources in activity or evidence (only ephemeral debug lookup logs with resource_id=None) | Ephemeral Logs Only (No Resources) |
| `case_418` | activity_815 mentions support_9464 with zero subject identifiers | Unsupported Activity (No Subject ID) |
| `case_420` | activity_753 mentions export_389 with zero subject identifiers | Unsupported Activity (No Subject ID) |
| `case_44` | activity_3856 mentions backup_6266 with zero subject identifiers | Unsupported Activity (No Subject ID) |
| `case_51` | activity_3738 mentions backup_7809 with zero subject identifiers | Unsupported Activity (No Subject ID) |
| `case_520` | activity_50 mentions support_9251 with zero subject identifiers | Unsupported Activity (No Subject ID) |
| `case_522` | activity_296 mentions support_8538 with zero subject identifiers | Unsupported Activity (No Subject ID) |
| `case_60` | account_058 activity (activity_3966) is post-audit cutoff; no pre-audit evidence exists | Post-Audit Activity Only |

---

## 6. 32-Case Sample Accuracy (In-Sample Benchmark)

The 32 public requests in `dataset/sample_deletion_requests.csv` serve as an in-sample reference benchmark (evaluation requests `case_33` to `case_550` are strictly out-of-sample):

* **Baseline Metric (Step R)**:
  * Accuracy: **28 / 32 (87.50%)**
  * Macro-F1: **0.8333**
  * COMPLETE Precision: **100.0%** (0 false positives)
  * COMPLETE Recall: **60.0%** (6/10 detected)
  * Step-level F1: **52.92%**
* **With Tombstone Resolution Rule (Step V / Step Y)**:
  * Accuracy: **29 / 32 (90.62%)** via compliant tombstone resolution on `case_31` (`tombstone_440` in `evidence_15`)
  * Macro-F1: **0.8750**
  * COMPLETE Precision: **100.0%**
  * COMPLETE Recall: **70.0%** (7/10 detected)
  * INCOMPLETE Recall: **100.0%** (22/22 detected)

---

## 7. Model Execution & Architectural Disclosure

- **Model Execution Policy**: Confirmed `DECISION: MODEL_OFF` across all pipeline steps. Zero external AI or LLM API calls were made. Total inference cost is **$0.00**.
- **Model Attribution Clarification**: Previous audit logs containing references to "Gemini" reflected the coding agent harness runtime environment (`antigravity-ide`) rather than pipeline model inference calls. The NullTrace deletion-audit agent executes 100% deterministic local Python algorithms.
- **Production Isolation**: Re-verified that production modules (`code/src/` and `code/main.py`) contain **0 hits** for `sample_output.csv` and `sample_evaluation.json`.
