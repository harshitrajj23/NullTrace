# NullTrace: Resource Linkage Diagnostic Report

## 1. System Activity Schema Findings

- **Exact Header**: `activity_id,event_time,event_type,source_system,target_system,resource_id,reported_result,details`
- **Total Data Rows**: 4,011 rows
- **Columns with <= 5 Distinct Values**:
  - `reported_result` (3 distinct values): `SUCCESS`: 2,914 (72.6%), `FAILED`: 721 (18.0%), `PARTIAL`: 376 (9.4%)
- **Column Carrying Resource IDs**: `resource_id` (contains system resource tokens such as `account_*`, `search_*`, `analytics_*`, `backup_*`, `data_flow_*`, `support_*`, `tombstone_*`, `export_*`, `cache_*`, `email_delivery_*`).
- **Columns Linking to Subject Identifiers**:
  - **Dedicated Subject Column**: **None**. There is no `user_id`, `email`, `phone`, or `hash` column in `system_activity.csv`.
  - **Text Linkage in `details`**: Exactly 12 rows (out of 4,011, or 0.3%) mention subject identifiers within the free-text `details` column, all associated with `event_type = LINK_RESOURCE_IDENTITY` (rows 4000 to 4011). The remaining 3,999 rows (99.7%) contain zero subject identifiers and record system-level operations only.

---

## 2. Candidate Link Counts by Reason Code and Strength

### Full Dataset (518 Evaluation Requests)
- **Total Candidate Records Linked**: 14
- **Cases with at least one candidate**: 12 / 518
- **Links by Reason Code**:
  - `SUBJECT_USER_ID_MATCH`: 14
- **Links by Strength (following D3)**:
  - `CONFIRMED`: 14
  - `PROBABLE`: 0
  - `UNRESOLVED`: 0

### Sample Dataset (32 Public Requests)
- **Total Candidate Records Linked**: 2
- **Cases with at least one candidate**: 2 / 32 (`case_07`, `case_17`)
- **Reason Code Breakdown**: `SUBJECT_USER_ID_MATCH`: 2 (both `CONFIRMED`)
  - `case_07`: `object_19` (`activity_4007`, `CONFIRMED`)
  - `case_17`: `tombstone_17` (`activity_4011`, `CONFIRMED`)

---

## 3. Investigation of the 4 Unfound Resource IDs

A full repository and binary sweep was performed for the 4 resource IDs identified as `NOT_FOUND_IN_DATASET` in Step E.1:

| Resource ID | Originating Sample Case | Files Found In Dataset | Line / Context Line | Reason for Absence in Raw Dataset Tables |
| :--- | :--- | :--- | :--- | :--- |
| `account_004` | `case_04` | `dataset/sample_output.csv` | Line 5: `VERIFY_RECORD_ABSENT` | The account was deleted prior to audit; absent by definition from failover replica `evidence_54`. |
| `support_001` | `case_07` | `dataset/sample_output.csv` | Line 8: `REPORT_REMAINING_RECORD` | Originates as a support ticket inside `evidence/documents/delivery_correction_attachment.pdf`. |
| `audit_record_5569` | `case_20` | `dataset/sample_output.csv` | Line 21: `VERIFY_RECORD_PRESENT` | Future verification step (`evidence_id: ""`) confirming retained audit record; not logged in activity. |
| `audit_record_6645` | `case_18` | `dataset/sample_output.csv` | Line 19: `VERIFY_RECORD_PRESENT` | Future verification step (`evidence_id: ""`) confirming retained audit record; not logged in activity. |

---

## 4. Sample Cross-Check Totals and Miss List

### Summary Metrics
- **Expected Resources (case-resource pairs)**: 111
- **Candidate Resources from Activity Linker**: 2
- **Matched Resources**: 0
- **Missed Resources**: 111
- **Extra Candidates**: 2

### Full Miss List (111 Unmatched Expected Resources)

| Case ID | Missed Expected Resource ID |
| :--- | :--- |
| `case_01` | `account_001` |
| `case_02` | `account_002` |
| `case_03` | `account_7566` |
| `case_03` | `analytics_9406` |
| `case_03` | `audit_record_2016` |
| `case_04` | `account_004` |
| `case_04` | `analytics_901` |
| `case_05` | `account_005` |
| `case_06` | `account_006` |
| `case_06` | `search_001` |
| `case_07` | `account_007` |
| `case_07` | `support_001` |
| `case_08` | `account_008` |
| `case_08` | `export_001` |
| `case_09` | `account_3960` |
| `case_09` | `audit_record_4902` |
| `case_09` | `backup_4978` |
| `case_10` | `account_010` |
| `case_10` | `support_002` |
| `case_11` | `account_4248` |
| `case_11` | `analytics_2034` |
| `case_11` | `audit_record_9394` |
| `case_11` | `data_flow_9522` |
| `case_11` | `search_052` |
| `case_11` | `support_864` |
| `case_12` | `account_9797` |
| `case_12` | `analytics_9914` |
| `case_12` | `audit_record_2945` |
| `case_13` | `account_9335` |
| `case_13` | `audit_record_4816` |
| `case_13` | `search_1308` |
| `case_13` | `support_4218` |
| `case_14` | `account_3677` |
| `case_14` | `audit_record_987` |
| `case_14` | `backup_3870` |
| `case_15` | `account_4745` |
| `case_15` | `audit_record_1596` |
| `case_15` | `data_flow_9846` |
| `case_16` | `account_994` |
| `case_16` | `audit_record_9528` |
| `case_16` | `search_1007` |
| `case_17` | `account_4092` |
| `case_17` | `audit_record_1797` |
| `case_17` | `backup_3245` |
| `case_18` | `account_5521` |
| `case_18` | `analytics_037` |
| `case_18` | `audit_record_6645` |
| `case_18` | `data_flow_4890` |
| `case_18` | `search_4013` |
| `case_18` | `support_5569` |
| `case_19` | `account_9102` |
| `case_19` | `audit_record_6793` |
| `case_19` | `search_6083` |
| `case_19` | `support_9553` |
| `case_20` | `account_5037` |
| `case_20` | `audit_record_5569` |
| `case_20` | `data_flow_1770` |
| `case_20` | `search_4262` |
| `case_21` | `account_6440` |
| `case_21` | `analytics_5335` |
| `case_21` | `audit_record_3737` |
| `case_22` | `account_4990` |
| `case_22` | `analytics_4440` |
| `case_22` | `audit_record_3482` |
| `case_22` | `search_8911` |
| `case_23` | `account_410` |
| `case_23` | `audit_record_4128` |
| `case_23` | `export_7364` |
| `case_23` | `search_898` |
| `case_24` | `account_5334` |
| `case_24` | `audit_record_7095` |
| `case_24` | `search_5577` |
| `case_25` | `account_3136` |
| `case_25` | `analytics_1895` |
| `case_25` | `audit_record_451` |
| `case_26` | `account_5684` |
| `case_26` | `analytics_4566` |
| `case_26` | `audit_record_5416` |
| `case_26` | `backup_3120` |
| `case_26` | `data_flow_6244` |
| `case_26` | `support_4715` |
| `case_27` | `account_3866` |
| `case_27` | `analytics_4574` |
| `case_27` | `audit_record_3830` |
| `case_27` | `backup_5970` |
| `case_27` | `data_flow_2295` |
| `case_27` | `support_4707` |
| `case_28` | `account_5482` |
| `case_28` | `analytics_6077` |
| `case_28` | `audit_record_9265` |
| `case_28` | `backup_838` |
| `case_28` | `data_flow_2337` |
| `case_28` | `support_2351` |
| `case_29` | `account_7012` |
| `case_29` | `analytics_5208` |
| `case_29` | `audit_record_3954` |
| `case_29` | `data_flow_3827` |
| `case_29` | `search_1993` |
| `case_29` | `support_5281` |
| `case_30` | `account_4163` |
| `case_30` | `analytics_3697` |
| `case_30` | `audit_record_1707` |
| `case_30` | `data_flow_8524` |
| `case_30` | `search_9359` |
| `case_30` | `support_6477` |
| `case_31` | `account_4857` |
| `case_31` | `audit_record_6909` |
| `case_31` | `tombstone_440` |
| `case_32` | `account_8858` |
| `case_32` | `audit_record_7068` |
| `case_32` | `tombstone_9178` |

### Extra Candidates (2 Resources)
| Case ID | Extra Resource ID | Activity ID | Reason Code |
| :--- | :--- | :--- | :--- |
| `case_07` | `object_19` | `activity_4007` | `SUBJECT_USER_ID_MATCH` |
| `case_17` | `tombstone_17` | `activity_4011` | `SUBJECT_USER_ID_MATCH` |

---

## 5. What the Activity Linker Cannot See Yet

The activity linker operates exclusively on `system_activity.csv`. Because 99.7% of activity rows (3,999/4,011) describe system operations without subject identifiers, the linker can only observe resources explicitly cataloged in the 12 `LINK_RESOURCE_IDENTITY` rows. Consequently, it cannot discover: (1) security service audit records (`audit_record_*`) which reside solely in evidence content (SQL replicas, structured log files, and text handover registers); (2) account, search index, or analytics entries whose association with a user exists only inside evidence files (e.g. database foreign keys or customer snapshot bundles); and (3) historical or downstream sync replicas. Bridging these missing resources requires the subsequent evidence parsing and multi-source state reconstruction stage.
