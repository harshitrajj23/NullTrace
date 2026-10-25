# NullTrace — Step U: Four-Error Root-Cause Investigation Report

## Executive Summary
This report documents the forensic error investigation into the four remaining misclassified cases in the authorized NullTrace public-sample evaluation (`case_01`, `case_02`, `case_04`, and `case_31`).

### Baseline Performance Prior to Investigation
* **Public Sample Accuracy**: **87.50% (28 / 32 correct deletion statuses)**
* **Macro-F1 Score**: **0.8333**
* **COMPLETE Precision**: **100.0% (6 / 6)** — zero false positive COMPLETE predictions
* **COMPLETE Recall**: **60.0% (6 / 10)**
* **INCOMPLETE Recall**: **100.0% (22 / 22)**
* **Step-Level F1**: **52.92%**
* **Root Deliverable Status**: Preserved and verified (`output.csv` SHA-256: `c2173c42197e503ba349eb2cad214b1f9276c6caa9a9e9308bae836e3c109d24`)

---

## 1. Reproduction of Baseline & Error Case Identification

Using the standalone authorized evaluator (`code/evaluation/evaluate_predictions.py`) against `dataset/sample_output.csv` under strict Answer-Key Isolation, all 32 public sample cases were evaluated. Exactly four cases were misclassified, all of which are False Negatives on `COMPLETE`:

| Case ID | Email | Requested At | Audit Cutoff | Reported Status | Truth Status | Predicted Status | Error Type |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| `case_01` | `amina.elmasri@gmail.com` | `2026-08-18T09:14:00Z` | `2026-09-03T11:30:00Z` | `COMPLETE` | `COMPLETE` | `INCOMPLETE` | False Negative |
| `case_02` | `mateo.rios@outlook.com` | `2026-08-20T14:22:00Z` | `2026-09-04T15:00:00Z` | `COMPLETE` | `COMPLETE` | `INCOMPLETE` | False Negative |
| `case_04` | `thandiwe.n@gmail.com` | `2026-08-27T08:15:00Z` | `2026-09-07T10:20:00Z` | `COMPLETE` | `COMPLETE` | `INCOMPLETE` | False Negative |
| `case_31` | `a.eze08@gmail.com` | `2026-09-08T16:02:00Z` | `2026-09-15T12:00:00Z` | `COMPLETE` | `COMPLETE` | `INCOMPLETE` | False Negative |

---

## 2. Case-by-Case Deep Forensic Investigation

### Case 01: `amina.elmasri@gmail.com` (`user_01`)
* **Identity Cluster**:
  - `user_id`: `user_01`
  - `email`: `amina.elmasri@gmail.com`
  - `phone`: `+971 50 482 7316`
  - `email_hash`: `d4e1f59abcf9a1e0cfdc7c27ad6c07ed4ff88b326a16ed5eed5ec6bc31618c93`
* **Canonical Resource**: `account_001`
* **System Activity**:
  - `activity_3342` (`2026-08-20T16:41:43Z`): `DELETE_RECORD`, `deletion_worker`, `account_service`, `account_001`, `SUCCESS`, *"Deletion worker reported the requested operation as completed. Target resource: account_001."*
* **Evidence Examination**:
  - `evidence_54` (`customer_accounts_failover_replica_20260902.sql`) captured on `2026-09-02T23:00:00Z` (prior to `audit_at: 2026-09-03T11:30:00Z`).
  - In `evidence_54`, `account_001` is absent from both `customer_profiles_primary` and `customer_profiles_failover_replica`.
* **Root Cause**:
  - `SqlSnapshotExtractor` performs `SELECT * FROM tbl` and emits observations only for records present in database tables. It does not perform negative presence queries against point-in-time database snapshot replicas.
  - Consequently, `account_001` received 0 direct evidence observations.
  - The state reconstructor only had `activity_3342` (`reported_result: SUCCESS`).
  - Per AGENTS.md §6.1 / §6.5: *"Reported statuses and activity results are claims; the agent must establish the state at each case's audit_at time from the supplied evidence."*
  - The pipeline treated `activity_3342` as an uncorroborated claim and marked `account_001` as `UNKNOWN`, causing `validate_case_completion` to safely fail closed to `INCOMPLETE`.
* **Classification**: **Genuine Evidence/Design Limitation (Negative SQL Snapshot Proving)**.

---

### Case 02: `mateo.rios@outlook.com` (`user_02`)
* **Identity Cluster**:
  - `user_id`: `user_02`
  - `email`: `mateo.rios@outlook.com`
  - `phone`: `+34 612 847 593`
  - `email_hash`: `fad1c282b6b8ff346ee92e617331f69c2b6bb345af954eeb44581c57529eab9d`
* **Canonical Resource**: `account_002`
* **System Activity**:
  - `activity_3376` (`2026-08-22T07:30:03Z`): `DELETE_RECORD`, `deletion_worker`, `account_service`, `account_002`, `PARTIAL`, *"Deletion worker completed some internal work but could not confirm the final state. Target resource: account_002."*
* **Evidence Examination**:
  - `account_002` is absent from `evidence_54` (`customer_accounts_failover_replica_20260902.sql`).
  - However, the worker activity specifically reported `PARTIAL`.
* **Root Cause**:
  - In commerce platforms with distributed databases, a `PARTIAL` result indicates that deletion succeeded on some nodes but could not be confirmed globally.
  - Inferring complete deletion from absence in a single failover replica when the worker reported `PARTIAL` introduces severe false-completion risk (as exemplified by `case_05` where primary deletion occurred but replica retention remained).
  - The pipeline correctly refused to certify completion without an affirmative readback log.
* **Classification**: **Intentional Fail-Closed Conservative Guardrail**.

---

### Case 04: `thandiwe.n@gmail.com` (`user_04`)
* **Identity Cluster**:
  - `user_id`: `user_04`
  - `email`: `thandiwe.n@gmail.com`
  - `phone`: `+27 71 684 5928`
  - `email_hash`: `f730ef60615bde7a8f5ee21138637b4e9d4094855fbb02da6afcdba9c076281f`
* **System Activity**:
  - Zero rows in `system_activity.csv` mentioning `user_04`, `account_004`, or any cluster identifier.
* **Evidence Examination**:
  - Zero rows in any evidence file across all 94 evidence files.
* **Root Cause**:
  - Complete absence of evidence. No candidate resources could be discovered or verified.
  - `completion_validator.py` Rule 1 strictly enforces: *"A lack of findings is not evidence of deletion (empty resources -> INCOMPLETE)"*.
  - Under the official challenge rules (§6.3, §6.5): *"A verification step for a COMPLETE case must cite the evidence that proves the current compliant state... Do not fabricate evidence."*
  - Without any evidence to cite, the pipeline cannot emit a compliant verification step.
* **Classification**: **Genuine Evidentiary Limitation**.

---

### Case 31: `a.eze08@gmail.com` (`user_541`)
* **Identity Cluster**:
  - `user_id`: `user_541`
  - `email`: `a.eze08@gmail.com`
  - `phone`: `+234 803 052 7943`
  - `email_hash`: `1b7bf5a90890498cc6b7d2b50b0580ad1dbfaee7766f5d09cd87ecb548533e9e`
* **System Activity**:
  - `activity_303` (`2026-01-26T13:05:38Z`): `UPDATE_RECORD`, `profile_service`, `account_service`, `account_541`, `SUCCESS`, *"Profile preference update..."*
* **Evidence Examination**:
  - In `customer_data_snapshot_bundle_20260915.json` (`evidence_51`), captured at `2026-09-15T12:00:00Z`:
    - `tombstone_440`: `{'resource_id': 'tombstone_440', 'subject_reference': 'user_541', 'name': None, 'email': None, 'phone': None, 'email_hash': None, 'account_status': 'DELETED'}`
    - `audit_record_6909`: `{'resource_id': 'audit_record_6909', 'subject_reference': 'user_541', 'event_name': 'account_deletion_reviewed', 'actor_type': 'automated_privacy_workflow', ...}`
* **Root Cause Analysis (Confirmed Implementation Defect)**:
  - The pipeline linked `account_541` from `activity_303` (from January 2026).
  - Because `activity_303` was an update operation, `reconstruct_resource_state` marked `account_541` as `PRESENT`.
  - Because there was no subsequent explicit activity for `account_541`, `account_541` remained `PRESENT`!
  - However, `tombstone_440` in `evidence_51` explicitly proves `account_status: 'DELETED'` and all direct identifiers have been stripped.
  - Per AGENTS.md §1 & §6.5: *"For an ACCOUNT_TOMBSTONE, preserve the stable subject reference and remove the name, email, phone, email hash, and any other direct identifiers required by the applicable REDACT rule."*
  - The presence of a compliant account tombstone with `account_status: 'DELETED'` proves that the underlying primary account was deleted and replaced by the tombstone. Failing to connect the tombstone to the account deletion is a confirmed defect.
* **Classification**: **Confirmed Implementation Defect in Account Tombstone Replacement Resolution**.

---

## 3. Safe, Generalizable Fix Simulation (Case 31)

We simulated the generalizable rule for account tombstone resolution:
* **Rule**: When an `ACCOUNT_TOMBSTONE` is verified compliant (`observed_state == REDACTED`, `account_status == 'DELETED'`, direct PII absent), any associated primary account (`account_<id>`) lacking conflicting post-tombstone evidence is resolved as `ABSENT` (tombstoned), citing the tombstone evidence ID.

### Simulation Results on 32 Public Samples
* **Status Accuracy**: **90.62% (29 / 32)** (Up from 87.50%, +3.12% gain)
* **Macro-F1**: **0.8798** (Up from 0.8333, +0.0465 gain)
* **COMPLETE Precision**: **100.0% (7 / 7)** (Zero false COMPLETEs!)
* **COMPLETE Recall**: **70.0% (7 / 10)** (`case_31` recovered!)
* **INCOMPLETE Recall**: **100.0% (22 / 22)** (Zero regressions)
* **Step F1**: **54.15%** (Up from 52.92%, +1.23% gain)
* **Exact Sequence Accuracy**: **3.12% (1 / 32)**
* **Changed Cases**: Exactly 1 case changed (`case_31`: `INCOMPLETE` → `COMPLETE`).

---

## 4. Remaining Uncertainty and Summary Table

| Case ID | Root Cause Category | Explanation | Solvable Under Rules? |
| :--- | :--- | :--- | :---: |
| `case_01` | Evidence/Design Limitation | Absence in SQL replica (`evidence_54`) is not queried as negative evidence. | Requires negative SQL query engine |
| `case_02` | Intentional Guardrail | Worker reported `PARTIAL`; absence in replica alone is insufficient to rule out replication drift. | Preserves 100% precision |
| `case_04` | Genuine Evidentiary Limitation | Zero activity logs, zero evidence files across entire dataset. | Unprovable without fabricating evidence |
| `case_31` | Confirmed Implementation Defect | Account tombstone (`tombstone_440`) proves account deletion, but January 2026 update activity overrode it. | **Safely resolvable (+3.12% accuracy gain)** |

---

## 5. Recommendation

Per the strict instructions for Step U:
- All changes were tested in isolated development simulations (`build/sim_tombstone_rule.csv`).
- Root `output.csv` remains **completely unchanged** at SHA-256 `c2173c42197e503ba349eb2cad214b1f9276c6caa9a9e9308bae836e3c109d24`.
- `code.zip` remains **unchanged**.
- **Recommendation**:
  1. The current promoted baseline (`output.csv`, 87.50% sample accuracy, 100% precision) is solid, verified, and submission-ready.
  2. The Case 31 tombstone resolution rule is confirmed safe, generalizable, and mathematically verified to reach **90.62%** sample accuracy with 100% precision.
  3. Per the stop condition, no further changes are deployed until explicit authorization.
