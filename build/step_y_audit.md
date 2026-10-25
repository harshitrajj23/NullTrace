# NullTrace: Step Y Audit Report — Repair and Verify

**Date**: 2026-10-25  
**Harness**: antigravity-ide  
**Model Policy**: DECISION: MODEL_OFF (Zero external API calls, deterministic local execution)  
**Status**: Step Y Repair and Verification Completed (Candidate isolated in `build/nulltrace_step_y.csv`; root `output.csv` untampered)

---

## 1. Reconciliation of Reports & Hashes

### 1.1 SHA-256 Hash Verification

SHA-256 checksums were recomputed directly from the filesystem:

| File | SHA-256 Checksum | Match Status |
| :--- | :--- | :--- |
| `output.csv` | `c2173c42197e503ba349eb2cad214b1f9276c6caa9a9e9308bae836e3c109d24` | **Identical** to Candidate Step R |
| `build/nulltrace_candidate_step_r.csv` | `c2173c42197e503ba349eb2cad214b1f9276c6caa9a9e9308bae836e3c109d24` | **Identical** to `output.csv` |
| `build/root_output_backup_step_q.csv` | `788302aaea25bf22e1d84ce376b7450700285712dc356fb1b90ee5fc4927a650` | Preserved Step Q baseline backup |

**Confirmation**: `output.csv` and `build/nulltrace_candidate_step_r.csv` are identical byte-for-byte. `build/root_output_backup_step_q.csv` represents the earlier Step Q baseline prior to candidate promotion.

### 1.2 Direct Script Step Counts from `output.csv`

Direct programmatic inspection of `output.csv` yielded:

- **Total Cases**: 518 (`INCOMPLETE`: 346, `COMPLETE`: 162, `NOT_APPLICABLE`: 10)
- **Total Emitted Steps**: 2,037
  - `FINDING` phase: **586**
  - `REMEDIATION` phase: **586**
  - `VERIFICATION` phase: **865** (586 post-remediation verifications + 279 verification steps for the 162 `COMPLETE` cases)

#### Explanation of Step T vs Step X Mismatch:
In `build/step_t_final_promotion_report.md` (lines 59–61), an intermediate draft breakdown was mistakenly reported as `FINDING: 777, REMEDIATION: 601, VERIFICATION: 659` (summing to 2,037). However, the actual CSV artifact `build/nulltrace_candidate_step_r.csv` that was promoted strictly enforces a 1:1 finding-to-remediation invariant for all incomplete cases (586 findings paired with 586 remediations and 586 post-remediation verifications, plus 279 verification steps across the 162 COMPLETE cases = 865 verifications). Step X independently counted steps directly from the CSV and reported the correct breakdown (586 / 586 / 865).

### 1.3 32-Case Accuracy Shift Explanation (87.50% to 90.62%)

- **Target Discrepancy**: `output.csv` contains predictions for the 518 evaluation requests (`case_33` to `case_550`). It does not contain the 32 public sample cases (`case_01` to `case_32`).
- **Code Change Origin**: In Step V, the `apply_account_tombstone_resolution` rule was added to `code/src/rule_engine.py`.
- **Public Sample Impact**: When evaluated against `dataset/sample_deletion_requests.csv`, `case_31` possessed a valid compliant tombstone (`tombstone_440` in `evidence_15`), which resolved its primary account to `ABSENT` with direct PII removed. This transitioned `case_31` from `INCOMPLETE` to `COMPLETE` under the evaluator (`code/evaluation/evaluate_predictions.py`), improving accuracy from 28/32 (87.50%) to 29/32 (90.62%).
- **Why `output.csv` Did Not Change**: In Step V and Step W, instructions explicitly prohibited overwriting root `output.csv`. Additionally, across the 518 evaluation cases, the 8 tombstone cases (`case_543`–`case_550`) already had zero account activity in `system_activity.csv`, meaning their predictions were already stable. Thus `output.csv` remained unchanged while sample accuracy improved.

---

## 2. Empty INCOMPLETE Rows Audit & Resolution

The 26 `INCOMPLETE` rows with `steps_json = []` in `output.csv` were:
`case_127`, `case_168`, `case_170`, `case_175`, `case_264`, `case_288`, `case_292`, `case_311`, `case_345`, `case_372`, `case_408`, `case_412`, `case_413`, `case_414`, `case_416`, `case_417`, `case_418`, `case_420`, `case_44`, `case_46`, `case_51`, `case_520`, `case_522`, `case_60`, `case_61`, `case_63`.

### 2.1 19 Resolved Cases (Supporting Evidence/Activity Found)

For 19 cases, subject-linked resources with valid supporting evidence or activity IDs at or before `audit_at` were identified. Compliant `FINDING`, `REMEDIATION`, and `VERIFICATION` steps were produced following spec grammar and sequence:

1. **`case_127`**: `account_6805` (activity `activity_3113` on 2026-08-05 <= audit_at 2026-08-17) -> FINDING `REPORT_REMAINING_RECORD` (PRESENT, `activity_3113`), REMEDIATION `DELETE_RECORD` (ABSENT, ""), VERIFICATION `VERIFY_RECORD_ABSENT` (ABSENT, "").
2. **`case_168`**: `export_4102` (activity `activity_2811` on 2026-07-14 <= audit_at 2026-07-28) -> FINDING `REPORT_REMAINING_RECORD` (PRESENT, `activity_2811`), REMEDIATION `DELETE_RECORD` (ABSENT, ""), VERIFICATION `VERIFY_RECORD_ABSENT` (ABSENT, "").
3. **`case_175`**: `account_246` (activity `activity_2642` on 2026-07-03 <= audit_at 2026-07-23) -> FINDING `REPORT_REMAINING_RECORD` (PRESENT, `activity_2642`), REMEDIATION `DELETE_RECORD` (ABSENT, ""), VERIFICATION `VERIFY_RECORD_ABSENT` (ABSENT, "").
4. **`case_264`**: 
   - `backup_3250` (activity `activity_2118`): `REPORT_RESTORE_RISK` -> `BLOCK_RESTORE` -> `VERIFY_RESTORE_BLOCKED`.
   - `data_flow_4885` (activity `activity_2117`): `REPORT_ACTIVE_DATA_FLOW` -> `DISABLE_DATA_FLOW` -> `VERIFY_DATA_FLOW_DISABLED`.
   - `support_9996` (activity `activity_2116`): `REPORT_EXPOSED_PII` -> `REDACT_RECORD` -> `VERIFY_RECORD_REDACTED`.
5. **`case_288`**: `export_7906` (activity `activity_1909` on 2026-05-15 <= audit_at 2026-05-29) -> FINDING `REPORT_REMAINING_RECORD` (PRESENT, `activity_1909`), REMEDIATION `DELETE_RECORD` (ABSENT, ""), VERIFICATION `VERIFY_RECORD_ABSENT` (ABSENT, "").
6. **`case_292`**: `backup_1825` (activity `activity_1848` on 2026-05-12 <= audit_at 2026-05-29) -> FINDING `REPORT_RESTORE_RISK` (ACTIVE, `activity_1848`), REMEDIATION `BLOCK_RESTORE` (BLOCKED, ""), VERIFICATION `VERIFY_RESTORE_BLOCKED` (BLOCKED, "").
7. **`case_311`**: `search_3004` (in SQL replica evidence `evidence_29` at audit_at 2026-05-19) -> FINDING `REPORT_REMAINING_RECORD` (PRESENT, `evidence_29`), REMEDIATION `DELETE_RECORD` (ABSENT, ""), VERIFICATION `VERIFY_RECORD_ABSENT` (ABSENT, "").
8. **`case_372`**: `export_5081` (activity `activity_1239` on 2026-04-01 <= audit_at 2026-04-19) -> FINDING `REPORT_REMAINING_RECORD` (PRESENT, `activity_1239`), REMEDIATION `DELETE_RECORD` (ABSENT, ""), VERIFICATION `VERIFY_RECORD_ABSENT` (ABSENT, "").
9. **`case_413`**: `analytics_4523` (activity `activity_858` on 2026-03-05 <= audit_at 2026-03-25) -> FINDING `REPORT_EXPOSED_PII` (PRESENT, `activity_858`), REMEDIATION `ANONYMIZE_RECORD` (ANONYMIZED, ""), VERIFICATION `VERIFY_RECORD_ANONYMIZED` (ANONYMIZED, "").
10. **`case_414`**: `support_3768` (activity `activity_859` on 2026-03-05 <= audit_at 2026-03-25) -> FINDING `REPORT_EXPOSED_PII` (PRESENT, `activity_859`), REMEDIATION `REDACT_RECORD` (REDACTED, ""), VERIFICATION `VERIFY_RECORD_REDACTED` (REDACTED, "").
11. **`case_418`**: `support_9464` (activity `activity_815` on 2026-03-02 <= audit_at 2026-03-25) -> FINDING `REPORT_EXPOSED_PII` (PRESENT, `activity_815`), REMEDIATION `REDACT_RECORD` (REDACTED, ""), VERIFICATION `VERIFY_RECORD_REDACTED` (REDACTED, "").
12. **`case_420`**: `export_389` (activity `activity_753` on 2026-02-27 <= audit_at 2026-03-25) -> FINDING `REPORT_REMAINING_RECORD` (PRESENT, `activity_753`), REMEDIATION `DELETE_RECORD` (ABSENT, ""), VERIFICATION `VERIFY_RECORD_ABSENT` (ABSENT, "").
13. **`case_44`**: `backup_6266` (activity `activity_3856` on 2026-09-15 <= audit_at 2026-09-26) -> FINDING `REPORT_RESTORE_RISK` (ACTIVE, `activity_3856`), REMEDIATION `BLOCK_RESTORE` (BLOCKED, ""), VERIFICATION `VERIFY_RESTORE_BLOCKED` (BLOCKED, "").
14. **`case_46`**: `tombstone_17` (activity `activity_4011` on 2026-03-10 <= audit_at 2026-03-11) -> FINDING `REPORT_EXPOSED_PII` (PRESENT, `activity_4011`), REMEDIATION `REDACT_RECORD` (REDACTED, ""), VERIFICATION `VERIFY_RECORD_REDACTED` (REDACTED, "").
15. **`case_51`**: `backup_7809` (activity `activity_3738` on 2026-09-09 <= audit_at 2026-09-26) -> FINDING `REPORT_RESTORE_RISK` (ACTIVE, `activity_3738`), REMEDIATION `BLOCK_RESTORE` (BLOCKED, ""), VERIFICATION `VERIFY_RESTORE_BLOCKED` (BLOCKED, "").
16. **`case_520`**: `support_9251` (activity `activity_50` on 2026-01-09 <= audit_at 2026-02-03) -> FINDING `REPORT_EXPOSED_PII` (PRESENT, `activity_50`), REMEDIATION `REDACT_RECORD` (REDACTED, ""), VERIFICATION `VERIFY_RECORD_REDACTED` (REDACTED, "").
17. **`case_522`**: `support_8538` (activity `activity_296` on 2026-01-26 <= audit_at 2026-02-03) -> FINDING `REPORT_EXPOSED_PII` (PRESENT, `activity_296`), REMEDIATION `REDACT_RECORD` (REDACTED, ""), VERIFICATION `VERIFY_RECORD_REDACTED` (REDACTED, "").
18. **`case_63`**: `marketing_001` (activity `activity_4008` on 2026-09-16 <= audit_at 2026-09-17) -> FINDING `REPORT_REMAINING_RECORD` (PRESENT, `activity_4008`), REMEDIATION `DELETE_RECORD` (ABSENT, ""), VERIFICATION `VERIFY_RECORD_ABSENT` (ABSENT, "").
19. **`case_61`**: `object_19` (activity `activity_4007` on 2026-02-13 <= audit_at 2026-02-14, attachment belonging solely to subject) -> FINDING `REPORT_REMAINING_RECORD` (PRESENT, `activity_4007`), REMEDIATION `DELETE_RECORD` (ABSENT, ""), VERIFICATION `VERIFY_RECORD_ABSENT` (ABSENT, "").

### 2.2 7 Unresolved Cases (No Supporting Pre-Audit Evidence Exists)

Under the strict instruction: *"If no supporting evidence exists, do not invent steps. List the case with its reason and stop for my decision. Do not guess an 'unknown' operation, because the spec does not define one."*

1. **`case_60`** (`user_58`): Retained `audit_record_629` is confirmed compliant in `evidence_05`. The only account activity (`activity_3966` for `account_058`) occurred on 2026-09-26, which is 5 days after `audit_at` (2026-09-21T10:00:00Z). No pre-audit evidence exists for any account record.
2. **`case_170`** (`user_168`): Primary account `account_665` is verified `ABSENT` in `evidence_16`, and `audit_record_4443` is retained. `search_3619` appears only in a trace log dated 2026-07-30, which is post-cutoff (audit cutoff: 2026-07-28T06:00:00Z). No pre-audit evidence exists.
3. **`case_345`** (`user_343`): `audit_record_454` is compliant in `evidence_71`. Activity for `account_343` (`activity_2093`) occurred on 2026-05-28, which is post-cutoff (audit cutoff: 2026-04-29T09:00:00Z). No pre-audit evidence exists.
4. **`case_408`** (`user_406`): `audit_record_4216` is compliant in `evidence_38`. Activity for `account_406` (`activity_3055`) occurred on 2026-08-02, which is post-cutoff (audit cutoff: 2026-03-30T10:00:00Z). No pre-audit evidence exists.
5. **`case_412`** (`user_410`): `audit_record_5637` is compliant in `evidence_38`. Activity for `account_410` (`activity_3662`) occurred on 2026-09-05, which is post-cutoff (audit cutoff: 2026-03-30T10:00:00Z). No pre-audit evidence exists.
6. **`case_416`** (`user_414`): Keiko Sato. The subject's identifiers appear only in ephemeral debug logs (`profile_lookup_started`, `index_query_started` with `resource_id=None`) in `evidence_39`. Zero concrete resources or activity records exist in the entire dataset.
7. **`case_417`** (`user_415`): Soo-jin Kim. Identifiers appear only in ephemeral debug logs with `resource_id=None` in `evidence_39`. Zero concrete resources or activity records exist in the entire dataset.

---

## 3. Audit of 162 COMPLETE Rows

All 162 `COMPLETE` cases in `output.csv` were checked against the 4 rules:
1. **Every system the cluster touches has a verifying evidence ID**: Checked across all candidate resources. 100% verified.
2. **No active sync, import, replication, or restore event is left enabled or unverified**: 0 active resurrection risks detected at `audit_at`.
3. **Every retained record shows only permitted identifiers**: 0 tombstones or support conversations expose direct PII.
4. **Required retained records are present**: All required security audit records and blocked backup archives are present in direct snapshot evidence.

**Result**: **0 Demotions**. All 162 `COMPLETE` cases are fully grounded in participant-visible evidence.

---

## 4. Candidate Validation (`build/nulltrace_step_y.csv`)

`code.src.ops.validate_steps` was executed across all 518 rows of `build/nulltrace_step_y.csv`:
- **Total rows**: 518 (Header: `case_id,deletion_status,steps_json`)
- **Sorting**: Strictly sorted in ascending order by `case_id`
- **Validation Failures**: **0**
- **Grammar & Semantics**: 100% valid phase order (`FINDING` -> `REMEDIATION` -> `VERIFICATION`), step numbering consecutive from 1, valid operation/state pairings, and zero ungrounded future evidence IDs.
- **Total Emitted Steps**: 2,100 (+63 steps from baseline)
  - `FINDING`: 607
  - `REMEDIATION`: 607
  - `VERIFICATION`: 886

---

## 5. Evaluation on 32 Public Samples

Evaluated using `code/evaluation/evaluate_predictions.py` against `dataset/sample_output.csv`:

| Metric | Score | Detail |
| :--- | :--- | :--- |
| **Status Accuracy** | **90.62%** | **29 / 32 correct** |
| **COMPLETE Precision** | **100.0%** | **7 / 7 (Zero False COMPLETEs)** |
| **COMPLETE Recall** | **70.0%** | **7 / 10 recovered** |
| **INCOMPLETE Precision** | **88.0%** | **22 / 25** |
| **INCOMPLETE Recall** | **100.0%** | **22 / 22 (Zero regressions)** |
| **Misclassified Cases** | `case_01`, `case_02`, `case_04` | False Negatives (Predicted INCOMPLETE, Truth COMPLETE) |
| **Odd Sorted Positions (16 cases)** | **93.75%** | **15 / 16 correct** |
| **Even Sorted Positions (16 cases)** | **87.50%** | **14 / 16 correct** |

---

## 6. Official Submission URL Correction

Typo `wwww.hackerrank.com` was corrected across `AGENTS.md` and repository reports to:
`https://www.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists`
