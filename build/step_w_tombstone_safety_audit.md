# Step W: Read-Only Tombstone Safety Audit

**Date**: October 25, 2026  
**Auditor**: `antigravity-ide` (Independent Read-Only Inspection)  
**Execution Runtime**: Deterministic Python Pipeline (`DECISION: MODEL_OFF`)  
**Network Activity**: None ($0.00 spend)  
**Dataset Integrity**: Verified Clean (`git status dataset/` shows clean, zero modifications)  
**Output Checksum**: Verified Unchanged (`c2173c42197e503ba349eb2cad214b1f9276c6caa9a9e9308bae836e3c109d24`)  
**Final Verdict**: **SAFE UNDER TESTED CONDITIONS**  

---

## 1. Executive Summary

This independent read-only audit evaluated the `ACCOUNT_TOMBSTONE` resolution rule implemented in `code/src/rule_engine.py` (and invoked in `code/src/pipeline.py`), inspecting both its theoretical safety properties under challenge rules and its empirical behavior across all 550 cases (32 public sample cases and 518 evaluation cases).

### Core Audit Conclusions
1. **Mathematical Grounding**: The rule does **not** assume all data is deleted when a tombstone is present. It strictly resolves the associated *primary account* (`account_<id>` in `account_service`) to `ResourceState.ABSENT` when affirmative evidence (`deleted_customer_references` snapshot proving `account_status: 'DELETED'`) supersedes historical pre-deletion activity.
2. **Robust Multi-Layered Safeguards**:
   - Explicit identifier matching (`subject_reference` / canonical `user_id`).
   - Strict direct PII removal verification (`tombstone_direct_pii_removed is True`).
   - Temporal validation (`timestamp <= audit_at`).
   - Rejection on conflicting direct observations (`obs_dt >= t_time`).
   - Rejection on post-tombstone writes or recreation (`act_dt > t_time`).
   - Independent verification in `completion_validator.py` (`TOMBSTONE_DIRECT_PII_EXPOSED` guard).
3. **Counterexample Defense Verified**: All 5 noncompliant tombstones in the dataset (`tombstone_9178`, `3745`, `7389`, `8095`, `8648`) are successfully caught. Zero false `COMPLETE` classifications are emitted.
4. **Empirical Impact**:
   - Recovers `case_31` from `INCOMPLETE` to `COMPLETE` with 100% compliant verification steps.
   - Public sample accuracy: **90.62%** (29/32), Macro-F1: **0.8798**, COMPLETE precision: **100.0%**, Step F1: **54.15%**.
   - Full 518 dataset: 162 COMPLETE, 346 INCOMPLETE, 10 NOT_APPLICABLE (0 validator errors).

---

## 2. Audit A — Search Tombstone Counterexamples

### 2.1 Implementation Analysis (`code/src/rule_engine.py`)
The rule `apply_account_tombstone_resolution` checks seven sequential prerequisites before resolving any account:

```text
Prerequisite 1: Tombstone Identity & Classification
   getattr(t_assess, "is_tombstone") or t_rid.startswith("tombstone_") or category == "ACCOUNT_TOMBSTONE"

Prerequisite 2: Strict Privacy & Compliance
   t_assess.policy_satisfied is True
   t_assess.observed_state == ResourceState.REDACTED
   getattr(t_assess, "tombstone_direct_pii_removed") is True

Prerequisite 3: Evidence Grounding
   t_assess.supporting_evidence_ids is non-empty

Prerequisite 4: Identity Cluster Grounding
   subj_ref in cluster_user_ids (matching stable internal user reference)

Prerequisite 5: Account Association
   a_rid is associated with subject (canonical account_id or numerical suffix match)

Prerequisite 6: Zero Conflicting Direct Observations
   All direct observations of account have obs_dt < t_time

Prerequisite 7: Zero Post-Tombstone Writes / Recreation Activity
   All activity events for account have act_dt <= t_time
```

### 2.2 Forensic Inspection of the 5 Noncompliant Tombstones

| Tombstone ID | Evidence File | Linked Case | Subject ID | Exposed Direct PII | Pipeline Handling | Emitted Operation | Confirmed Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `tombstone_9178` | `evidence_51` (`.json`) | `case_32` (sample) | `user_542` | Name (`Kofi Addo`), Email, Phone, Email Hash | Rejected by `pii_removed` check; flagged by validator | `REPORT_EXPOSED_PII` (`PRESENT`) | **Correctly INCOMPLETE** |
| `tombstone_3745` | `evidence_52` (`.sql`) | `case_548` (eval) | `user_548` | Name (`Sofía Fernández`), Email, Phone, Email Hash | Rejected by `pii_removed` check; flagged by validator | `REPORT_EXPOSED_PII` (`PRESENT`) | **Correctly INCOMPLETE** |
| `tombstone_7389` | `evidence_52` (`.sql`) | `case_550` (eval) | `user_550` | Name (`Camille Moreau`), Email, Email Hash | Rejected by `pii_removed` check; flagged by validator | `REPORT_EXPOSED_PII` (`PRESENT`) | **Correctly INCOMPLETE** |
| `tombstone_8095` | `evidence_52` (`.sql`) | `case_546` (eval) | `user_546` | Name (`Mariana Costa`), Phone, Email Hash | Rejected by `pii_removed` check; flagged by validator | `REPORT_EXPOSED_PII` (`PRESENT`) | **Correctly INCOMPLETE** |
| `tombstone_8648` | `evidence_52` (`.sql`) | `case_544` (eval) | `user_544` | Name (`Keiko Ito`), Email, Email Hash | Rejected by `pii_removed` check; flagged by validator | `REPORT_EXPOSED_PII` (`PRESENT`) | **Correctly INCOMPLETE** |

**Finding**: All five noncompliant tombstones violate the `REDACT` rule because direct identifiers remain exposed in the records. None of them trigger account resolution. Each linked case is properly identified as `INCOMPLETE` with a finding of `REPORT_EXPOSED_PII` on the tombstone, followed by proposed remediation (`REDACT_RECORD`).

### 2.3 Forensic Inspection of the 5 Compliant Tombstones

| Tombstone ID | Evidence File | Linked Case | Subject ID | Direct PII Status | Account Activity History | Emitted Steps | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| `tombstone_440` | `evidence_51` (`.json`) | `case_31` (sample) | `user_541` | All direct PII `null`; status `DELETED` | `activity_303` (2026-01-26, pre-tombstone update) | `VERIFY_RECORD_ABSENT` (`account_541`), `VERIFY_RECORD_PRESENT` (`audit_record_6909`), `VERIFY_RECORD_REDACTED` (`tombstone_440`) | **COMPLETE** |
| `tombstone_205` | `evidence_52` (`.sql`) | `case_543` (eval) | `user_543` | All direct PII `null`; status `DELETED` | None | `VERIFY_RECORD_PRESENT` (`audit_record_6244`), `VERIFY_RECORD_REDACTED` (`tombstone_205`) | **COMPLETE** |
| `tombstone_3963` | `evidence_52` (`.sql`) | `case_549` (eval) | `user_549` | All direct PII `null`; status `DELETED` | None | `VERIFY_RECORD_PRESENT` (`audit_record_1491`), `VERIFY_RECORD_REDACTED` (`tombstone_3963`) | **COMPLETE** |
| `tombstone_8774` | `evidence_52` (`.sql`) | `case_547` (eval) | `user_547` | All direct PII `null`; status `DELETED` | None | `VERIFY_RECORD_PRESENT` (`audit_record_7352`), `VERIFY_RECORD_REDACTED` (`tombstone_8774`) | **COMPLETE** |
| `tombstone_946` | `evidence_52` (`.sql`) | `case_545` (eval) | `user_545` | All direct PII `null`; status `DELETED` | None | `VERIFY_RECORD_PRESENT` (`audit_record_5041`), `VERIFY_RECORD_REDACTED` (`tombstone_946`) | **COMPLETE** |

### 2.4 Investigation of Potential Failure Modes

1. **Cross-Account / Cross-System Tombstone Linkage**:
   - *Risk*: A tombstone for `user_A` resolving an account belonging to `user_B`.
   - *Audit Finding*: The rule explicitly requires that `subj_ref` matches the request's `cluster_user_ids`. If `subj_ref` is absent or points to another user, resolution is aborted. (Verified by regression test `test_mismatched_subject_reference_rejected`).
2. **Lingering PII in Other Records**:
   - *Risk*: A tombstone is compliant, but the user's data remains in support records, analytics, exports, or search indexes.
   - *Audit Finding*: The rule *only* resolves the primary account. All other candidate resources (support conversations, search indexes, backups, analytics) are evaluated independently by `completion_validator.py`. If *any* other resource violates policy or has active resurrection flows, the case evaluates to `INCOMPLETE`.
3. **Post-Tombstone Writes or Account Recreation**:
   - *Risk*: An account was deleted and tombstoned, but an automated workflow recreated or updated it afterward.
   - *Audit Finding*: The rule inspects all `SystemActivity` events for the account. If any event has `act_dt > t_time`, resolution is aborted. (Verified by regression test `test_post_tombstone_activity_prevents_resolution`).
4. **Conflicting Observations After Tombstone**:
   - *Risk*: A later snapshot shows the account present.
   - *Audit Finding*: The rule inspects all direct observations. If any observation has `obs_dt >= t_time` showing presence, resolution is aborted. (Verified by regression test `test_post_tombstone_observation_prevents_resolution`).
5. **Fabricated Evidence References**:
   - *Risk*: The verification step for `account_541` cites an arbitrary evidence ID.
   - *Audit Finding*: In `customer_data_snapshot_bundle_20260915.json` (`evidence_51`), lines 4-10 contain the official snapshot of `account_service.customer_profiles`, proving zero customer profile records exist. The evidence ID cited (`evidence_51`) is the exact physical file proving both empty profiles and tombstone creation.

---

## 3. Audit B — Measure Full Dataset Impact

### 3.1 Quantitative Summary
- **Total raw tombstone observations discovered**: 18 entries across `evidence_51` and `evidence_52`.
- **Unique tombstone IDs**: 10
- **Compliant tombstones**: 5 (`tombstone_440`, `205`, `3963`, `8774`, `946`)
- **Noncompliant tombstones**: 5 (`tombstone_9178`, `3745`, `7389`, `8095`, `8648`)
- **Total cases linked to tombstones**: 10 cases (2 sample cases: `case_31`, `case_32`; 8 evaluation cases: `case_543` to `case_550`)
- **Cases where status changed**: Exactly **1 case** (`case_31`: `INCOMPLETE` → `COMPLETE`).
- **Cases resolved by the tombstone rule**: Exactly 1 (`case_31`). The 4 compliant evaluation cases (`case_543`, `case_545`, `case_547`, `case_549`) had zero historical account activity in `system_activity.csv`, so their primary accounts were never added as conflicting candidates.
- **Cases with conflicting evidence or post-tombstone writes**: 0 in the actual dataset.
- **Counterfactual Risk**: **5 cases** (`case_32`, `case_544`, `case_546`, `case_548`, `case_550`) would be falsely classified as `COMPLETE` if the `tombstone_direct_pii_removed` and validator safeguards were removed.

### 3.2 Full 518 Dataset Status Distribution
- `COMPLETE`: 162 (31.27%)
- `INCOMPLETE`: 346 (66.80%)
- `NOT_APPLICABLE`: 10 (1.93%)
- Total cases: 518
- Total emitted steps: 2,037
- Structural & semantic validation errors: **0**
- Checksum comparison with promoted root `output.csv`: **0 differences** (SHA-256: `c2173c42197e503ba349eb2cad214b1f9276c6caa9a9e9308bae836e3c109d24`).

---

## 4. Independent Verification & Reproducibility

### 4.1 Automated Test Suite
- Executed: `pytest code/tests/ -q`
- Result: **163 passed in 21.16s** (100% pass rate).
- Zero broken tests, zero skipped tests.

### 4.2 Public Sample Evaluation (32 Authorized Cases)
Evaluated offline using authorized evaluation metrics without inspecting `dataset/sample_output.csv`:

| Evaluation Metric | Baseline Value | Step W Audited Value | Confirmed Delta |
| :--- | :---: | :---: | :---: |
| **Status Accuracy** | 87.50% (28/32) | **90.62% (29/32)** | **+3.12%** |
| **Macro-F1** | 83.33% | **87.98%** | **+4.65%** |
| **COMPLETE Precision** | 100.0% (6/6) | **100.0% (7/7)** | **100.0% (Zero false COMPLETEs)** |
| **COMPLETE Recall** | 60.0% (6/10) | **70.0% (7/10)** | **+10.0%** |
| **INCOMPLETE Precision** | 84.62% (22/26) | **88.00% (22/25)** | **+3.38%** |
| **INCOMPLETE Recall** | 100.0% (22/22) | **100.0% (22/22)** | **100.0% (Zero regressions)** |
| **Step-Level F1** | 52.92% | **54.15%** | **+1.23%** |
| **Step Precision** | 66.41% | **66.67%** | **+0.26%** |
| **Step Recall** | 44.04% | **45.60%** | **+1.56%** |
| **Sequence Accuracy** | 3.12% (1/32) | **3.12% (1/32)** | Unchanged |

### 4.3 Deliverable & Checksum Verification
- `output.csv` SHA-256: `c2173c42197e503ba349eb2cad214b1f9276c6caa9a9e9308bae836e3c109d24` (Verified unchanged).
- `dataset/` repository status: Verified clean and untouched.
- `log.txt`: Verified unmodified during this audit.

---

## 5. Final Audit Verdict

### **VERDICT: SAFE UNDER TESTED CONDITIONS**

**Justification**:
1. The rule is grounded in explicit evidence and respects challenge specifications.
2. It does not introduce any false `COMPLETE` classifications (COMPLETE precision is 100.0%).
3. Noncompliant tombstones with exposed PII are strictly rejected.
4. All 163 tests pass, validator reports 0 errors across 518 cases, and all integrity constraints are fully satisfied.
5. In accordance with the stop condition, no further changes, optimizations, or promotions were performed.
