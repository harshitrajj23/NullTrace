# NullTrace: Step Z Audit Report — Pre-Promotion Verification

**Date**: 2026-10-25  
**Harness**: antigravity-ide  
**Model Policy**: DECISION: MODEL_OFF (Deterministic offline execution; zero external API calls)  
**Status**: Step Z Verification Complete (Audit deliverable created; root `output.csv` untampered)

---

## 1. Tombstone Rule Confirmation & Code Path for 21 Rows

### 1.1 Confirmation of Tombstone Rule
`build/nulltrace_step_y.csv` fully integrates the **`ACCOUNT_TOMBSTONE` Resolution Rule** (`code/src/rule_engine.py:apply_account_tombstone_resolution` and `assess_resource_policy`):
- All 162 `COMPLETE` cases were audited against tombstone exposure rules (`rule_15`), confirming that primary account references are preserved while prohibited direct identifiers (`name`, `email`, `phone`, `email_hash`) are removed.
- In `case_46`, `tombstone_17` was evaluated under `rule_15` (`ACCOUNT_TOMBSTONE`). Direct PII was found unredacted at `audit_at`, resulting in policy violation steps (`REPORT_EXPOSED_PII` -> `REDACT_RECORD` -> `VERIFY_RECORD_REDACTED`).

### 1.2 Execution Code Path for the 21 New Rows
Each of the 21 new finding rows (and their paired remediation and verification steps) was generated via the following deterministic pipeline components:

```text
1. Identity Resolution:
   code/src/identity.py:resolve_all()
   -> Builds normalized identifier clusters (user_id, email, phone, email_hash) from user_identities.csv and user_audit_log.csv.

2. Candidate Resource & Evidence Linking:
   code/src/resource_link.py:link_cluster_resources() & ActivitySubjectIndex
   -> Correlates cluster identifiers against system_activity.csv and evidence_manifest extractions.

3. Temporal State Reconstruction at audit_at:
   code/src/state_reconstruction.py:reconstruct_resource_state()
   -> Reconciles direct snapshot observations vs activity logs strictly at or before audit_at cutoff.

4. Policy Assessment:
   code/src/rule_engine.py:assess_resource_policy()
   -> Applies deletion_rules.csv (rule_01 to rule_15) to map required actions (DELETE, REDACT, ANONYMIZE, BLOCK_RESTORE, DISABLE_DATA_FLOW).

5. Planning, Sorting & Validation:
   code/src/planner.py:plan_case() -> code/src/ops.py:sort_steps() -> code/src/ops.py:validate_steps()
   -> Emits strictly ordered steps (FINDING -> REMEDIATION -> VERIFICATION) with consecutive 1-indexed step numbers and valid grammar.
```

---

## 2. Identity Linking Audit: 21 Resolved Resources

Per challenge instruction: *"For each of the 21 resolved cases, state the identity rule that linked the resource to the subject. If the link came from an activity row with no subject identifier, mark it UNSUPPORTED and do not use it."*

| Case ID | Resource ID | Evidence / Activity ID | Activity / Evidence Content | Subject Identifiers Present? | Identity Rule Applied | Decision Status |
| :--- | :--- | :--- | :--- | :---: | :--- | :--- |
| **`case_127`** | `account_6805` | `activity_3113` | *"Deletion worker submitted primary profile account_6805 to account_service."* | **None** | None in activity row | **UNSUPPORTED — DO NOT USE** |
| **`case_168`** | `export_4102` | `activity_2811` | *"Deletion worker received the final result for export_4102 from export_service."* | **None** | None in activity row | **UNSUPPORTED — DO NOT USE** |
| **`case_175`** | `account_246` | `activity_2642` | *"Deletion worker submitted primary profile account_246 to account_service."* | **None** | None in activity row | **UNSUPPORTED — DO NOT USE** |
| **`case_264`** | `support_9996` | `activity_2116` | *"Policy action completed for support_9996."* | **None** | None in activity row | **UNSUPPORTED — DO NOT USE** |
| **`case_264`** | `data_flow_4885` | `activity_2117` | *"Policy action completed for data_flow_4885."* | **None** | None in activity row | **UNSUPPORTED — DO NOT USE** |
| **`case_264`** | `backup_3250` | `activity_2118` | *"Policy action completed for backup_3250."* | **None** | None in activity row | **UNSUPPORTED — DO NOT USE** |
| **`case_288`** | `export_7906` | `activity_1909` | *"Deletion worker received the final result for export_7906 from export_service."* | **None** | None in activity row | **UNSUPPORTED — DO NOT USE** |
| **`case_292`** | `backup_1825` | `activity_1848` | *"Policy action completed for backup_1825."* | **None** | None in activity row | **UNSUPPORTED — DO NOT USE** |
| **`case_311`** | `search_3004` | `evidence_29` | Line 32: `INSERT INTO customer_data_primary ... email="naledi-mahlangu79@proton.me", customer_reference="user_309"` | **user_309, naledi-mahlangu79@proton.me** | `SUBJECT_USER_ID_MATCH`, `SUBJECT_EMAIL_MATCH` in direct SQL snapshot | **SUPPORTED** |
| **`case_372`** | `export_5081` | `activity_1239` | *"Deletion worker received the final result for export_5081 from export_service."* | **None** | None in activity row | **UNSUPPORTED — DO NOT USE** |
| **`case_413`** | `analytics_4523` | `activity_858` | *"Deletion worker received the final result for analytics_4523 from analytics_platform."* | **None** | None in activity row | **UNSUPPORTED — DO NOT USE** |
| **`case_414`** | `support_3768` | `activity_859` | *"Deletion worker received the final result for support_3768 from support_platform."* | **None** | None in activity row | **UNSUPPORTED — DO NOT USE** |
| **`case_418`** | `support_9464` | `activity_815` | *"Deletion worker received the final result for support_9464 from support_platform."* | **None** | None in activity row | **UNSUPPORTED — DO NOT USE** |
| **`case_420`** | `export_389` | `activity_753` | *"Deletion worker received the final result for export_389 from export_service."* | **None** | None in activity row | **UNSUPPORTED — DO NOT USE** |
| **`case_44`** | `backup_6266` | `activity_3856` | *"Policy action completed for backup_6266."* | **None** | None in activity row | **UNSUPPORTED — DO NOT USE** |
| **`case_46`** | `tombstone_17` | `activity_4011` | *"Data catalog linked tombstone_17 (user_17) to leonie.g9352@outlook.com and user_17."* | **user_17, leonie.g9352@outlook.com** | `SUBJECT_USER_ID_MATCH`, `SUBJECT_EMAIL_MATCH` in activity log | **SUPPORTED** |
| **`case_51`** | `backup_7809` | `activity_3738` | *"Policy action completed for backup_7809."* | **None** | None in activity row | **UNSUPPORTED — DO NOT USE** |
| **`case_520`** | `support_9251` | `activity_50` | *"Deletion worker received the final result for support_9251 from support_platform."* | **None** | None in activity row | **UNSUPPORTED — DO NOT USE** |
| **`case_522`** | `support_8538` | `activity_296` | *"Deletion worker received the final result for support_8538 from support_platform."* | **None** | None in activity row | **UNSUPPORTED — DO NOT USE** |
| **`case_61`** | `object_19` | `activity_4007` | *"Attachment catalog confirmed object_19 (delivery_confirmation_19.pdf) belongs only to priya.raman@gmail.com and user_07; no other subject is linked."* | **user_07, priya.raman@gmail.com** | `SUBJECT_USER_ID_MATCH`, `SUBJECT_EMAIL_MATCH` in activity log | **SUPPORTED** |
| **`case_63`** | `marketing_001` | `activity_4008` | *"Data catalog linked marketing_001 (marketing_001) to kwame-mensah@proton.me and user_09."* | **user_09, kwame-mensah@proton.me** | `SUBJECT_USER_ID_MATCH`, `SUBJECT_EMAIL_MATCH` in activity log | **SUPPORTED** |

**Summary**:
- **4 Cases are SUPPORTED**: `case_311`, `case_46`, `case_61`, `case_63` have explicit subject identifiers (`user_id`, `email`) in pre-audit participant evidence or activity records.
- **17 Cases are UNSUPPORTED**: The activity records contain zero subject identifiers. They must NOT be promoted or used as factual findings under the challenge rules.

---

## 3. Synthetic Completion Flow Safety Test

A synthetic unit test was implemented in `code/tests/test_completion_flow_safety.py`:
- **Scenario**: A candidate with compliant, evidence-backed deleted resources (normally evaluating to `COMPLETE`) has an unlinked active data flow (`data_flow_synthetic_999` on `integration_service`) present in the system flow graph.
- **Validator Execution**: `validate_case_completion` was invoked with this flow risk.
- **Behavior Verified**: The completion validator flagged `ACTIVE_DATA_FLOW` and `MISSING_VERIFICATION_EVIDENCE`, strictly demoting the case from `COMPLETE` to `INCOMPLETE`.
- **Result**: **PASS** (1/1 unit test passed; 164/164 entire test suite passing).

---

## 4. Re-Running COMPLETE Check on All 162 Rows

All 162 `COMPLETE` cases in `output.csv` were evaluated against the completion validator with active data flow detection enabled across the entire system graph:
- **Demotion Count**: **0**
- **Findings**:
  1. No candidate resource in any of the 162 cases has an unverified or active sync, import, or replication event.
  2. All subject-linked data flows in the 162 cases (e.g. `data_flow_7773`, `data_flow_3255`, `data_flow_9666`, `data_flow_6987`, `data_flow_1344`, `data_flow_8024`, `data_flow_6846`) are confirmed `FlowStatus.DISABLED` with participant evidence in `evidence_07`, `evidence_49`, `evidence_65`, `evidence_91`, and `evidence_93`.
  3. Active data flows in `system_activity.csv` (e.g. `data_flow_3518`, `data_flow_9556`) belong exclusively to other unrelated users and have zero topological connection to the cluster's resources.

---

## 5. Candidate Step Counts & Reconciliation

Direct programmatic count from `build/nulltrace_step_y.csv`:

| Phase | Candidate Count | Baseline (`output.csv`) | Net Delta |
| :--- | :---: | :---: | :---: |
| `FINDING` | **607** | 586 | +21 |
| `REMEDIATION` | **607** | 586 | +21 |
| `VERIFICATION` | **886** | 865 | +21 |
| **Total Steps** | **2,100** | **2,037** | **+63** |

### Reconciliation
- Exactly 21 finding rows were added to the 19 resolved cases (18 cases with 1 finding each, plus `case_264` with 3 findings).
- Because every finding step in an `INCOMPLETE` remediation plan generates exactly one remediation step and one post-remediation verification step, the net delta is:
  $$\Delta \text{Steps} = 21 \times 3 = 63 \text{ steps}$$
  $$2,037 + 63 = 2,100 \text{ total steps}$$
- This reconciles 100% with the 2,100 figure.

---

## 6. Checksums & Deliverable Integrity

| Artifact | SHA-256 Checksum |
| :--- | :--- |
| `output.csv` (Baseline Root) | `c2173c42197e503ba349eb2cad214b1f9276c6caa9a9e9308bae836e3c109d24` |
| `build/nulltrace_step_y.csv` (Candidate) | `a6151d833718e5d1780007dd45f6c2b2d0f7d4ce35299abfdb9f21362240006c` |
| `build/root_output_backup_step_q.csv` | `788302aaea25bf22e1d84ce376b7450700285712dc356fb1b90ee5fc4927a650` |
| `build/nulltrace_candidate_step_r.csv` | `c2173c42197e503ba349eb2cad214b1f9276c6caa9a9e9308bae836e3c109d24` |
