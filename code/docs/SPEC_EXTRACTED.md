# NullTrace: Specification & Dataset Extraction Report

## 1. Governing Files Review
The governing files were read in full, in the specified order:
1. **`AGENTS.md`**: Complete repository rules, session lifecycle, transcript logging format (§5), and challenge contract (§6).
2. **`CLAUDE.md`**: Directs all AI agents to `@AGENTS.md`.
3. **`agent_trace_instructions.md`**: Instructions for preserving structured traces (`agent-trace.zip`) across harnesses including Antigravity, Claude Code, and Codex.
4. **`README.md`**: Project overview, execution entry point (`code/main.py`), packaging rules (`code.zip`), evaluation reporting guidelines, and submission links.
5. **`problem_statement.md`**: Full participant-facing specification detailing the deletion audit contract, allowed operations, phases, and evaluation criteria.

### Problem Statement File Comparison
- **Repository Root**: `problem_statement.md` exists and contains 163 lines defining the challenge contract.
- **`dataset/problem_statement.md`**: **Does not exist** on disk.
- **Conclusion**: There is only one copy of `problem_statement.md` in the checkout (at the repository root).

---

## 2. Dataset Inventory (Read-Only Audit)

### 2.1 Tabular Datasets (`dataset/*.csv`)

| File Name | Exact Header Line | Data Row Count | Columns with $\le 5$ Distinct Values & Counts | Empty, Malformed, or Duplicate Lines |
| :--- | :--- | :---: | :--- | :--- |
| **`deletion_requests.csv`** | `case_id,email,requested_at,reported_status,reported_at,audit_at,request_text` | 518 | `reported_status`: `{'COMPLETE': 254, 'PARTIALLY_COMPLETE': 152, 'NOT_STARTED': 112}` | None (0 empty, 0 malformed, 0 duplicates) |
| **`sample_deletion_requests.csv`** | `case_id,email,requested_at,reported_status,reported_at,audit_at,request_text` | 32 | `reported_status`: `{'COMPLETE': 17, 'NOT_STARTED': 10, 'PARTIALLY_COMPLETE': 5}` | None (0 empty, 0 malformed, 0 duplicates) |
| **`sample_output.csv`** | `case_id,deletion_status,steps_json` | 32 | `deletion_status`: `{'INCOMPLETE': 22, 'COMPLETE': 10}` | None (0 empty, 0 malformed, 0 duplicates) |
| **`user_identities.csv`** | `user_id,name,email,phone,email_hash,updated_at` | 850 | None (all columns have $>5$ distinct values) | None (0 empty, 0 malformed, 0 duplicates) |
| **`user_audit_log.csv`** | `audit_id,user_id,event_time,field_name,old_value,new_value` | 306 | `field_name`: `{'email': 107, 'email_hash': 107, 'phone': 92}` | None (0 empty, 0 malformed, 0 duplicates) |
| **`system_activity.csv`** | `activity_id,event_time,event_type,source_system,target_system,resource_id,reported_result,details` | 4011 | `reported_result`: `{'SUCCESS': 2914, 'FAILED': 721, 'PARTIAL': 376}` | None (0 empty, 0 malformed, 0 duplicates) |
| **`deletion_rules.csv`** | `rule_id,data_category,condition,required_action` | 15 | `required_action`: `{'DELETE': 7, 'REDACT': 3, 'RETAIN': 3, 'ANONYMIZE': 2}` | None (0 empty, 0 malformed, 0 duplicates) |
| **`evidence_files.csv`** | `file_id,file_path,origin,captured_at` | 94 | None (all columns have $>5$ distinct values) | None (0 empty, 0 malformed, 0 duplicates) |
| **`output.csv`** | `case_id,deletion_status,steps_json` | 0 | Empty template (header only) | Header only; 0 data rows |

### 2.2 Representative Rows (3 Samples Copied Verbatim)

#### `deletion_requests.csv`
```csv
case_33,ingrid.dahl@outlook.com,2026-07-16T08:00:00Z,COMPLETE,2026-07-18T02:00:00Z,2026-07-19T13:00:00Z,Please close my account and process the associated personal-data deletion. Please handle any copies that fall within the scope of the deletion request. Please confirm when the review is complete.
case_34,haruka.s1838@zoho.com,2026-09-24T08:00:00Z,COMPLETE,2026-09-26T02:00:00Z,2026-09-27T13:00:00Z,I would like the account associated with this address to be erased. Please handle any copies that fall within the scope of the deletion request. Please contact me if you need information to verify the request.
case_35,g.silva76@gmail.com,2026-08-30T03:00:00Z,NOT_STARTED,2026-08-31T21:00:00Z,2026-09-02T08:00:00Z,Please close my account and process the associated personal-data deletion. Please check the records connected to the account before confirming completion. Please contact me if you need information to verify the request.
```

#### `sample_deletion_requests.csv`
```csv
case_01,amina.elmasri@gmail.com,2026-08-18T09:14:00Z,COMPLETE,2026-08-20T16:42:00Z,2026-09-03T11:30:00Z,"Hi, I haven’t used this account in years and would like it closed. Please remove the profile and the personal details attached to it."
case_02,mateo.rios@outlook.com,2026-08-21T18:06:00Z,PARTIALLY_COMPLETE,2026-08-22T07:25:00Z,2026-09-04T15:00:00Z,"Intenté eliminar mi cuenta ayer, pero la página terminó mostrando un error. ¿Pueden comprobar si todavía queda algún dato y completar la eliminación si hace falta?"
case_03,l.fontaine46@yahoo.com,2026-09-13T11:00:00Z,COMPLETE,2026-09-15T11:00:00Z,2026-09-26T11:00:00Z,Je demande la suppression définitive du compte associé à cette adresse e-mail. Veuillez examiner les identifiants actuels et antérieurs conformément à votre procédure de confidentialité. Merci de confirmer le résultat une fois la vérification terminée.
```

#### `sample_output.csv`
```csv
case_01,COMPLETE,"[{""evidence_id"":""evidence_54"",""operation"":""VERIFY_RECORD_ABSENT"",""phase"":""VERIFICATION"",""resource_id"":""account_001"",""state"":""ABSENT"",""step_no"":1,""system_id"":""account_service""}]"
case_02,COMPLETE,"[{""evidence_id"":""evidence_54"",""operation"":""VERIFY_RECORD_ABSENT"",""phase"":""VERIFICATION"",""resource_id"":""account_002"",""state"":""ABSENT"",""step_no"":1,""system_id"":""account_service""}]"
case_03,COMPLETE,"[{""step_no"":1,""phase"":""VERIFICATION"",""system_id"":""account_service"",""resource_id"":""account_7566"",""operation"":""VERIFY_RECORD_ABSENT"",""state"":""ABSENT"",""evidence_id"":""evidence_94""},{""step_no"":2,""phase"":""VERIFICATION"",""system_id"":""security_service"",""resource_id"":""audit_record_2016"",""operation"":""VERIFY_RECORD_PRESENT"",""state"":""PRESENT"",""evidence_id"":""evidence_94""},{""step_no"":3,""phase"":""VERIFICATION"",""system_id"":""analytics_platform"",""resource_id"":""analytics_9406"",""operation"":""VERIFY_RECORD_ANONYMIZED"",""state"":""ANONYMIZED"",""evidence_id"":""evidence_94""}]"
```

#### `user_identities.csv`
```csv
user_01,Amina El-Masri,amina.elmasri@gmail.com,+971 50 482 7316,d4e1f59abcf9a1e0cfdc7c27ad6c07ed4ff88b326a16ed5eed5ec6bc31618c93,2026-05-28T04:03:00Z
user_02,Mateo Ríos,mateo.rios@outlook.com,+34 612 847 593,fad1c282b6b8ff346ee92e617331f69c2b6bb345af954eeb44581c57529eab9d,2026-04-24T07:44:00Z
user_03,Oliver Bennett,oliver-bennett@gmail.com,+1 (202) 555-0103,1fa7764c96e40e8570cbb7569f707f6d84c593cecbe5c1ed2b0a07a624dba039,2026-03-14T14:21:00Z
```

#### `user_audit_log.csv`
```csv
audit_01,user_485,2024-12-14T16:31:44Z,phone,+33 6 24 34 80 16,+33 6 63 29 68 28
audit_02,user_505,2024-12-25T00:51:04Z,phone,+81 90 6278 6936,+81 90 7870 0272
audit_03,user_525,2025-01-04T00:11:24Z,phone,+46 70 144 08 06,+46 70 808 74 05
```

#### `system_activity.csv`
```csv
activity_01,2026-01-04T14:56:29Z,INDEX_RECORD,account_service,search_service,search_9729,SUCCESS,Customer search-index refresh processed search_9729.
activity_02,2026-01-04T16:08:26Z,INDEX_RECORD,account_service,search_service,search_6919,SUCCESS,Customer search-index refresh processed search_6919.
activity_03,2026-01-04T17:14:03Z,INDEX_RECORD,account_service,search_service,search_4613,SUCCESS,Customer search-index refresh processed search_4613.
```

#### `deletion_rules.csv`
```csv
rule_01,USER_PROFILE,Always,DELETE
rule_02,SECONDARY_IDENTIFIER,Always,DELETE
rule_03,SEARCH_INDEX_ENTRY,Always,DELETE
```

#### `evidence_files.csv`
```csv
evidence_01,evidence/logs/service_events_ap_south_20260915.log,central_observability_export,2026-09-15T11:59:39Z
evidence_02,evidence/records/customer_data_snapshot_bundle_20260917.json,records_assurance_snapshot_bundle,2026-09-17T12:00:00Z
evidence_03,evidence/records/customer_account_handover_20261001.txt,customer_account_service,2026-10-01T12:00:00Z
```

#### `output.csv` (Template)
```csv
case_id,deletion_status,steps_json
```

---

### 2.3 Evidence Files Inventory (`dataset/evidence/`)

- **Total Files on Disk**: 94
- **Total Files in Manifest (`evidence_files.csv`)**: 94
- **Manifest vs. Disk Discrepancies**:
  - Files in manifest but missing on disk: **0** (`set()`)
  - Files on disk not listed in manifest: **0** (`set()`)

#### File Count & Characteristics by Extension

| Extension | Count | Sample File Path | Content Characteristics |
| :---: | :---: | :--- | :--- |
| **`.json`** | 28 | `evidence/records/customer_data_snapshot_bundle_20260913.json` | Text-extractable structured JSON data containing account snapshots, customer exports, and service configurations. |
| **`.log`** | 26 | `evidence/logs/application_trace_ap_northeast_20260730.log` | Text-extractable UTF-8 plain text logs containing timestamped traces, resource lookups, service events, and syslog entries. |
| **`.sql`** | 24 | `evidence/databases/customer_data_inventory_20260916.sql` | Text-extractable plain text SQL schema and DML dump files; directly executable in SQLite. Models primary, read, regional, reporting, and failover replicas. |
| **`.png`** | 11 | `evidence/images/backup_restore_console_20260429.png` | Raster image screenshots (1800x1200, 1800x1150, 1800x1100, 1500x920) of administrative consoles, ticket views, object storage, and search index inspectors. Text requires OCR / multimodal model inspection. |
| **`.pdf`** | 4 | `evidence/documents/legal_retention_register_20260529.pdf` | Formatted binary PDF documents (v1.4, generated via ReportLab with Flate-compressed streams and embedded subset Arial fonts). Contains formal retention registers, security extracts, and delivery reports. |
| **`.txt`** | 1 | `evidence/records/customer_account_handover_20261001.txt` | Text-extractable UTF-8 plain text record containing human handover notes and account audit records. |

---

## 3. Specification Extraction (from `problem_statement.md`)

### 3.1 Required Output Schema & Sort Rules (Section: "Required Output")
- **Columns and Order**:
  ```text
  case_id,deletion_status,steps_json
  ```
- **Row Count**: Exactly **518** data rows (plus header), exactly matching the 518 cases in `dataset/deletion_requests.csv`.
- **Sort Rule**: Sorted by `case_id` in ascending order.
- **`deletion_status` Values**: `COMPLETE`, `INCOMPLETE`, or `NOT_APPLICABLE`.
- **`steps_json` Specification**:
  - Valid JSON array containing step objects.
  - Numbered consecutively starting from `1` (`step_no`).
  - For `NOT_APPLICABLE`: Must be an empty JSON array: `[]`.
  - Step Schema:
    ```json
    {
      "step_no": 1,
      "phase": "FINDING",
      "system_id": "account_service",
      "resource_id": "account_005",
      "operation": "REPORT_REMAINING_RECORD",
      "state": "PRESENT",
      "evidence_id": "evidence_01"
    }
    ```

### 3.2 The 15 Allowed Operations (Section: "Allowed Operations")

| Phase | Operation | State | Meaning |
| :--- | :--- | :--- | :--- |
| **`FINDING`** | `REPORT_REMAINING_RECORD` | `PRESENT` | A record that should have been deleted still exists. |
| **`FINDING`** | `REPORT_EXPOSED_PII` | `PRESENT` | A record may remain, but it still contains identifiers that should have been redacted or anonymized. |
| **`FINDING`** | `REPORT_ACTIVE_DATA_FLOW` | `ACTIVE` | An active process can copy or recreate the user's data. |
| **`FINDING`** | `REPORT_RESTORE_RISK` | `ACTIVE` | A backup or restore path can bring deleted data back. |
| **`REMEDIATION`** | `DISABLE_DATA_FLOW` | `DISABLED` | Stop the process that can copy or recreate the data. |
| **`REMEDIATION`** | `BLOCK_RESTORE` | `BLOCKED` | Prevent the affected backup from restoring the user's data. |
| **`REMEDIATION`** | `DELETE_RECORD` | `ABSENT` | Remove the entire record. |
| **`REMEDIATION`** | `REDACT_RECORD` | `REDACTED` | Keep the record but remove the identifying fields required by policy. |
| **`REMEDIATION`** | `ANONYMIZE_RECORD` | `ANONYMIZED` | Keep the record after irreversibly unlinking it from the user. |
| **`VERIFICATION`** | `VERIFY_RECORD_ABSENT` | `ABSENT` | Confirm that a record no longer exists. |
| **`VERIFICATION`** | `VERIFY_RECORD_PRESENT` | `PRESENT` | Confirm that a policy-required retained record still exists. |
| **`VERIFICATION`** | `VERIFY_RECORD_REDACTED` | `REDACTED` | Confirm that required identifying fields have been removed. |
| **`VERIFICATION`** | `VERIFY_RECORD_ANONYMIZED` | `ANONYMIZED` | Confirm that the record can no longer be linked to the user. |
| **`VERIFICATION`** | `VERIFY_DATA_FLOW_DISABLED` | `DISABLED` | Confirm that the relevant data flow is inactive. |
| **`VERIFICATION`** | `VERIFY_RESTORE_BLOCKED` | `BLOCKED` | Confirm that the affected data cannot be restored. |

### 3.3 Phase Order and Step Ordering Rules (Section: "Rules")
1. **Phase Order**:
   - `FINDING` $\rightarrow$ `REMEDIATION` $\rightarrow$ `VERIFICATION`
2. **Within-Phase Operation Order**:
   - Matches the exact sequence defined in the problem statement table above:
     - Findings: `REPORT_REMAINING_RECORD` (1) $\rightarrow$ `REPORT_EXPOSED_PII` (2) $\rightarrow$ `REPORT_ACTIVE_DATA_FLOW` (3) $\rightarrow$ `REPORT_RESTORE_RISK` (4).
     - Remediation: `DISABLE_DATA_FLOW` (1) $\rightarrow$ `BLOCK_RESTORE` (2) $\rightarrow$ `DELETE_RECORD` (3) $\rightarrow$ `REDACT_RECORD` (4) $\rightarrow$ `ANONYMIZE_RECORD` (5).
     - Verification: `VERIFY_RECORD_ABSENT` (1) $\rightarrow$ `VERIFY_RECORD_PRESENT` (2) $\rightarrow$ `VERIFY_RECORD_REDACTED` (3) $\rightarrow$ `VERIFY_RECORD_ANONYMIZED` (4) $\rightarrow$ `VERIFY_DATA_FLOW_DISABLED` (5) $\rightarrow$ `VERIFY_RESTORE_BLOCKED` (6).
3. **Tie-Breaking Rule**:
   - When phase and operation are identical, sort by `system_id` ascending, then `resource_id` ascending.
4. **Evidence Citation Rules**:
   - Findings must cite a valid participant-visible `evidence_id` (`file_id`, `activity_id`, or `audit_id`).
   - For `COMPLETE` cases: Every verification step must cite the `evidence_id` proving compliant state at `audit_at`.
   - For `INCOMPLETE` cases: Proposed remediation steps and post-remediation verification steps represent future actions and must use `evidence_id: ""`.

### 3.4 Definitions of Deletion Statuses (Sections: "What You Need to Build" & "Rules")
- **`COMPLETE`**:
  - The request authorizes deletion, and at `audit_at`, every relevant copy has received the treatment required by `deletion_rules.csv`, no active sync, import, or restore path can recreate the data, retained records contain only permitted identifiers, and records that must be retained remain available.
  - Step array consists **only of `VERIFICATION` steps**, each citing proof evidence.
- **`INCOMPLETE`**:
  - The request authorizes deletion, but at `audit_at`, personal data remains without required treatment, prohibited PII is exposed, active synchronization flows persist, or unblocked restore risks exist.
  - Step array contains `FINDING` steps (with evidence citations), followed by `REMEDIATION` steps (with `""` evidence), followed by `VERIFICATION` steps (with `""` evidence).
- **`NOT_APPLICABLE`**:
  - The person did not authorize deletion (e.g., subject made an access request, data export request, correction/rectification inquiry, or marketing opt-out, explicitly stating not to delete the account).
  - Step array must be empty (`steps_json: []`).

### 3.5 Grader's Scoring Criteria (Section: "Evaluation")
The grader parses `steps_json` as JSON (ignoring key order and formatting whitespace, but enforcing array sequence). Scoring evaluates:
- Case-level deletion status accuracy (`COMPLETE`, `INCOMPLETE`, `NOT_APPLICABLE`).
- Current and historical identity resolution (tracking updates across `user_identities.csv` and `user_audit_log.csv`).
- Discovery of remaining data copies, exposed PII, active sync flows, and restore risks.
- Correct policy application per `deletion_rules.csv`.
- Valid evidence citation (`file_id`, `activity_id`, or `audit_id`).
- Completeness and strict ordering of remediation and verification steps.

### 3.6 Deliverables and Packaging (Sections: "Evaluation", "Submission", README & AGENTS.md)

| Item | Location / Format | Details |
| :--- | :--- | :--- |
| **`output.csv`** | Root: `./output.csv` | Exactly 518 data rows sorted by `case_id`. Header: `case_id,deletion_status,steps_json`. |
| **`code.zip`** | Archive at repo root | Clean zip containing runnable solution, prompts, configs, `README.md`, and evaluation reports. Excludes `dataset/`, virtual envs, build caches, and nested archives. |
| **`evaluation_report.md`** | `code/evaluation/evaluation_report.md` (or `evaluation/evaluation_report.md`) | Case, step, field, and sequence accuracy; 3 participant-created evaluation test cases; failures found and improvements made. |
| **`usage_report.md`** | `code/evaluation/usage_report.md` (or `evaluation/usage_report.md`) | Model names, provider, call counts, prompt/completion tokens, total/avg tokens per request, and total estimated cost. |
| **`chat_transcript`** | `./log.txt` at root | The complete conversation log following AGENTS.md §5 format uploaded to the HackerRank submission portal. |

---

## 4. Deletion Rules Mapping (`deletion_rules.csv`)

| Rule ID | Data Category | Condition | Required Action | Mapped Operation(s) (15-Operation Grammar) | Clarity & Ambiguity Notes |
| :---: | :--- | :--- | :---: | :--- | :--- |
| **`rule_01`** | `USER_PROFILE` | Always | `DELETE` | Finding: `REPORT_REMAINING_RECORD` (`PRESENT`)<br>Remediation: `DELETE_RECORD` (`ABSENT`)<br>Verification: `VERIFY_RECORD_ABSENT` (`ABSENT`) | Clear. Direct full deletion. |
| **`rule_02`** | `SECONDARY_IDENTIFIER` | Always | `DELETE` | Finding: `REPORT_REMAINING_RECORD` (`PRESENT`)<br>Remediation: `DELETE_RECORD` (`ABSENT`)<br>Verification: `VERIFY_RECORD_ABSENT` (`ABSENT`) | Clear. Historical/alternate identifiers must be deleted. |
| **`rule_03`** | `SEARCH_INDEX_ENTRY` | Always | `DELETE` | Finding: `REPORT_REMAINING_RECORD` (`PRESENT`)<br>Remediation: `DELETE_RECORD` (`ABSENT`)<br>Verification: `VERIFY_RECORD_ABSENT` (`ABSENT`) | Clear. Search index documents pointing to subject must be purged. |
| **`rule_04`** | `CACHE_ENTRY` | Always | `DELETE` | Finding: `REPORT_REMAINING_RECORD` (`PRESENT`)<br>Remediation: `DELETE_RECORD` (`ABSENT`)<br>Verification: `VERIFY_RECORD_ABSENT` (`ABSENT`) | Clear. Redis/cache entries must be purged. |
| **`rule_05`** | `SUPPORT_MESSAGE` | Conversation contains shared customer, agent, or order context that must be retained | `REDACT` | Finding: `REPORT_EXPOSED_PII` (`PRESENT`)<br>Remediation: `REDACT_RECORD` (`REDACTED`)<br>Verification: `VERIFY_RECORD_REDACTED` (`REDACTED`) | Clear. Multi-party conversation must be preserved while redacting customer direct identifiers. |
| **`rule_06`** | `SUPPORT_ATTACHMENT` | Attachment belongs only to the deletion subject | `DELETE` | Finding: `REPORT_REMAINING_RECORD` (`PRESENT`)<br>Remediation: `DELETE_RECORD` (`ABSENT`)<br>Verification: `VERIFY_RECORD_ABSENT` (`ABSENT`) | Clear. Dedicated user documents (e.g. ID scans) must be removed entirely. |
| **`rule_07`** | `ANALYTICS_PROFILE` | Record is still attributable to a user | `ANONYMIZE` | Finding: `REPORT_EXPOSED_PII` (`PRESENT`)<br>Remediation: `ANONYMIZE_RECORD` (`ANONYMIZED`)<br>Verification: `VERIFY_RECORD_ANONYMIZED` (`ANONYMIZED`) | Clear. Irreversibly unlink analytics record from user identifiers. |
| **`rule_08`** | `PRODUCT_TELEMETRY` | Record is still attributable to a user | `ANONYMIZE` | Finding: `REPORT_EXPOSED_PII` (`PRESENT`)<br>Remediation: `ANONYMIZE_RECORD` (`ANONYMIZED`)<br>Verification: `VERIFY_RECORD_ANONYMIZED` (`ANONYMIZED`) | Clear. Telemetry streams must strip attributing IDs. |
| **`rule_09`** | `USER_EXPORT` | Always | `DELETE` | Finding: `REPORT_REMAINING_RECORD` (`PRESENT`)<br>Remediation: `DELETE_RECORD` (`ABSENT`)<br>Verification: `VERIFY_RECORD_ABSENT` (`ABSENT`) | Clear. Data download archives must be deleted. |
| **`rule_10`** | `MARKETING_PROFILE` | Always | `DELETE` | Finding: `REPORT_REMAINING_RECORD` (`PRESENT`)<br>Remediation: `DELETE_RECORD` (`ABSENT`)<br>Verification: `VERIFY_RECORD_ABSENT` (`ABSENT`) | Clear. Marketing leads and CRM profiles must be deleted. |
| **`rule_11`** | `EMAIL_DELIVERY_LOG` | Log contains a user email address | `REDACT` | Finding: `REPORT_EXPOSED_PII` (`PRESENT`)<br>Remediation: `REDACT_RECORD` (`REDACTED`)<br>Verification: `VERIFY_RECORD_REDACTED` (`REDACTED`) | Clear. Delivery logs preserved, recipient email redacted. |
| **`rule_12`** | `SECURITY_AUDIT_LOG` | Record is within the supplied retention period | `RETAIN` | Verification: `VERIFY_RECORD_PRESENT` (`PRESENT`) | **Note**: Audit logs within retention must be kept. The grammar provides `VERIFY_RECORD_PRESENT`, but lacks a finding for premature deletion. |
| **`rule_13`** | `LEGAL_HOLD_RECORD` | A supplied legal hold is active | `RETAIN` | Verification: `VERIFY_RECORD_PRESENT` (`PRESENT`) | **Note**: Active legal hold records must remain available. |
| **`rule_14`** | `BACKUP_ARCHIVE` | Restore access can be blocked | `RETAIN` | Finding: `REPORT_RESTORE_RISK` (`ACTIVE`)<br>Remediation: `BLOCK_RESTORE` (`BLOCKED`)<br>Verification: `VERIFY_RESTORE_BLOCKED` (`BLOCKED`) | Clear. Backups are preserved, but unblocked restore access creates a recreation risk. |
| **`rule_15`** | `ACCOUNT_TOMBSTONE` | Account is deleted and only a stable internal user_id is needed to preserve references to retained records | `REDACT` | Finding: `REPORT_EXPOSED_PII` (`PRESENT`)<br>Remediation: `REDACT_RECORD` (`REDACTED`)<br>Verification: `VERIFY_RECORD_REDACTED` (`REDACTED`) | Clear. Stable `user_id` is retained; direct identifiers (name, email, phone, email_hash) are redacted. |

*(Note on Data Flows: Process flows that replicate or re-sync deleted data map to `REPORT_ACTIVE_DATA_FLOW` $\rightarrow$ `DISABLE_DATA_FLOW` $\rightarrow$ `VERIFY_DATA_FLOW_DISABLED`.)*

---

## 5. Sample Analysis (`sample_deletion_requests.csv` & `sample_output.csv`)

### 5.1 Status Distribution in Sample Output
- **Total sample cases**: 32
- **`INCOMPLETE`**: 22 cases (68.75%)
- **`COMPLETE`**: 10 cases (31.25%)
- **`NOT_APPLICABLE`**: 0 cases in the sample set (0.00%)

### 5.2 Representative Examples by Status

#### A. Status: `COMPLETE` (Example: `case_01`)
- **Input row in `sample_deletion_requests.csv`**:
  ```csv
  case_01,amina.elmasri@gmail.com,2026-08-18T09:14:00Z,COMPLETE,2026-08-20T16:42:00Z,2026-09-03T11:30:00Z,"Hi, I haven’t used this account in years and would like it closed. Please remove the profile and the personal details attached to it."
  ```
- **Output `steps_json`**:
  ```json
  [
    {
      "step_no": 1,
      "phase": "VERIFICATION",
      "system_id": "account_service",
      "resource_id": "account_001",
      "operation": "VERIFY_RECORD_ABSENT",
      "state": "ABSENT",
      "evidence_id": "evidence_54"
    }
  ]
  ```
  *Structure*: Only contains `VERIFICATION` steps proving the compliant state at `audit_at`. Cites concrete evidence (`evidence_54`).

#### B. Status: `INCOMPLETE` (Example: `case_05`)
- **Input row in `sample_deletion_requests.csv`**:
  ```csv
  case_05,david.kim.8271@gmail.com,2026-08-20T11:15:00Z,COMPLETE,2026-08-22T19:30:00Z,2026-09-04T12:00:00Z,I deleted this account and received a confirmation, but the same email address is still recognized. Please remove any remaining copy of my profile.
  ```
- **Output `steps_json`**:
  ```json
  [
    {
      "step_no": 1,
      "phase": "FINDING",
      "system_id": "account_service",
      "resource_id": "account_005",
      "operation": "REPORT_REMAINING_RECORD",
      "state": "PRESENT",
      "evidence_id": "evidence_54"
    },
    {
      "step_no": 2,
      "phase": "REMEDIATION",
      "system_id": "account_service",
      "resource_id": "account_005",
      "operation": "DELETE_RECORD",
      "state": "ABSENT",
      "evidence_id": ""
    },
    {
      "step_no": 3,
      "phase": "VERIFICATION",
      "system_id": "account_service",
      "resource_id": "account_005",
      "operation": "VERIFY_RECORD_ABSENT",
      "state": "ABSENT",
      "evidence_id": ""
    }
  ]
  ```
  *Structure*:
  - `FINDING` cites proof evidence (`evidence_54`).
  - Proposed `REMEDIATION` uses `evidence_id: ""`.
  - Future `VERIFICATION` uses `evidence_id: ""`.

#### C. Status: `NOT_APPLICABLE` (Contract Specification & Full Dataset Examples)
While `sample_output.csv` does not contain `NOT_APPLICABLE` rows, the specification explicitly defines non-deletion cases:
- **Canonical Output Row Format**:
  ```csv
  case_000,NOT_APPLICABLE,[]
  ```
- **Representative `NOT_APPLICABLE` Requests in Full Dataset (`deletion_requests.csv`)**:
  - `case_393`:
    > *"Can you tell me what personal information you hold about me? This is an information request, not a deletion request."*
  - `case_424`:
    > *"Could you send me a copy of the information held on my account? I still use it, so please don't delete anything."*
  - `case_482`:
    > *"I want to update my delivery address on file, but please keep my profile active."*

### 5.3 Audit of Steps on `INCOMPLETE` Cases
Across all 22 `INCOMPLETE` cases in `sample_output.csv`:
1. **Evidence ID on Findings**: Every `FINDING` step cites a non-empty `evidence_id` (`file_id`, `activity_id`, or `audit_id`). There are 0 findings with missing evidence.
2. **Evidence ID on Remediation**: Every `REMEDIATION` step has `evidence_id == ""` (empty string).
3. **Evidence ID on Verification for Incomplete**: Every `VERIFICATION` step on an `INCOMPLETE` case has `evidence_id == ""` (empty string).
4. **Evidence ID on Verification for Complete**: Every `VERIFICATION` step on a `COMPLETE` case has a non-empty `evidence_id` (citing proof).

---

## 6. Ambiguity Log

| Ambiguity Item | Observed Context | Established Truth / Decision |
| :--- | :--- | :--- |
| **1. `problem_statement.md` File Path** | Prompt instructs reading `dataset/problem_statement.md` alongside root. | `dataset/problem_statement.md` does not exist. Only `./problem_statement.md` at repository root exists. |
| **2. Zero `NOT_APPLICABLE` Samples in `sample_output.csv`** | All 32 public samples are either `INCOMPLETE` (22) or `COMPLETE` (10). | Specification in §6.3 and `problem_statement.md` governs: `NOT_APPLICABLE` uses status `NOT_APPLICABLE` and `steps_json: []`. Full dataset (`deletion_requests.csv`) contains access and export requests that authorize no deletion. |
| **3. Handling Missing Retained Records** | `rule_12` and `rule_13` require retention of security logs and legal records. | Grammar does not define a `REPORT_MISSING_RECORD` finding. If retained records are intact, they are verified with `VERIFY_RECORD_PRESENT`. |
| **4. Report Packaging Directory Hierarchy** | AGENTS.md specifies `evaluation/evaluation_report.md`, while README specifies `code/evaluation/evaluation_report.md`. | README notes that `code/evaluation/` is bundled by default with `zip -r code.zip README.md code`. Keeping reports under `code/evaluation/` fulfills both requirements cleanly. |
