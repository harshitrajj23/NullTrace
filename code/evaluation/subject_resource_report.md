# NullTrace: Subject-to-Resource Key Scan Report

## 1. Manifest and Dataset Schema Findings

- **`evidence_files.csv` Header**: `file_id,file_path,origin,captured_at`
  - **Subject Identifier Columns**: None.
  - **Resource Identifier Columns**: `file_id` (evidence bundle ID), `file_path` (path to evidence file).
  - **Distinct Value Counts (<= 5)**: None (all columns have > 5 distinct values).

- **Other Dataset CSV Schemas (Excluding Answer Keys)**:
  - `deletion_requests.csv` (`case_id,email,requested_at,reported_status,reported_at,audit_at,request_text`): `email` is subject identifier; `reported_status` has 3 values (`COMPLETE`, `NOT_STARTED`, `PARTIALLY_COMPLETE`).
  - `sample_deletion_requests.csv` (`case_id,email,requested_at,reported_status,reported_at,audit_at,request_text`): `email` is subject identifier; `reported_status` has 3 values (`COMPLETE`, `PARTIALLY_COMPLETE`, `NOT_STARTED`).
  - `user_identities.csv` (`user_id,name,email,phone,email_hash,updated_at`): `user_id`, `name`, `email`, `phone`, `email_hash` are subject identifiers.
  - `user_audit_log.csv` (`audit_id,user_id,event_time,field_name,old_value,new_value`): `user_id`, `old_value`, `new_value` carry subject identifiers; `field_name` has 3 values (`email`, `email_hash`, `phone`).
  - `system_activity.csv` (`activity_id,event_time,event_type,source_system,target_system,resource_id,reported_result,details`): `resource_id` carries resource tokens; `details` carries subject identifiers in only 12 catalog rows; `reported_result` has 3 values (`SUCCESS`, `FAILED`, `PARTIAL`).
  - `deletion_rules.csv` (`rule_id,data_category,condition,required_action`): `required_action` has 4 values (`DELETE`, `REDACT`, `ANONYMIZE`, `RETAIN`).

---

## 2. File Status Counts Across Dataset & Evidence

- **Total Files Scanned**: 101
- **`IMAGE_ONLY`**: 11
- **`TEXT_OK`**: 90

### Non-Text Files Requiring OCR / Vision Model
- `dataset/evidence/images/account_admin_console_20260926.png` (`IMAGE_ONLY`)
- `dataset/evidence/images/analytics_profile_view_20260713.png` (`IMAGE_ONLY`)
- `dataset/evidence/images/backup_restore_console_20260429.png` (`IMAGE_ONLY`)
- `dataset/evidence/images/connector_management_console_20260807.png` (`IMAGE_ONLY`)
- `dataset/evidence/images/customer_export_console_20260618.png` (`IMAGE_ONLY`)
- `dataset/evidence/images/deleted_account_reference_20260310.png` (`IMAGE_ONLY`)
- `dataset/evidence/images/marketing_profile_console.png` (`IMAGE_ONLY`)
- `dataset/evidence/images/object_storage_browser_20260213.png` (`IMAGE_ONLY`)
- `dataset/evidence/images/search_index_inspector_20260901.png` (`IMAGE_ONLY`)
- `dataset/evidence/images/security_audit_explorer_20260905.png` (`IMAGE_ONLY`)
- `dataset/evidence/images/support_ticket_console_20260524.png` (`IMAGE_ONLY`)

---

## 3. Co-occurrence Summary

- **Total Co-occurrence Links Found**: 2412
- **Resource IDs with at least One Co-occurring Subject Identifier**: 1248
- **Resource IDs with Zero Co-occurring Subject Identifiers**: 2881

---

## 4. Scoring-Only Comparison (Sample Output Answer Key)

- **Total Expected Resource Pairs in Sample Output**: 111
- **Expected Pairs Linkable via Direct Co-occurrence**: 38 (34.2%)
- **Expected Pairs Not Directly Linkable on Same Line**: 73 (65.8%)
- **Extra Co-occurring Resources**: 4

---

## 5. Re-check of the 4 Previously 'Unfound' IDs (Answer-Key Isolation)

| Resource ID | Match Status | Location | Context |
| :--- | :--- | :--- | :--- |
| `account_004` | **No match found** | None | Absent from all participant-facing evidence content and dataset tables |
| `support_001` | **FOUND** | `dataset/evidence/documents/delivery_correction_attachment.pdf` (page 1) | `Support reference CS-4827 / support_001` |
| `support_001` | **FOUND** | `dataset/evidence/documents/delivery_correction_attachment.pdf` (page 1) | `reference CS-4827 / support_001` |
| `audit_record_5569` | **No match found** | None | Absent from all participant-facing evidence content and dataset tables |
| `audit_record_6645` | **No match found** | None | Absent from all participant-facing evidence content and dataset tables |

---

## 6. The Most Likely Subject-to-Resource Key

The primary data source linking subjects to system resource IDs is the relational schema within evidence database dumps (`dataset/evidence/databases/*.sql`) and JSON snapshot bundles (`dataset/evidence/records/*.json`), where internal user IDs (`user_*`) directly co-occur as primary and foreign keys alongside resource records (`account_*`, `search_*`, `analytics_*`, `audit_record_*`, `support_*`). While uncompressed PDF parsing via `pypdf` successfully recovers document-level support tickets (e.g. `support_001`), the linker still cannot observe: (1) multi-hop relational dependencies where a resource references an account table rather than the subject directly; (2) resources stored in the 11 non-text console screenshots (`dataset/evidence/images/*.png`); and (3) records whose direct identifiers have already been deleted or tombstoned prior to the snapshot capture time.
