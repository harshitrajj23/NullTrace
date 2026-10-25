# NullTrace: Ghost Data Still Exists

## 1. Overview
NullTrace is a deterministic, fail-closed deletion-audit pipeline designed for the HackerRank Orchestrate competition. For every deletion request, it evaluates grounded evidence across platform activities, databases, logs, and exports to emit an audit decision of COMPLETE, INCOMPLETE, or NOT_APPLICABLE along with an ordered steps_json array. No LLM or vision model is used (DECISION: MODEL_OFF, see code/docs/DATA_HANDLING.md).

---

## 2. Requirements
* **Python Version**: Python 3.15 (tested and supported on Python 3.10+)
* **Dependencies**:
  ```bash
  pip install pypdf pytest
  ```
* **API Keys**: No API key is needed. NullTrace operates 100% offline with zero external network or model calls.

---

## 3. How to Run

### Pipeline
Execute the full deletion-audit pipeline to generate the 518-row output file:
```bash
python3 code/main.py run --output ./output.csv
```
*(Verified: verified by reading `code/main.py` CLI arguments. Reads `dataset/` and writes `output.csv` to the target path.)*

### Tests
Run the test suite across all 29 test modules:
```bash
python -m pytest code/tests/ -q
```
*(Verified: verified with `python3 -m pytest code/tests/ -q -p no:debugging`, passing all 175 tests. Note: the `-p no:debugging` flag disables pytest's pdb plugin to prevent Python from confusing the local `code/` folder with the standard library `code` module.)*

### Evaluator
Run the standalone prediction evaluator against the public sample ground truth:
```bash
python3 code/evaluation/evaluate_predictions.py --predictions build/candidate_sample_preds.csv --ground-truth dataset/sample_output.csv
```
*(Verified: verified by reading `code/evaluation/evaluate_predictions.py`. It reads the public sample answers in `dataset/sample_output.csv` and is for reporting only; production pipeline code never imports or reads sample ground truth.)*

---

## 4. Architecture
Pipeline execution flow through `code/src/`:

* **loader** (`code/src/loader.py`): Ingests participant-facing dataset CSV files and indexes raw records.
* **normalize** (`code/src/normalize.py`): Canonicalizes email addresses, phone numbers, and identifiers.
* **identity** (`code/src/identity.py`): Reconstructs identity clusters across current profiles and historical audit logs.
* **evidence extraction** (`code/src/evidence_extraction.py`): Extracts and indexes observations from SQL databases, logs, records, text, and PDF files.
* **resource link** (`code/src/resource_link.py`): Links cluster subjects to resources using grounded identifiers.
* **state reconstruction** (`code/src/state_reconstruction.py`): Reconstructs temporal resource states up to each request's `audit_at` cutoff.
* **rule engine** (`code/src/rule_engine.py`): Applies `deletion_rules.csv` and handles account tombstones.
* **planner** (`code/src/planner.py`): Generates ordered finding, remediation, and verification steps.
* **completion check** (`code/src/completion_validator.py`): Determines whether deletion is fully satisfied and evidence-backed.
* **overrides** (`code/src/pipeline.py`): Ingests reviewed case overrides from `code/config/overrides.csv`.
* **validator** (`code/src/ops.py`): Enforces step schema, operation-state pairs, ordering, and evidence citations.
* **CSV writer** (`code/src/grader_io.py`): Serializes validated steps and writes the final grader CSV.

---

## 5. Output Format
The pipeline produces `output.csv` containing the following three columns:
```text
case_id,deletion_status,steps_json
```

### The 15 Allowed Operations and Phases

| Phase | Operation | Allowed State | Meaning |
| :--- | :--- | :--- | :--- |
| **FINDING** | `REPORT_REMAINING_RECORD` | `PRESENT` | Record that should have been deleted still exists |
| **FINDING** | `REPORT_EXPOSED_PII` | `PRESENT` | Prohibited identifiers remain exposed in retained record |
| **FINDING** | `REPORT_ACTIVE_DATA_FLOW` | `ACTIVE` | Active sync process can copy or recreate data |
| **FINDING** | `REPORT_RESTORE_RISK` | `ACTIVE` | Backup or restore process can recreate deleted data |
| **REMEDIATION** | `DISABLE_DATA_FLOW` | `DISABLED` | Deactivates process that copies or recreates data |
| **REMEDIATION** | `BLOCK_RESTORE` | `BLOCKED` | Prevents affected backup from restoring data |
| **REMEDIATION** | `DELETE_RECORD` | `ABSENT` | Removes the record completely |
| **REMEDIATION** | `REDACT_RECORD` | `REDACTED` | Removes identifying fields while keeping record |
| **REMEDIATION** | `ANONYMIZE_RECORD` | `ANONYMIZED` | Unlinks record irreversibly from the user |
| **VERIFICATION** | `VERIFY_RECORD_ABSENT` | `ABSENT` | Confirms record no longer exists |
| **VERIFICATION** | `VERIFY_RECORD_PRESENT` | `PRESENT` | Confirms required retained record still exists |
| **VERIFICATION** | `VERIFY_RECORD_REDACTED` | `REDACTED` | Confirms prohibited fields were removed |
| **VERIFICATION** | `VERIFY_RECORD_ANONYMIZED` | `ANONYMIZED` | Confirms record is unlinked from the user |
| **VERIFICATION** | `VERIFY_DATA_FLOW_DISABLED` | `DISABLED` | Confirms sync/data flow is inactive |
| **VERIFICATION** | `VERIFY_RESTORE_BLOCKED` | `BLOCKED` | Confirms data cannot be restored from backup |

### Ordering Rule
* Rows are sorted strictly in ascending order by `case_id`.
* Within `steps_json`, phases must be ordered strictly as: `FINDING` -> `REMEDIATION` -> `VERIFICATION`.
* Within each phase, operations follow specification table order (e.g., disabling flows and blocking restores before modifying dependent records), then sorted by `system_id` ascending, and then `resource_id` ascending.
* Steps are consecutively numbered starting from `1` with no gaps.
* For `INCOMPLETE` cases, `evidence_id` is cited for FINDING steps and left empty (`""`) for REMEDIATION and future VERIFICATION steps.
* For `COMPLETE` cases, only evidence-backed VERIFICATION steps are emitted.
* For `NOT_APPLICABLE` cases, `steps_json` must be empty (`[]`).

---

## 6. Manual Overrides
`code/config/overrides.csv` defines reviewed judgment calls for exactly 9 cases:
* `case_226`, `case_423`, `case_530`, `case_73`: Demoted from `COMPLETE` to `INCOMPLETE` with `[]` because candidate verification steps cited post-audit snapshot files (`evidence_22`, `evidence_40`, `evidence_49`, `evidence_07`) and zero pre-audit evidence supports a finding.
* `case_319`: Demoted from `COMPLETE` to `INCOMPLETE` with 3 steps for `account_2088` because pre-audit `activity_1515` recorded a failed deletion (`DELETE_RECORD` failed on 2026-04-20 prior to `audit_at`).
* `case_311`, `case_46`, `case_61`, `case_63`: Reconstructed to `INCOMPLETE` with grounded pre-audit evidence findings (`search_3004`, `tombstone_17`, `object_19`, `marketing_001`).

Overrides are applied by `code/src/pipeline.py` after the rule engine and before validation. Overrides may only set status to `INCOMPLETE`, and each entry records its specific reason and source documentation file.

---

## 7. Known Limitations
Stated plainly:
* **26 Empty INCOMPLETE Rows**: 26 rows have `deletion_status = INCOMPLETE` and `steps_json = []` (a known violation of the INCOMPLETE format rule). These cases lack pre-audit grounded evidence to substantiate finding steps without hallucination. Their case IDs (from `build/unresolved_cases.csv`) are:
  `case_44`, `case_51`, `case_60`, `case_73`, `case_127`, `case_168`, `case_170`, `case_175`, `case_226`, `case_264`, `case_288`, `case_292`, `case_345`, `case_372`, `case_408`, `case_412`, `case_413`, `case_414`, `case_416`, `case_417`, `case_418`, `case_420`, `case_423`, `case_520`, `case_522`, `case_530`.
* **Unread Screenshots**: The 11 image-only screenshots were not read (`DECISION: MODEL_OFF`).
* **Accuracy on Public Samples**: Status accuracy is **90.6%** (29/32) on the public samples, **IN-SAMPLE**. Hidden 518 evaluation accuracy is not measured.
* **Step and Sequence Metrics**: Step-level F1 is about **54%** (0.5415), and exact sequence match is about **3%** (3.12%, 1/32 cases).
* **Sample-Derived Rules**: Some extraction and linking rules were derived from diagnosing sample misses.

---

## 8. Reproducibility
A clean clone reproduces `build/nulltrace_candidate_a3.csv` byte for byte (exact match of 411,883 bytes).

To verify the SHA-256 hash:
```bash
shasum -a 256 output.csv build/nulltrace_candidate_a3.csv
```
*(Verified: verified command. Both files output SHA-256 `ba03a6ba749d780aaef2258039d74cbf47c039c4f4fc1bdf0628490135ba3362`.)*

---

## 9. Evaluation and Usage Reports
* **Evaluation Report**: See [`evaluation/evaluation_report.md`](./evaluation/evaluation_report.md) for detailed case-level, step-level, and sequence metrics, failure analysis, and synthetic test cases.
* **Usage Report**: See [`evaluation/usage_report.md`](./evaluation/usage_report.md) for model call accounting ($0.00 cost, 0 external tokens under `MODEL_OFF`).

---

## 10. Submission
The official challenge and submission link is:  
https://www.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists
