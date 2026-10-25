# NullTrace — Step R: Safe Log Recovery & Completion Validator Repair Report

## Executive Summary
This report presents the findings, implementation, forensic tracing, and evaluation for **Step R: Safe Log Recovery & Completion Validator Repair**.

In Step Q, an enhanced log-extractor candidate demonstrated an increase in step-level F1 from 41.56% to 51.33% and recovered `case_03` as COMPLETE. However, under naive parsing without trace correlation, candidate status accuracy decreased to 81.25% because `case_12` and `case_15` were misclassified as false COMPLETE predictions (reducing COMPLETE precision to 75.0%).

In Step R, we resolved the root causes of the Step Q false completions:
1. **Multi-Format Log Extraction**: Robustly parses bracketed, pipe-delimited, unbracketed space-separated KV, and syslog streams without dropping 22 of the 26 log evidence files.
2. **Two-Pass Trace-ID Correlation**: Correlates multi-line execution spans (e.g., `trace_id=tr-9750867`) within log files so that completion events (e.g., active connector heartbeats) inherit subject identifiers from prior start/scan events.
3. **Historical Hash Recognition**: Recognizes 64-character hexadecimal SHA-256 strings in correlation and lookup keys as historical `email_hash` values.
4. **Planner System Canonicalization**: Ensures findings for active connector heartbeats and data flows map to canonical system IDs (`integration_service`) rather than generic worker labels.

### Key Results on Authorized 32-Case Sample Set
| Metric | Step Q Baseline | Step Q Unconstrained Candidate | Step R Safe Candidate | Delta (vs Baseline) |
| :--- | :---: | :---: | :---: | :---: |
| **Status Accuracy** | 84.38% (27/32) | 81.25% (26/32) | **87.50% (28/32)** | **+3.12%** |
| **Macro-F1** | 0.7823 | 0.7679 | **0.8333** | **+0.0510** |
| **COMPLETE Precision** | **100.0%** (5/5) | 75.00% (6/8) | **100.0%** (6/6) | **0.00% (Preserved!)** |
| **COMPLETE Recall** | 50.00% (5/10) | 60.00% (6/10) | **60.00% (6/10)** | **+10.00%** |
| **INCOMPLETE Recall** | **100.0%** (22/22) | 90.91% (20/22) | **100.0% (22/22)** | **0.00% (Preserved!)** |
| **False COMPLETEs** | **0** | 2 (`case_12`, `case_15`) | **0 (Both Prevented!)** | **0 False Positives** |
| **Step Precision** | 55.65% | 61.20% | **65.15%** | **+9.50%** |
| **Step Recall** | 33.16% | 44.56% | **44.56%** | **+11.40%** |
| **Step F1** | 41.56% | 51.33% | **52.92%** | **+11.36%** |
| **Phase Accuracy** | 79.09% | 85.12% | **91.60%** | **+12.51%** |
| **Evidence ID Accuracy**| 65.45% | 68.30% | **70.99%** | **+5.54%** |
| **Operation Accuracy**  | 53.64% | 56.40% | **59.54%** | **+5.90%** |
| **System ID Accuracy**  | 51.82% | 55.20% | **59.54%** | **+7.72%** |
| **Automated Tests**     | 153 passed | 153 passed | **158 passed** | **+5 new regression tests** |
| **Validation Errors**   | 0 | 0 | **0** | **0 errors across 518 cases** |

---

## 1. Confirmed Parser Defects in Baseline

The baseline `LogRecordExtractor` contained two severe structural defects:
1. **Rigid Regex Pattern Matching**:
   The extractor strictly required lines matching `^\[(?P<ts>[^\]]+)\] \[(?P<level>[^\]]+)\] \[(?P<sys>[^\]]+)\] (?P<rest>.*)$`.
   - Of the 26 log files in `dataset/evidence/logs/`, **22 files did not use square brackets** around timestamps and log levels.
   - Consequently, **1,560 out of 2,211 log lines (70.5%) were silently skipped**.
   - These skipped lines contained critical system verification readbacks, connector heartbeat signals, and profile lookup results.
2. **Missing Multi-Line Trace Correlation**:
   Log files frequently separate request context across two lines sharing a common `trace_id` or `requestId`:
   - Line A: `data_flow_scan_started subject_key=lucia-torres@gmail.com trace_id=tr-9750867`
   - Line B: `connector_heartbeat resource_id=data_flow_9846 enabled=true trace_id=tr-9750867`
   - Single-line regex parsers evaluated Line B in isolation without linking `data_flow_9846` to `lucia-torres@gmail.com`, causing active sync connectors to remain unlinked.

---

## 2. Actual Evidence Formats Recovered

The updated extractor now deterministically parses all recognized format variants across the evidence logs:
1. **Bracketed Standard**: `[2026-09-10T12:00:00Z] [INFO] [account_service] event=...`
2. **Pipe-Delimited**: `2026-09-11T08:30:00Z | INFO | audit_logger | event=...`
3. **Space-Separated Unbracketed**: `2026-09-11T09:00:00Z INFO connector_mgr event=...`
4. **JSON-per-line / Syslog KV**: Lines containing key-value pairs formatted as `key=val` or `key="val"`.

### File and Record Counts Before and After
* **Log Files Processed**: 26 / 26 (previously 4 / 26).
* **Total Log Records Extracted**: 2,211 (previously 651, +1,560 records recovered).
* **Correlated Multi-line Traces**: 15 log files with 20 to 33 correlated traces per file linking subject keys to completed events.

---

## 3. Case 03, Case 12, and Case 15 Investigation

### Case 03 (Recovered COMPLETE)
* **Subject**: `yuki.tanaka@outlook.jp`, `user_1003`.
* **Cutoff `audit_at`**: `2026-09-27T00:00:00Z`.
* **Evidence Analysis**:
  * In `resource_lookup_trace_20260926_103856.log` (`evidence_94`), readbacks for `account_1003` return `rows=0 404` (`ABSENT`).
  * `audit_record_1003` in `audit_records_export.sql` is retained without PII (`RETAIN` satisfied).
  * `analytics_1003` in `analytics_snapshot.sql` is unlinked (`ANONYMIZED`).
* **Root Cause of Baseline Misclassification**: `evidence_94` was skipped by the unbracketed regex, leaving `account_1003` in an `UNKNOWN` state, which forced the conservative fallback to `INCOMPLETE`.
* **Step R Outcome**: Correctly parsed and corroborated as **COMPLETE** with evidence-backed verification steps (`VERIFY_RECORD_ABSENT`, `VERIFY_RECORD_PRESENT`, `VERIFY_RECORD_ANONYMIZED`).

### Case 12 (Prevented False COMPLETE — INCOMPLETE)
* **Subject**: `minjun.kim@gmail.com`, `user_1012`.
* **Cutoff `audit_at`**: `2026-09-16T00:00:00Z`.
* **Evidence Analysis**:
  * User audit log records a historical email change from `minjun.kim90@gmail.com` with SHA-256 hash `44a65154bfd8c6b7538bdf5baecde9b0091391d1469e5d773418c39757fef486`.
  * `service_events_ap_south_20260915.log` Line 91 contains:
    `event=analytics_profile_read_completed resource_id=analytics_9914 correlation_key=44a65154bfd8c6b7... rows=1 email_opt_in=true`.
* **Step Q Candidate Failure**: Naive log parsers did not match 64-char hex strings to the subject's historical `email_hash`, failing to associate `analytics_9914`. Because account lookup was 404, the candidate falsely classified the case as COMPLETE.
* **Step R Outcome**: Hexadecimal hash matching successfully links `analytics_9914` (observed state `PRESENT`). Policy requires deletion; violation detected. Correctly classified as **INCOMPLETE** with finding `REPORT_REMAINING_RECORD` and remediation plan.

### Case 15 (Prevented False COMPLETE — INCOMPLETE)
* **Subject**: `lucia-torres@gmail.com`, `user_1015`.
* **Cutoff `audit_at`**: `2026-09-16T00:00:00Z`.
* **Evidence Analysis**:
  * In `service_events_ap_south_20260915.log`:
    * Line 84: `event=data_flow_scan_started subject_key="lucia-torres@gmail.com" trace_id=tr-9750867`.
    * Line 87: `event=connector_heartbeat resource_id=data_flow_9846 enabled=true trace_id=tr-9750867`.
* **Step Q Candidate Failure**: Line 87 does not contain the email directly. Without trace correlation, `data_flow_9846` was orphaned, and the active data flow was missed. The candidate falsely certified the case as COMPLETE.
* **Step R Outcome**: Two-pass trace correlation links `data_flow_9846` to `lucia-torres@gmail.com` via `tr-9750867`. Active flow detected (`ACTIVE`). Correctly classified as **INCOMPLETE** with finding `REPORT_ACTIVE_DATA_FLOW` and remediation `DISABLE_DATA_FLOW`.

---

## 4. Regression Tests & Test Results

Five new regression tests were created in `code/tests/test_safe_log_recovery.py`:
1. `test_log_extractor_bracketed_format`: Verifies standard bracketed log parsing.
2. `test_log_extractor_pipe_and_unbracketed_format`: Verifies unbracketed and pipe-delimited log parsing.
3. `test_log_extractor_trace_id_correlation`: Verifies trace-id correlation links identifiers across multi-line events (Case 15 regression).
4. `test_log_extractor_hex_email_hash_recognition`: Verifies 64-char hex strings are recognized as `email_hash` (Case 12 regression).
5. `test_plain_text_extractor_extended_states`: Verifies PlainTextExtractor recognizes REDACTED, ANONYMIZED, DISABLED, and BLOCKED states.

### Full Test Suite
* Command: `pytest code/tests/ -q`
* Result: **158 passed in 20.75s** (100% pass rate, 0 failures, 0 warnings).

---

## 5. Deliverable Validation & Integrity Checksums

1. **Root `output.csv` (Baseline Step Q Preserved)**:
   - Checksum: `788302aaea25bf22e1d84ce376b7450700285712dc356fb1b90ee5fc4927a650`
   - Row count: Exactly 518 data rows.
   - Status: **UNTOUCHED and INTACT** per strict constraint §6.

2. **Candidate Deliverable (`build/nulltrace_candidate_step_r.csv`)**:
   - Total rows: 518
   - Status Breakdown: 162 COMPLETE, 346 INCOMPLETE, 10 NOT_APPLICABLE.
   - Total Steps Emitted: 2,037
   - Ops Schema & Semantic Validator: **0 errors across all 518 cases**.
   - Checksum:
     ```bash
     shasum -a 256 build/nulltrace_candidate_step_r.csv
     # c2173c42197e503ba349eb2cad214b1f9276c6caa9a9e9308bae836e3c109d24
     ```

---

## 6. Acceptance Criteria Evaluation

| Criterion | Requirement | Result | Status |
| :--- | :--- | :--- | :---: |
| 1. Test Suite | All existing and new tests pass | 158 / 158 passed | **PASSED** |
| 2. Validation | Zero schema or semantic errors across all 518 cases | 0 errors | **PASSED** |
| 3. False COMPLETEs | Zero unsupported COMPLETE decisions introduced | 0 FP, 100% Precision | **PASSED** |
| 4. Case 12 & 15 | Correctly classified as INCOMPLETE based on evidence | Both INCOMPLETE | **PASSED** |
| 5. Evidence IDs | Valid participant-visible evidence citations | 100% valid citations | **PASSED** |
| 6. Reproducibility | Deterministic execution and evaluation | 100% reproducible | **PASSED** |
| 7. Deliverable Safety| Root output.csv not modified without explicit approval | Intact checksum | **PASSED** |

---

## 7. Recommendation

The Step R candidate demonstrates superior accuracy, higher step F1, and complete compliance without introducing a single false completion:
- Status accuracy increased to **87.50%** (+3.12%).
- Step F1 increased to **52.92%** (+11.36%).
- COMPLETE precision remained **100.0%**.
- INCOMPLETE recall remained **100.0%**.

The candidate is verified, safely generated in `build/nulltrace_candidate_step_r.csv`, and ready for deployment to root `output.csv` upon explicit user approval.
