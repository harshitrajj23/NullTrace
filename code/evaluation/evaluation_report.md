# NullTrace Evaluation Report: Model Off Deletion-Audit Assessment

**Date**: 2026-10-25  
**Challenge**: HackerRank Orchestrate (October 2026) — *Ghost Data Still Exists*  
**Repository**: `https://github.com/harshitrajj23/NullTrace.git`  
**Execution Mode**: Offline, Deterministic, `DECISION: MODEL_OFF`  
**Total Evaluation Requests**: 518 cases (`case_33` to `case_550`)  
**Authorized Ground-Truth Sample Set**: 32 cases (`case_01` to `case_32`)

---

## 1. Executive Summary and Evaluation Scope

This report documents the rigorous evaluation of the integrated NullTrace deletion-audit pipeline against the authorized evaluation ground truth (`dataset/sample_output.csv`).

### Non-Negotiable Answer-Key Isolation
* **Strict Physical Separation**: Ground-truth data (`dataset/sample_output.csv`) is read **only** by the standalone evaluation script (`code/evaluation/evaluate_predictions.py`).
* **Zero Production Contamination**: Neither production extraction, identity clustering, state reconstruction, resurrection detection, planning, nor completion validation import or read the sample output key.
* **Coverage Scope Disclaimer**: Ground truth is provided exclusively for the 32 public sample cases (`case_01`..`case_32`). The evaluation metrics reported below are measured exclusively on this 32-case sample set. **These sample metrics do not establish full-dataset accuracy** for the 518 evaluation requests (`case_33`..`case_550`), as ground-truth labels for the 518 evaluation cases are organizer-held.

---

## 2. Quantitative Evaluation Results (32 Sample Cases)

### 2.1 Overall Performance
* **Sample Size**: 32 requests (`case_01` to `case_32`)
* **Ground-Truth Coverage**: 32 / 32 cases (100.0%)
* **Status Accuracy**: **78.12%** (25 / 32 correct deletion statuses)
* **Macro-F1 Score**: **0.6621**
* **False COMPLETE Rate**: **0.0%** (0 false positive COMPLETE predictions)

### 2.2 Status Confusion Matrix
The confusion matrix below compares ground truth (rows) against NullTrace predictions (columns):

| True Status \ Predicted | COMPLETE | INCOMPLETE | NOT_APPLICABLE | Total Support |
|:------------------------|:--------:|:----------:|:--------------:|:-------------:|
| **COMPLETE**            | **3**    | 7          | 0              | 10            |
| **INCOMPLETE**          | **0**    | **22**     | 0              | 22            |
| **NOT_APPLICABLE**      | 0        | 0          | **0**          | 0             |
| **Total Predicted**     | 3        | 29         | 0              | 32            |

### 2.3 Per-Class Precision, Recall, and F1

| Class | Support | TP | FP | FN | Precision | Recall | F1 Score |
|:------|:-------:|:--:|:--:|:--:|:---------:|:------:|:--------:|
| **COMPLETE** | 10 | 3 | 0 | 7 | **1.0000** | 0.3000 | 0.4615 |
| **INCOMPLETE** | 22 | 22 | 7 | 0 | **0.7586** | **1.0000** | **0.8627** |
| **NOT_APPLICABLE** | 0 | 0 | 0 | 0 | *Undefined* | *Undefined* | *Undefined* |

> **Critical Safety Achievement**: Precision on `COMPLETE` is **100%** (1.0000). The pipeline never asserts that a deletion is COMPLETE unless every required evidence check strictly proves compliant absence, redaction, or anonymization. Under uncertainty, the pipeline safely fails closed to `INCOMPLETE`.

### 2.4 Step-Level and Sequence Quality Metrics

* **Ground-Truth Steps**: 193 steps across 32 sample cases
* **Predicted Steps**: 97 steps across 32 sample cases
* **Matched Steps (Exact Multiset)**: 55 steps
* **Step Precision**: **56.70%** (55 / 97)
* **Step Recall**: **28.50%** (55 / 193)
* **Step F1 Score**: **37.93%**
* **Exact Sequence Accuracy**: **3.12%** (1 / 32 cases exact identical step-by-step sequence)

### 2.5 Field-Level Accuracies (Aligned Positions)
Across all aligned step positions between predictions and ground truth:
* **Phase**: **76.60%**
* **System ID**: **51.06%**
* **Resource ID**: **57.45%**
* **Operation**: **52.13%**
* **State**: **56.38%**
* **Evidence ID**: **67.02%**

---

## 3. Step and Evidence Contract Validation

All predictions across both the 32 sample cases and all 518 full evaluation requests were validated against the grader contract (`code/src/ops.py:validate_steps`):

1. **Schema Integrity**: Every row strictly matches `case_id,deletion_status,steps_json`.
2. **JSON Serialization**: 100% valid JSON array with keys `step_no`, `phase`, `system_id`, `resource_id`, `operation`, `state`, `evidence_id`.
3. **Step Numbering**: Step numbers start at 1 and increment consecutively with 0 gaps.
4. **Phase Ordering**: Strictly ordered `FINDING` -> `REMEDIATION` -> `VERIFICATION`.
5. **Operation & State Compatibility**:
   - `REPORT_REMAINING_RECORD` / `REPORT_EXPOSED_PII` -> `PRESENT`
   - `REPORT_ACTIVE_DATA_FLOW` / `REPORT_RESTORE_RISK` -> `ACTIVE`
   - `DISABLE_DATA_FLOW` -> `DISABLED`
   - `BLOCK_RESTORE` -> `BLOCKED`
   - `DELETE_RECORD` / `VERIFY_RECORD_ABSENT` -> `ABSENT`
   - `REDACT_RECORD` / `VERIFY_RECORD_REDACTED` -> `REDACTED`
   - `ANONYMIZE_RECORD` / `VERIFY_RECORD_ANONYMIZED` -> `ANONYMIZED`
   - `VERIFY_RECORD_PRESENT` -> `PRESENT`
   - `VERIFY_DATA_FLOW_DISABLED` -> `DISABLED`
   - `VERIFY_RESTORE_BLOCKED` -> `BLOCKED`
6. **Evidence ID Contract**:
   - All `FINDING` operations and `COMPLETE` verification steps cite real, non-empty, participant-visible evidence IDs from `dataset/evidence_files.csv`.
   - All proposed `REMEDIATION` and future `VERIFICATION` steps for `INCOMPLETE` cases carry `evidence_id = ""`.
   - Zero fabricated, inferred, or post-audit evidence references.
7. **Total Validation Failures**: **0** across all 518 cases.

---

## 4. Systematic Errors Diagnosed & Defect Corrections

### 4.1 Defect 1: Unparsed Evidence in Multi-Service JSON Files (Fixed)
* **Error Category**: Missing Multi-Service Evidence Extraction
* **Affected Sample Cases**: `case_23` and multiple related incomplete cases
* **Root Cause**: `JsonRecordExtractor` previously only parsed files matching the `snapshots` structure (12 files). It completely ignored top-level `records` arrays (5 files, e.g., `connector_configurations_20260812.json`, `security_audit_ledger_20261001.json`) and `service_exports` dictionaries (11 files, e.g., `service_resource_export_*.json`).
* **Consequence**: In `case_23`, surviving records in `export_service` (`export_7364`) and `search_service` (`search_898`) in `evidence_92` were missed. Because only a retained audit record was visible, the validator previously misclassified `case_23` as `COMPLETE` (a critical False Positive).
* **Fix Applied**: Extended `JsonRecordExtractor` in `code/src/evidence_extraction.py` to parse all 3 JSON schemas (`snapshots`, root `records`, and `service_exports`), extracting observations across account lookups, search index entries, export jobs, and connector configs.
* **Result**:
  - `case_23` correctly detected as `INCOMPLETE` with findings for `export_7364` and `search_898` citing `evidence_92`.
  - False COMPLETE count dropped from 1 to **0** (100% COMPLETE precision).
  - Overall accuracy improved from 75.0% to 78.12%.
  - Total steps emitted across 518 cases grew from 787 to 1311.

### 4.2 Defect 2: Unlinked Activity Rows & Fail-Closed Behavior
* **Error Category**: Subject-to-Resource Linkage Gaps
* **Affected Sample Cases**: 7 cases (`case_01`, `case_02`, `case_04`, etc.)
* **Root Cause**: In `system_activity.csv`, deletion worker events record `DELETE_RECORD` on resources like `account_001` or `account_002` without subject identifiers in `details`. Because no co-occurrence link in evidence explicitly binds `user_01` to `account_001`, the linker safely excludes ungrounded resources.
* **Resolution**: In accordance with the project contract ("A lack of findings is not evidence of deletion", "Uncertainty always resolves to INCOMPLETE"), the validator fails closed to `INCOMPLETE` when resource evidence is insufficient. This prevents unsubstantiated COMPLETE assertions while maintaining 100% precision on true COMPLETE cases.

---

## 5. Team-Made Synthetic Test Cases

To verify that the integrated pipeline detects realistic failure modes without reading production data, three synthetic end-to-end integration tests were implemented in `code/tests/test_synthetic_pipeline_cases.py`:

### Test Case 1: Replication Drift (Failover Database Contains Personal Data)
* **Failure Mode**: Primary database has deleted the subject record (`ABSENT`), but a regional failover replica database snapshot still contains the full profile (`PRESENT`).
* **Synthetic Identifiers**: `user_synth_01`, `synth.drift@example.org`, resource `account_synth_replica_01` in SQLite table `customer_profiles_failover_replica`.
* **Expected Outcome**: Status `INCOMPLETE`, finding `REPORT_REMAINING_RECORD` citing `evidence_replica_db`, remediation `DELETE_RECORD`, verification `VERIFY_RECORD_ABSENT`.
* **Actual Result**: **PASSED**. Pipeline detected the surviving replica record, correctly reported finding citing SQLite evidence, and planned remediation.

### Test Case 2: Active Synchronization Flow / Resurrection Risk
* **Failure Mode**: Primary deletion reported complete, but an active synchronization connector (`enabled: true`) continues to bridge user data to an analytics store.
* **Synthetic Identifiers**: `user_synth_02`, `synth.sync@example.org`, resource `data_flow_synth_202`.
* **Expected Outcome**: Status `INCOMPLETE`, finding `REPORT_ACTIVE_DATA_FLOW` with state `ACTIVE` citing `evidence_connector_json`, remediation `DISABLE_DATA_FLOW`, verification `VERIFY_DATA_FLOW_DISABLED`.
* **Actual Result**: **PASSED**. Pipeline identified active connector, emitted `REPORT_ACTIVE_DATA_FLOW`, prioritized `DISABLE_DATA_FLOW` before resource operations, and verified disabled flow.

### Test Case 3: Account Tombstone PII Leakage
* **Failure Mode**: An account tombstone preserves the permitted internal reference (`user_synth_03`) but unredacted direct personal identifiers (`synth.tombstone@example.org`) remain exposed.
* **Synthetic Identifiers**: `user_synth_03`, `synth.tombstone@example.org`, resource `tombstone_synth_303`.
* **Expected Outcome**: Status `INCOMPLETE`, finding `REPORT_EXPOSED_PII` with state `PRESENT` citing `evidence_tombstone_json`, remediation `REDACT_RECORD`, verification `VERIFY_RECORD_REDACTED`.
* **Actual Result**: **PASSED**. Pipeline detected exposed direct PII on tombstone, emitted `REPORT_EXPOSED_PII`, and planned redaction.

---

## 6. Full 518-Case Integrated Pipeline Output Summary

A clean run of the integrated pipeline across all 518 evaluation requests produced `build/nulltrace_integrated.csv`:

* **Total Evaluation Requests Processed**: 518 / 518
* **NOT_APPLICABLE**: 10 (1.93%)
* **INCOMPLETE**: 403 (77.80%)
* **COMPLETE**: 105 (20.27%)
* **Total Steps Emitted**: 1311
* **Average Steps per Request**: 2.53
* **Validation Errors**: 0
* **Automated Tests Passing**: 137 / 137 (100% passing in 20.07s)
