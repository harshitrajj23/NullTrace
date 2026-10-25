# NullTrace: Step Z2 Audit Report — Candidate Repair & Verification

**Date**: 2026-10-25  
**Harness**: antigravity-ide  
**Model Policy**: DECISION: MODEL_OFF (Deterministic offline execution; zero external API calls)  
**Status**: Step Z2 Candidate Repaired & Verified (`build/nulltrace_step_z2.csv`; root `output.csv` preserved)

---

## 1. Code Path & Tombstone Rule Confirmation

### 1.1 Tombstone Resolution Confirmation
Both `build/nulltrace_step_y.csv` and `build/nulltrace_step_z2.csv` fully incorporate the **`ACCOUNT_TOMBSTONE` Resolution Rule** (`rule_15`, `code/src/rule_engine.py:apply_account_tombstone_resolution` and `assess_resource_policy`):
- All 162 `COMPLETE` cases were audited against tombstone rules, confirming that account references are preserved while prohibited direct identifiers (`name`, `email`, `phone`, `email_hash`) are removed.
- In `case_46`, `tombstone_17` was evaluated under `rule_15` (`ACCOUNT_TOMBSTONE`). Direct PII was found unredacted, triggering policy violation steps (`REPORT_EXPOSED_PII` -> `REDACT_RECORD` -> `VERIFY_RECORD_REDACTED`).

### 1.2 Pipeline Code Path for the 21 Rows
The 21 candidate finding rows originated through the following pipeline modules:
1. `code/src/identity.py:resolve_all`: Resolves normalized identifier clusters from `user_identities.csv` and `user_audit_log.csv`.
2. `code/src/resource_link.py:link_cluster_resources` & `ActivitySubjectIndex`: Matches cluster identifiers against `system_activity.csv` and evidence manifest extractions.
3. `code/src/state_reconstruction.py:reconstruct_resource_state`: Reconstructs temporal state at `audit_at` cutoff.
4. `code/src/rule_engine.py:assess_resource_policy`: Evaluates data category against `deletion_rules.csv` (`rule_01` to `rule_15`).
5. `code/src/planner.py:plan_case` -> `code/src/ops.py:sort_steps`: Emits 1-indexed steps ordered `FINDING` -> `REMEDIATION` -> `VERIFICATION`.

### 1.3 Production Code Grep for Evaluation Files
Grep search for `sample_output.csv` and `sample_evaluation.json` in production code (`code/src/`):
- **`sample_evaluation.json`**: **0 hits** across all production source files.
- **`sample_output.csv`**:
  - `code/src/pipeline.py` (lines 9, 202): Docstrings explicitly stating: *"Never reads sample_output.csv or output.csv"*.
  - `code/src/loader.py` (lines 373–378): Optional diagnostic load of `sample_output.csv` into `Dataset.sample_output`. Verified that `dataset.sample_output` is **never referenced or used anywhere in production pipeline logic** (0 usages).
  - `code/src/identity.py` (line 606): Uncalled standalone diagnostic function `cross_check_sample_resources`.
  - `code/src/resource_link.py` (line 330): Uncalled standalone diagnostic function `cross_check_sample_candidates`.
- **Conclusion**: Production pipeline predictions never inspect, parse, or condition upon `sample_output.csv` or `sample_evaluation.json`.

---

## 2. Removal of Unsupported Activity Links & 4 Supported Cases

Per the instruction to remove every finding whose link came from an activity row with no subject identifier (17 UNSUPPORTED rows across 15 cases):

### 2.1 The 4 Supported Cases (Retained with Full Steps)
1. **`case_311`**: `search_3004` -> Direct evidence `evidence_29` (`customer_data_regional_replicas_20260519.sql` line 32) explicitly contains `email="naledi-mahlangu79@proton.me"` and `customer_reference="user_309"`. Rule: `SUBJECT_USER_ID_MATCH` + `SUBJECT_EMAIL_MATCH` in direct SQL snapshot at audit cutoff.
2. **`case_46`**: `tombstone_17` -> `activity_4011` explicitly states: `Data catalog linked tombstone_17 (user_17) to leonie.g9352@outlook.com and user_17.` Rule: `SUBJECT_USER_ID_MATCH` + `SUBJECT_EMAIL_MATCH`.
3. **`case_61`**: `object_19` -> `activity_4007` explicitly states: `Attachment catalog confirmed object_19 (delivery_confirmation_19.pdf) belongs only to priya.raman@gmail.com and user_07; no other subject is linked.` Rule: `SUBJECT_USER_ID_MATCH` + `SUBJECT_EMAIL_MATCH`.
4. **`case_63`**: `marketing_001` -> `activity_4008` explicitly states: `Data catalog linked marketing_001 (marketing_001) to kwame-mensah@proton.me and user_09.` Rule: `SUBJECT_USER_ID_MATCH` + `SUBJECT_EMAIL_MATCH`.

### 2.2 The 15 Cases / 17 Rows Removed (Reverted to `[]`)
All 17 resources originated from activity records with **zero subject identifiers** (`user_id`, `email`, `phone`, `name`, `hash` all absent):
- `case_127` (`account_6805`, `activity_3113`)
- `case_168` (`export_4102`, `activity_2811`)
- `case_175` (`account_246`, `activity_2642`)
- `case_264` (`support_9996`, `data_flow_4885`, `backup_3250`, activities `activity_2116`, `2117`, `2118`)
- `case_288` (`export_7906`, `activity_1909`)
- `case_292` (`backup_1825`, `activity_1848`)
- `case_372` (`export_5081`, `activity_1239`)
- `case_413` (`analytics_4523`, `activity_858`)
- `case_414` (`support_3768`, `activity_859`)
- `case_418` (`support_9464`, `activity_815`)
- `case_420` (`export_389`, `activity_753`)
- `case_44` (`backup_6266`, `activity_3856`)
- `case_51` (`backup_7809`, `activity_3738`)
- `case_520` (`support_9251`, `activity_50`)
- `case_522` (`support_8538`, `activity_296`)

---

## 3. The 22 Unresolved INCOMPLETE Cases (`build/unresolved_cases.csv`)

Exactly 22 cases are now `INCOMPLETE` with `steps_json = []`. All 22 cases have been written to `build/unresolved_cases.csv`:

| Case ID | Category | Reason Recorded in `build/unresolved_cases.csv` |
| :--- | :--- | :--- |
| **`case_127`** | Unsupported Activity Link | `activity_3113` mentions `account_6805` with zero subject identifiers; snapshot is post-audit cutoff |
| **`case_168`** | Unsupported Activity Link | `activity_2811` mentions `export_4102` with zero subject identifiers |
| **`case_175`** | Unsupported Activity Link | `activity_2642` mentions `account_246` with zero subject identifiers |
| **`case_264`** | Unsupported Activity Link | `activity_2116`, `2117`, `2118` mention `support_9996`, `data_flow_4885`, `backup_3250` with zero subject identifiers |
| **`case_288`** | Unsupported Activity Link | `activity_1909` mentions `export_7906` with zero subject identifiers |
| **`case_292`** | Unsupported Activity Link | `activity_1848` mentions `backup_1825` with zero subject identifiers |
| **`case_372`** | Unsupported Activity Link | `activity_1239` mentions `export_5081` with zero subject identifiers |
| **`case_413`** | Unsupported Activity Link | `activity_858` mentions `analytics_4523` with zero subject identifiers |
| **`case_414`** | Unsupported Activity Link | `activity_859` mentions `support_3768` with zero subject identifiers |
| **`case_418`** | Unsupported Activity Link | `activity_815` mentions `support_9464` with zero subject identifiers |
| **`case_420`** | Unsupported Activity Link | `activity_753` mentions `export_389` with zero subject identifiers |
| **`case_44`** | Unsupported Activity Link | `activity_3856` mentions `backup_6266` with zero subject identifiers |
| **`case_51`** | Unsupported Activity Link | `activity_3738` mentions `backup_7809` with zero subject identifiers |
| **`case_520`** | Unsupported Activity Link | `activity_50` mentions `support_9251` with zero subject identifiers |
| **`case_522`** | Unsupported Activity Link | `activity_296` mentions `support_8538` with zero subject identifiers |
| **`case_60`** | No Pre-Audit Evidence | `account_058` activity (`activity_3966`) is post-audit cutoff; no pre-audit evidence exists |
| **`case_170`** | No Pre-Audit Evidence | `search_3619` trace log is post-audit cutoff; no pre-audit evidence exists |
| **`case_345`** | No Pre-Audit Evidence | `account_343` activity (`activity_2093`) is post-audit cutoff; no pre-audit evidence exists |
| **`case_408`** | No Pre-Audit Evidence | `account_406` activity (`activity_3055`) is post-audit cutoff; no pre-audit evidence exists |
| **`case_412`** | No Pre-Audit Evidence | `account_410` activity (`activity_3662`) is post-audit cutoff; no pre-audit evidence exists |
| **`case_416`** | No Evidence | Keiko Sato: zero resources in activity or evidence (only ephemeral debug lookup logs with `resource_id=None`) |
| **`case_417`** | No Evidence | Soo-jin Kim: zero resources in activity or evidence (only ephemeral debug lookup logs with `resource_id=None`) |

---

## 4. Synthetic Completion-Check Test Results

Implemented in `code/tests/test_completion_pipeline_cases.py` calling real `code.src.completion_validator:validate_case_completion`:

1. **Case (a) — Active flow for cluster resource, unlinked by ID**:
   - Condition: Clean candidate with deleted account; active data flow `data_flow_999` present in `flow_risks`.
   - Result: **PASS** (Demoted to `INCOMPLETE` with reason `ACTIVE_DATA_FLOW`).
2. **Case (b) — Disabled flow for cluster resource**:
   - Condition: Candidate with disabled data flow `data_flow_101` in connector configurations.
   - Result: **PASS** (`COMPLETE` with verification step `VERIFY_DATA_FLOW_DISABLED`).
3. **Case (c) — Active flow for unrelated subject**:
   - Condition: Background activity in system, but flow does not touch this cluster.
   - Result: **PASS** (`COMPLETE`; independent user deletion is not falsely demoted).
4. **Case (d) — COMPLETE with all verification steps and no flows**:
   - Condition: Clean candidate with verified absent/retained records.
   - Result: **PASS** (`COMPLETE` with valid evidence-backed verification steps).

**Overall Synthetic Test Status**: **4 / 4 PASSED** (164/164 test suite passing).

---

## 5. COMPLETE Check on All Remaining 162 Rows

All 162 `COMPLETE` cases in `build/nulltrace_step_z2.csv` were audited:
- **Demotion Count**: **0**
- **Demoted Cases**: None (`[]`)
- **Active or Unverified Flows Touching Cluster Resources**: **0**
- **Findings**: Every candidate resource has verified absent or compliant state in direct snapshot evidence. All subject-linked data flows are confirmed `FlowStatus.DISABLED` with participant evidence (`evidence_07`, `evidence_49`, `evidence_65`, `evidence_91`, `evidence_93`). Active flows in `system_activity.csv` belong solely to unrelated subjects and do not touch any cluster resource.

---

## 6. Step Counts Programmatic Reconciliation

Direct script count on `build/nulltrace_step_z2.csv`:

| Phase | Step Z2 Count | Baseline (`output.csv`) | Step Y Candidate | Net Delta vs Baseline |
| :--- | :---: | :---: | :---: | :---: |
| `FINDING` | **590** | 586 | 607 | +4 |
| `REMEDIATION` | **590** | 586 | 607 | +4 |
| `VERIFICATION` | **869** | 865 | 886 | +4 |
| **Total Steps** | **2,049** | **2,037** | **2,100** | **+12** |

### Mathematical Reconciliation:
- Baseline `output.csv`: 586 finding + 586 remediation + 865 verification = **2,037 steps**.
- In Step Z2, exactly 4 supported cases (`case_311`, `case_46`, `case_61`, `case_63`) have verified steps.
- Each of the 4 cases contributes 1 finding, 1 remediation, and 1 verification step:
  $$4 \times 3 = 12 \text{ steps}$$
  $$2,037 + 12 = \mathbf{2,049} \text{ steps}$$
- From Step Y (2,100 steps), the 17 unsupported finding rows (51 steps total) were removed:
  $$2,100 - 51 = \mathbf{2,049} \text{ steps}$$
- Reconciliation is 100% exact.

---

## 7. SHA-256 Checksums

| File | SHA-256 Checksum | Note |
| :--- | :--- | :--- |
| `output.csv` | `c2173c42197e503ba349eb2cad214b1f9276c6caa9a9e9308bae836e3c109d24` | Root submission baseline (preserved) |
| `build/nulltrace_step_z2.csv` | `5e8b0175360887114a25381628814136fe0f349e7189aeefc2aaf0f519e72445` | Repaired Step Z2 candidate (518 rows) |
| `build/unresolved_cases.csv` | `fd2c9af983cf54fe6f5236eb155fdc7dc2c4a37171d403b71366247d9ae2157a` | Exactly 22 unresolved cases with reasons |
| `build/nulltrace_step_y.csv` | `a6151d833718e5d1780007dd45f6c2b2d0f7d4ce35299abfdb9f21362240006c` | Step Y audit candidate |
| `build/nulltrace_candidate_step_r.csv` | `c2173c42197e503ba349eb2cad214b1f9276c6caa9a9e9308bae836e3c109d24` | Step R candidate (promoted in Step T) |
| `build/root_output_backup_step_q.csv` | `788302aaea25bf22e1d84ce376b7450700285712dc356fb1b90ee5fc4927a650` | Step Q baseline backup |
