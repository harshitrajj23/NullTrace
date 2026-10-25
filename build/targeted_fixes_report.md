# NullTrace — Step L: Targeted Accuracy Improvements Report

**Date:** 2026-10-25  
**Harness / Tool:** antigravity-ide  
**Model:** Gemini 3.8 Flash (Medium)  
**Execution Decision:** MODEL_OFF (Deterministic rule-based execution, 0 external API calls, 0 network requests, 0 paid spend)  
**Target File:** `build/targeted_fixes_report.md`

---

## 1. Executive Summary

In accordance with the diagnostic findings documented in `build/incomplete_case_diagnostic.md`, Step L implements two targeted, evidence-grounded improvements:
1. **Canonical Account ID Linkage**: Resolving subject identifiers (`user_X`) to canonical primary account resources (`account_X` / `account_{int:03d}`) with strict corroboration and leading-zero semantics.
2. **Support Ticket Redaction-State Interpretation**: Distinguishing verified historical redactions (`REDACTED`) from active PII exposure (`PRESENT`) across structured snapshots, service exports, SQL snapshots, text handovers, and logs.

Both fixes are backed by dedicated regression test suites and verified across the complete 518-case evaluation dataset.

### Baseline vs New Prediction Distribution

| Metric | Baseline (`build/nulltrace_integrated.csv`) | New (`build/nulltrace_integrated.csv`) | Net Delta |
|---|---|---|---|
| **Total Evaluation Requests** | 518 | 518 | 0 |
| **COMPLETE** | 105 | 113 | +8 |
| **INCOMPLETE** | 403 | 395 | -8 |
| **NOT_APPLICABLE** | 10 | 10 | 0 |
| **Total Steps Emitted** | 1,365 | 1,353 | -12 |
| **Validation Failures** | 0 | 0 | 0 |
| **Test Suite Passed** | 137 / 137 | 146 / 146 | +9 tests |

---

## 2. Source Files Changed

1. `code/src/resource_link.py`:
   - Implemented `get_canonical_account_id(user_id)` supporting leading-zero padding (`user_01` -> `account_001`, `user_8741` -> `account_8741`).
   - Implemented `check_canonical_account_corroboration()` with multiple strict safeguards:
     - Rejects canonical derivation if the identity cluster already contains a distinct, directly grounded `account_` resource in evidence observations (e.g., `user_421` is explicitly linked to `account_2420` in `evidence_40`).
     - Rejects if the candidate account is linked to conflicting `user_id` or `email` values in evidence observations or system activity details.
     - Requires corroborating activity row or evidence snapshot originating from/targeting `account_service`.
   - Updated `link_cluster_resources()` to perform corroborated canonical account linking (Pass 4) with `reason_code="CANONICAL_ACCOUNT_MATCH"` and `strength="CONFIRMED"`.

2. `code/src/evidence_extraction.py`:
   - Updated `JsonRecordExtractor`:
     - Added `customer_reference` to checked snapshot identifier fields.
     - In snapshot support records and service exports (`support_platform`), checks for explicit redaction markers (`message_text == "[REDACTED]"` or `requester_email=None`). Maps to `ResourceState.REDACTED` if redacted, or `ResourceState.PRESENT` if unredacted direct identifiers persist.
   - Updated `SqlSnapshotExtractor`:
     - Inspects support conversations in SQLite exports for `[REDACTED]` message text and masks, assigning `ResourceState.REDACTED`.
   - Updated `PlainTextExtractor`:
     - Explicitly maps `outcome == 'REDACTED'` -> `ResourceState.REDACTED`, `ANONYMIZED` -> `ResourceState.ANONYMIZED`, `IDENTIFIABLE` -> `ResourceState.PRESENT`.
   - Updated `LogRecordExtractor`:
     - Recognizes `support_ticket_read_completed` with null parameters as `ResourceState.REDACTED`.

3. `code/src/state_reconstruction.py`:
   - In `load_all_evidence_observations()`, distinguishes `REDACTED` vs `PRESENT` support ticket states.

4. `code/src/pipeline.py`:
   - Updated candidate resource discovery to supply `all_obs` to `link_cluster_resources()` and discover corroborated canonical accounts when no account is directly linked.

5. `code/tests/test_canonical_account_link.py` (New):
   - 5 comprehensive regression tests covering leading zeros, valid linkage, unrelated account rejection, missing snapshot conservatism, and remaining account remediation.

6. `code/tests/test_support_ticket_redaction.py` (New):
   - 4 comprehensive regression tests covering explicit historical redaction, active unredacted PII, missing evidence conservatism, and contradictory evidence handling.

---

## 3. Detailed Rules Implemented

### 3.1 Canonical Account ID Linkage Rules
- **Rule 1.1 (Leading-Zero Semantics)**: `user_{N}` derives `account_{int(N):03d}` for `int(N) < 1000`, and `account_{N}` for `int(N) >= 1000`.
- **Rule 1.2 (Direct Grounding Priority)**: If evidence observations already link the subject to an existing `account_` resource (such as `account_2420` for `user_421`), canonical derivation is suppressed.
- **Rule 1.3 (Conflicting Identity Guard)**: If candidate `canonical_rid` appears in any evidence observation or activity log with an identifier belonging to another subject, it is unconditionally rejected.
- **Rule 1.4 (Corroboration Requirement)**: A canonical account is only admitted if corroborated by an activity event in `system_activity` or an observation in evidence files.
- **Rule 1.5 (Absence Is Not Deletion)**: A canonical account without a post-event verification snapshot remains in `UNKNOWN` state, ensuring `INCOMPLETE` is retained.

### 3.2 Support Ticket Redaction-State Rules
- **Rule 2.1 (Explicit Redaction Recognition)**: Support tickets where `message_text` contains `[REDACTED]` and direct identifiers (`requester_email`, `requester_phone`, `requester_name`) are null/masked are assigned `ResourceState.REDACTED`.
- **Rule 2.2 (Active PII Detection)**: Support tickets where direct personal data remains in cleartext are assigned `ResourceState.PRESENT`, generating `REPORT_EXPOSED_PII` and `REDACT_RECORD`.
- **Rule 2.3 (Conservatism on Missing / Contradictory Evidence)**: If redaction cannot be verified or conflicting snapshots exist, state defaults to `UNKNOWN` with `has_conflict=True`, retaining `INCOMPLETE`.

---

## 4. Test Suite Results

### 4.1 Focused Regression Tests
Ran `pytest code/tests/test_canonical_account_link.py code/tests/test_support_ticket_redaction.py -v`:
- `test_canonical_id_derivation_leading_zeros`: PASSED
- `test_1_supported_canonical_mapping_resolves_unlinked_resource`: PASSED
- `test_2_unrelated_account_similar_suffix_rejected`: PASSED
- `test_3_missing_snapshot_not_interpreted_as_deletion`: PASSED
- `test_4_supported_mapping_resource_remains_present_requires_remediation`: PASSED
- `test_1_explicitly_verified_historical_redaction`: PASSED
- `test_2_active_unredacted_direct_identifier`: PASSED
- `test_3_missing_redaction_evidence`: PASSED
- `test_4_contradictory_redaction_evidence`: PASSED
**Result:** 9 passed in 0.03s.

### 4.2 Full Test Suite
Ran `pytest -v`:
- Total tests: 146
- Passed: 146
- Failed / Errored: 0
- Execution time: 20.61s
- Prior baseline: 137 passed in 20.07s (+9 new regression tests).

---

## 5. Prediction Analysis & Case Transition Details

A total of 24 cases changed status between baseline and the improved pipeline.

### 5.1 Cases Changing from INCOMPLETE to COMPLETE (16 Cases)
- **Cases:** `case_151`, `case_191`, `case_231`, `case_277`, `case_324`, `case_331`, `case_335`, `case_351`, `case_41`, `case_463`, `case_464`, `case_480`, `case_532`, `case_77`, `case_81`, `case_82`.
- **Root Cause & Supporting Evidence:**
  - In the previous baseline, each of these cases was classified as `INCOMPLETE` because historical support ticket records (e.g. `support_3964` in `evidence_22`, `support_2036` in `evidence_26`, `support_7249` in `evidence_31`, `support_008` in `evidence_07`) were universally assigned `ResourceState.PRESENT`, falsely emitting `[FINDING] support_platform ... REPORT_EXPOSED_PII PRESENT`.
  - Inspection of the backing evidence files (`evidence_03`, `evidence_07`, `evidence_22`, `evidence_26`, `evidence_31`, `evidence_45`, `evidence_49`, `evidence_65`, `evidence_71`) proved that each ticket record had already been redacted: direct identifiers were null and message texts were masked with `[REDACTED]`.
  - With the redaction fix, each ticket emits a valid evidence-backed `[VERIFICATION] support_platform ... VERIFY_RECORD_REDACTED REDACTED (ev: evidence_XX)`.
  - Combined with existing verified absent accounts, retained security audit records, and blocked backups, each case strictly satisfies all evidence-backed completion rules.

### 5.2 Cases Changing from COMPLETE to INCOMPLETE (8 Cases)
- **Cases:** `case_128`, `case_179`, `case_311`, `case_332`, `case_345`, `case_408`, `case_412`, `case_60`.
- **Root Cause & Supporting Evidence:**
  - In the baseline run, these 8 cases were previously declared `COMPLETE` with only a single verification step: `[VERIFICATION] security_service audit_record_XXXX VERIFY_RECORD_PRESENT PRESENT`.
  - The baseline had completely failed to link the subject's primary account, falsely declaring completion while ignoring the account status.
  - With canonical account linkage:
    - `case_128`: Linked `account_126`, which has `activity_1108` showing an update/presence. Emits `[FINDING] account_service account_126 REPORT_REMAINING_RECORD PRESENT`.
    - `case_179`: Linked `account_177`, which has `activity_2215` showing presence. Emits `[FINDING] account_service account_177 REPORT_REMAINING_RECORD PRESENT`.
    - `case_332`: Linked `account_330`, which has `activity_878` showing an active profile preference update. Emits `[FINDING] account_service account_330 REPORT_REMAINING_RECORD PRESENT`.
    - `case_311`, `case_345`, `case_408`, `case_412`, `case_60`: Linked accounts (`account_309`, `account_343`, `account_406`, `account_410`, `account_058`). While activity events reference these accounts, there is no post-audit verification snapshot in evidence proving their deletion at `audit_at`. Their state remains `UNKNOWN`/unverified, properly retaining `INCOMPLETE`.
  - **Verdict:** The baseline classifications for these 8 cases were false positives. The improved pipeline correctly eliminated these unsupported `COMPLETE` decisions.

---

## 6. Verification and Validation of Predictions

All 518 cases in `build/nulltrace_integrated.csv` were validated against the full grading schema and constraints:
1. **Case Count**: Exactly 518 rows, matching `dataset/deletion_requests.csv` 1-to-1.
2. **Status Values**: Exactly `COMPLETE` (113), `INCOMPLETE` (395), `NOT_APPLICABLE` (10).
3. **NOT_APPLICABLE Invariant**: Exactly 10 cases, all with `steps_json = []`.
4. **COMPLETE Invariant**: All 113 `COMPLETE` cases contain only `VERIFICATION` steps, and every single step cites an authoritative, non-empty `evidence_id` from the evidence manifest, system activity, or audit log.
5. **Phase & Operation Ordering**: All steps strictly follow `FINDING` -> `REMEDIATION` -> `VERIFICATION` and consecutive `step_no` numbering starting at 1.
6. **Grammar & Semantics**: 0 invalid operations, 0 invalid states, 0 empty required fields.

---

## 7. Submission Artifact & Directory Integrity Confirmation

- `dataset/`: Completely unmodified (read-only).
- `dataset/sample_output.csv`: Never accessed or read by production code.
- `output.csv` (repository root): Untouched.
- `problem_statement.md`: Untouched.
- No external network requests or API calls were executed (`DECISION: MODEL_OFF`).
