# NullTrace — Step Q: Forensic Error Analysis & Targeted Accuracy Report

## Executive Summary
This report presents the complete forensic investigation, baseline reproduction, trace analysis, and accuracy audit of NullTrace for the HackerRank Orchestrate October 2026 challenge, *Ghost Data Still Exists*.

Under strict Answer-Key Isolation (never reading `dataset/sample_output.csv` to generate predictions or tune rules), we reproduced the authorized evaluation baseline on the 32 public sample cases, forensically traced all 5 misclassified cases (`case_01`, `case_02`, `case_03`, `case_04`, `case_31`), analyzed the pipeline's step-level quality, evaluated candidate fixes, and evaluated the architectural trade-offs between step-level recall and compliance precision.

### Key Findings
1. **Baseline Verified**: The baseline was reproduced exactly: 84.38% status accuracy (27/32), Macro-F1: 78.23%, COMPLETE Precision: 100.0%, INCOMPLETE Recall: 100.0%, Step F1: 41.56%.
2. **Misclassified Cases Discovered**: The actual misclassified sample cases are `case_01`, `case_02`, `case_03`, `case_04`, and `case_31`. `case_05` was already correctly classified as INCOMPLETE.
3. **Confirmed Defect Identified (Evidence Log Parser Dropping 22 of 26 Files)**: `LogRecordExtractor` used rigid regexes that dropped non-bracketed, space-separated key-value logs, syslog lines, and pipe-delimited streams (skipping 1,560 of 2,211 log lines across 22 evidence files). In particular, readback logs in `resource_lookup_trace_20260926_103856.log` (`evidence_94`) proving `case_03`'s deletion was COMPLETE were dropped.
4. **Safety Trade-off Discovered**: Expanding the log parser alone recovers `case_03` and increases Step F1 from 41.56% to 51.33% (+9.77%), but causes `case_12` and `case_15` to become False Positives (falsely certifying incomplete cases as COMPLETE due to undetected active data flows). This lowers overall status accuracy from 84.38% to 81.25% and breaks the 100% COMPLETE precision guarantee.
5. **Final Executive Decision**: Retain the existing validated deliverables (`output.csv` SHA-256 `788302aa...`, `code.zip` 83 entries) to preserve 100% COMPLETE precision, 100% INCOMPLETE recall, zero false compliance certifications, and 153/153 passing unit tests.

---

## 1. Baseline Reproduction

The evaluation baseline was reproduced independently using the standalone evaluator `code/evaluation/evaluate_predictions.py` against `build/sample_predictions.csv`:

* **Git Status**: Clean working directory on branch `main` (`4f154fc4d14111d73f1ebf8b1a699763fc5a0572`).
* **Evaluator Command**:
  ```bash
  python3 code/evaluation/evaluate_predictions.py \
    --predictions build/sample_predictions.csv \
    --ground-truth dataset/sample_output.csv \
    --report-json build/baseline_sample_evaluation_step_q.json
  ```
* **Evaluated Cases**: 32 public sample cases (`case_01` through `case_32`).
* **Status Metrics**:
  * Overall Status Accuracy: **84.38% (27/32)**
  * Macro-F1: **0.7823**
* **Confusion Matrix**:
  | True \ Pred | COMPLETE | INCOMPLETE | NOT_APPLICABLE |
  | :--- | :---: | :---: | :---: |
  | **COMPLETE** | 5 | 5 | 0 |
  | **INCOMPLETE** | 0 | 22 | 0 |
  | **NOT_APPLICABLE** | 0 | 0 | 0 |
* **Per-Class Metrics**:
  * `COMPLETE`: Support = 10, Precision = 1.0000, Recall = 0.5000, F1 = 0.6667
  * `INCOMPLETE`: Support = 22, Precision = 0.8148, Recall = 1.0000, F1 = 0.8980
  * `NOT_APPLICABLE`: Support = 0, Precision = N/A, Recall = N/A, F1 = N/A
* **Step & Sequence Metrics**:
  * Truth Steps: 193
  * Predicted Steps: 115
  * Matched Steps: 64
  * Step Precision: 0.5565
  * Step Recall: 0.3316
  * Step F1: 0.4156
  * Sequence Accuracy: 3.12% (1/32)
* **Field Accuracies**:
  * `phase`: 79.09%
  * `evidence_id`: 65.45%
  * `resource_id`: 58.18%
  * `state`: 57.27%
  * `operation`: 53.64%
  * `system_id`: 51.82%
* **Test Suite**: 153/153 tests passing via `pytest code/tests/ -q` in 21.40s.
* **Root Output Checksum**:
  `788302aaea25bf22e1d84ce376b7450700285712dc356fb1b90ee5fc4927a650` (identical between `output.csv` and `build/nulltrace_integrated.csv`).
* **Preserved Baseline Copy**: `build/baseline_step_q.csv` (SHA-256: `788302aaea25bf22e1d84ce376b7450700285712dc356fb1b90ee5fc4927a650`).

---

## 2. Misclassified Case Traces

The 5 misclassified public cases were identified from the evaluator diagnostics as `case_01`, `case_02`, `case_03`, `case_04`, and `case_31`.

### Case Trace: `case_01`
1. **Input Request**: *"Hi, I haven’t used this account in years and would like it closed. Please remove the profile and the personal details attached to it."* (`email: amina.elmasri@gmail.com`).
2. **Audit Cutoff**: `2026-09-03 11:30:00+00:00`.
3. **Evidence Files**: No files in `dataset/evidence/` contain `user_01`, `amina.elmasri`, `account_001`, or the phone/email hash.
4. **Extracted Observations**: 0 direct evidence observations.
5. **Resource-Linking Decisions**: `account_001` linked via `system_activity.csv` row `activity_3342`.
6. **Reconstructed States**: `account_001` -> `UNKNOWN` (activity `activity_3342: DELETE_RECORD SUCCESS` treated as uncorroborated claim per §6.6).
7. **Required Verification Conditions**: Direct evidence proving record is absent.
8. **Emitted Steps**: `[]` (INCOMPLETE with insufficient evidence).
9. **Final Classification**: `INCOMPLETE` (Truth: `COMPLETE`).
10. **Responsible Code**: `code/src/state_reconstruction.py:reconstruct_resource_state:L415`.
11. **Why Prediction Differs**: Ground truth author accepted `activity_3342` SUCCESS claim without independent corroborating evidence.
12. **Cause Categorization**: **Genuine Evidence Limitation & Strict Rule Enforcement**. Absolute Constraint 11 forbids trusting `reported_result: SUCCESS` alone as proof of deletion.

### Case Trace: `case_02`
1. **Input Request**: *"Intenté eliminar mi cuenta ayer, pero la página terminó mostrando un error. ¿Pueden comprobar si todavía queda algún dato y completar la eliminación si hace falta?"* (`email: mateo.rios@outlook.com`).
2. **Audit Cutoff**: `2026-09-04 15:00:00+00:00`.
3. **Evidence Files**: `evidence_54` (`customer_accounts_failover_replica_20260902.sql`) captured at `2026-09-02 23:00:00Z`.
4. **Extracted Observations**: `account_002` was absent from both `customer_profiles_primary` and `customer_profiles_failover_replica`.
5. **Resource-Linking Decisions**: `account_002` linked via `activity_3376: DELETE_RECORD PARTIAL`.
6. **Reconstructed States**: `account_002` -> `UNKNOWN` (activity reported `PARTIAL` work; absence from SQL dump was not ingested as negative evidence).
7. **Required Verification Conditions**: Verification that record is absent across primary and failover replicas.
8. **Emitted Steps**: `[]` (INCOMPLETE with insufficient evidence).
9. **Final Classification**: `INCOMPLETE` (Truth: `COMPLETE`).
10. **Responsible Code**: `code/src/state_reconstruction.py:reconstruct_resource_state:L475`.
11. **Why Prediction Differs**: The pipeline did not treat absence from a failover replica dump as proof of global absence.
12. **Cause Categorization**: **Evidence Limitation & Conservative Fail-Closed Policy**.

### Case Trace: `case_03`
1. **Input Request**: *"Je demande la suppression définitive du compte associé à cette adresse e-mail. Veuillez examiner les identifiants actuels et antérieurs conformément à votre procédure de confidentialité. Merci de confirmer le résultat une fois la vérification terminée."* (`email: l.fontaine46@yahoo.com`).
2. **Audit Cutoff**: `2026-09-26 11:00:00+00:00`.
3. **Evidence Files**: `evidence_94` (`evidence/logs/resource_lookup_trace_20260926_103856.log`) captured at `2026-09-26 10:38:56Z` (21 minutes before audit cutoff).
4. **Extracted Observations**:
   * L17-18: `service=account_service event=profile_lookup_completed resource_id=account_7566 rows=0 http_status=404 lookup_key=l.fontaine46@yahoo.com` -> `ResourceState.ABSENT`.
   * L33-34: `service=security_service event=audit_record_read_completed resource_id=audit_record_2016 rows=1 subject_reference=user_43 event_code=IDENTITY_CHANGE_RECORDED` -> `ResourceState.PRESENT`.
   * L41-42: `service=analytics_platform event=analytics_profile_read_completed resource_id=analytics_9406 customer_reference=null email=null phone=null email_hash=null` -> `ResourceState.ANONYMIZED`.
5. **Resource-Linking Decisions**: In baseline, 0 resources linked because `LogRecordExtractor` discarded `resource_lookup_trace_20260926_103856.log`.
6. **Reconstructed States**: In baseline, no states reconstructed (`candidate_rids: []`).
7. **Required Verification Conditions**: All 3 resources verified in their required states with evidence ID `evidence_94`.
8. **Emitted Steps**: Baseline emitted `[]`.
9. **Final Classification**: `INCOMPLETE` (Truth: `COMPLETE`).
10. **Responsible Code**: `code/src/evidence_extraction.py:LogRecordExtractor:L658`.
11. **Why Prediction Differs**: `LogRecordExtractor` skipped 22 out of 26 log files due to rigid bracketed/KV regexes.
12. **Cause Categorization**: **Confirmed Implementation Defect in Evidence Parser**.

### Case Trace: `case_04`
1. **Input Request**: *"I’m deleting my account. You can keep anonymous statistics, but nothing in analytics should still point back to me."* (`email: thandiwe.n@gmail.com`).
2. **Audit Cutoff**: `2026-09-07 10:20:00+00:00`.
3. **Evidence Files**: No evidence files under `dataset/evidence/` mention `thandiwe.n@gmail.com`, `user_04`, or hash `f730ef60...`.
4. **Extracted Observations**: 0 direct observations.
5. **Resource-Linking Decisions**: 0 candidate resources linked.
6. **Reconstructed States**: No states reconstructed.
7. **Required Verification Conditions**: Verification of account absence and analytics anonymization.
8. **Emitted Steps**: `[]` (INCOMPLETE with insufficient evidence).
9. **Final Classification**: `INCOMPLETE` (Truth: `COMPLETE`).
10. **Responsible Code**: `code/src/completion_validator.py:validate_case_completion:L216` (`NO_RESOURCES_IDENTIFIED`).
11. **Why Prediction Differs**: Ground truth author assumes complete deletion occurred, but participant-facing evidence contains zero files for this user.
12. **Cause Categorization**: **Genuine Evidence Limitation**. Predicting COMPLETE would fabricate evidence without source corroboration.

### Case Trace: `case_31`
1. **Input Request**: *"I no longer need this account. Please remove my name and contact details, but keeping an internal deleted-account reference is fine if other required records still depend on it."* (`email: a.eze08@gmail.com`, `user_id: user_541`).
2. **Audit Cutoff**: `2026-09-15 12:00:00+00:00`.
3. **Evidence Files**: `evidence_51` (`customer_data_snapshot_bundle_20260915.json`) captured at `2026-09-15 12:00:00Z`.
4. **Extracted Observations**:
   * `deleted_customer_references`: `tombstone_440` (subject_reference: `user_541`, direct PII all null) -> `ResourceState.REDACTED`.
   * `security_audit_events`: `audit_record_6909` -> `ResourceState.PRESENT`.
   * `customer_profiles`: `records: []` (0 records in account_service).
5. **Resource-Linking Decisions**: `tombstone_440` and `audit_record_6909` linked from `evidence_51`. `account_541` linked from canonical account heuristic.
6. **Reconstructed States**:
   * `tombstone_440`: `REDACTED` (Policy Satisfied).
   * `audit_record_6909`: `PRESENT` (Policy Satisfied).
   * `account_541`: `PRESENT` (due to fallback to January `activity_303: UPDATE_RECORD` because no direct positive observation existed for `account_541`).
7. **Required Verification Conditions**: Truth expects `account_4857: VERIFY_RECORD_ABSENT`, `audit_record_6909: VERIFY_RECORD_PRESENT`, `tombstone_440: VERIFY_RECORD_REDACTED`.
8. **Emitted Steps**: Baseline emitted FINDING for `account_541`.
9. **Final Classification**: `INCOMPLETE` (Truth: `COMPLETE`).
10. **Responsible Code**: `code/src/resource_link.py` and `code/src/state_reconstruction.py`.
11. **Why Prediction Differs**: `account_4857` was deleted in `activity_3682` (10:45 AM on 2026-09-06) without an explicit user ID in `details`. Linking `account_4857` to `user_541` relies on temporal proximity to `tombstone_440` (11:31 AM), which violates Absolute Constraint 12.
12. **Cause Categorization**: **Ambiguous Requirement / Constraint 12 Enforcement**.

---

## 3. Confirmed Defects and Supporting Evidence

### Defect 1: Log Parser Rigid Format Skipping (Confirmed)
* **Location**: `code/src/evidence_extraction.py:LogRecordExtractor:extract`.
* **Root Cause**: `LogRecordExtractor` used regexes `_RE_BRACKET` and `_RE_KV`. Lines not matching both were discarded (`else: continue`).
* **Supporting Evidence**:
  * Scanned all 26 `.log` files: 22 files produced exactly 0 observations.
  * 1,560 out of 2,211 log lines (70.6%) were skipped.
  * 97 evaluation cases have explicit subject identifiers in `resource_lookup_trace_*.log` files that were dropped.
* **Official Rule Violated**: `AGENTS.md §6.6` (Extract facts from logs and ground findings in participant-visible evidence).

### Defect 2: Snapshot Bundle Negative Evidence (Confirmed)
* **Location**: `code/src/evidence_extraction.py:JsonRecordExtractor` and `code/src/state_reconstruction.py`.
* **Root Cause**: When a snapshot bundle has `records: []` for a collection (such as `account_service.customer_profiles`), 0 observations were emitted. If an older activity log existed (e.g. `UPDATE_RECORD` from 8 months prior), the state reconstructor fell back to that pre-deletion activity and declared the record `PRESENT`.
* **Official Rule Violated**: `AGENTS.md §6.5` (Reconstruct true state at `audit_at` from available evidence).

---

## 4. Rejected Hypotheses and Reasons

1. **Rejected Hypothesis: Trusting `DELETE_RECORD SUCCESS` activity claims alone improves accuracy.**
   * *Reason*: Violates Absolute Constraint 11 and `problem_statement.md:L124` (*"Reported workflow statuses and operation results are claims. A lack of findings is not evidence of deletion"*). Treating uncorroborated success claims as proof would create false positives in cases where replication drift occurred (such as `case_05`).
2. **Rejected Hypothesis: Temporal proximity clustering of unassociated activity rows.**
   * *Reason*: Violates Absolute Constraint 12. Multiple unrelated users share minute-level timestamps in `system_activity.csv`. Proximity-based linkage causes cross-user entity contamination.
3. **Rejected Hypothesis: Blindly adopting the Enhanced Log Parser into production.**
   * *Reason*: When simulated on the 32 public samples, the enhanced log parser improved Step F1 from 41.56% to 51.33% and recovered `case_03`, but falsely classified `case_12` and `case_15` as COMPLETE. This decreased overall status accuracy from 84.38% to 81.25% and reduced COMPLETE precision from 100% to 75%. Falsely certifying undeleted cases violates the primary privacy safety goal.

---

## 5. Candidate Fix Simulation & Metric Comparison

We simulated the enhanced log extractor on the 32 authorized sample cases:

| Metric | Baseline | Candidate (Enhanced Log) | Delta | Assessment |
| :--- | :---: | :---: | :---: | :--- |
| **Status Accuracy** | **84.38% (27/32)** | 81.25% (26/32) | -3.13% | **Regressed** (2 false positives introduced) |
| **Macro-F1** | **0.7823** | 0.7681 | -0.0142 | Slight decline |
| **COMPLETE Precision** | **100.0% (5/5)** | 75.0% (6/8) | -25.0% | **Critical Safety Regression** |
| **COMPLETE Recall** | 50.0% (5/10) | **60.0% (6/10)** | +10.0% | Improved (recovered `case_03`) |
| **INCOMPLETE Recall** | **100.0% (22/22)** | 90.91% (20/22) | -9.09% | Regressed |
| **Step Precision** | 0.5565 | **0.5959** | +3.94% | Improved |
| **Step Recall** | 0.3316 | **0.4508** | +11.92% | **Substantial Gain** |
| **Step F1** | 0.4156 | **0.5133** | +9.77% | **Substantial Gain** |
| **Sequence Accuracy** | 3.12% (1/32) | 3.12% (1/32) | 0.00% | Unchanged |

### Trade-off Analysis
* **The Step-Quality Gain**: Parsing all 26 log files extracts 2,211 log observations and increases Step F1 by almost 10 full percentage points (to 51.33%).
* **The Compliance Hazard**: Because downstream cross-system data flows (such as `data_flow_9846` in `case_15`) are not yet linked to requesting clusters, recognizing that the primary account record was deleted causes the completion validator to prematurely declare the whole case COMPLETE. In a deletion audit, false certification of deletion is a catastrophic compliance failure ($2.4M incident in the challenge scenario).
* **Decision**: In strict adherence to prompt instruction (*"Do not weaken safety checks to increase COMPLETE recall. If a fix improves one metric but worsens another, disclose the trade-off. If no justified fixes are found, retain the existing deliverables"*), we retain the baseline prediction file.

---

## 6. Step-Level Error Analysis

The baseline step-level F1 of 41.56% stems from three root causes:
1. **Incomplete Log Ingestion**: Discarding 22 log files prevented the emission of verification steps for readback checks (e.g. `evidence_94` in `case_03`).
2. **False INCOMPLETE Classifications**: When a case is classified as INCOMPLETE, NullTrace emits a 3-phase remediation plan (`FINDING` -> `REMEDIATION` -> `VERIFICATION`) for any remaining resource, whereas the ground truth for a COMPLETE case contains only `VERIFICATION` steps.
3. **Multi-Step Deduplication & Sequence Matching**: Exact sequence accuracy is 3.12% because even minor ordering differences across independent microservices affect the sequence match, though field-level phase accuracy is 79.09%.

---

## 7. Deliverable Integrity & Verification

The existing deliverables remain fully validated and intact:
* **Root `output.csv`**:
  * Row Count: Exactly 518 data rows.
  * SHA-256: `788302aaea25bf22e1d84ce376b7450700285712dc356fb1b90ee5fc4927a650`.
  * Status Breakdown: 137 COMPLETE, 371 INCOMPLETE, 10 NOT_APPLICABLE.
  * Validation: 0 schema or semantic errors via `ops.validate_steps`.
* **Submission Archive `code.zip`**:
  * Size: 343,236 bytes (83 files).
  * Exclusions Verified: Zero `dataset/`, `.git/`, `.env`, or `__pycache__` files.
* **Automated Test Suite**:
  * Result: 153 passed in 21.40s (`pytest code/tests/ -q`).

---

## 8. Recommended Next Action

The repository is fully packaged, tested, and ready for submission:
1. Retain root `output.csv` (SHA-256: `788302aa...`).
2. Retain `code.zip` (343 KB).
3. Retain root `log.txt`.
4. Submit deliverables to the official challenge portal:
   https://www.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists
