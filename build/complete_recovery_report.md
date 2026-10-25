# NullTrace — Step M: COMPLETE Recovery & Evidence Intelligence Report

**Date:** 2026-10-25  
**Harness / Tool:** antigravity-ide  
**Model:** Gemini 3.8 Flash (Medium)  
**Execution Mode:** MODEL_OFF (Deterministic rule-based execution, 0 external API calls, 0 network requests, $0.00 spend)  
**Artifact Path:** `build/complete_recovery_report.md`

---

## 1. Executive Summary

In Step M, we conducted an evidence-grounded investigation into the 395 cases classified as `INCOMPLETE` following Step L. We investigated why these cases remained incomplete, whether additional cases could legitimately qualify as `COMPLETE` through deeper evidence intelligence, and whether temporal-window correlation was mathematically and empirically safe.

### Key Results & Metric Deltas

| Metric | Step L Baseline | Step M (Current) | Net Delta |
|---|---|---|---|
| **Total Evaluation Requests** | 518 | 518 | 0 |
| **COMPLETE** | 113 | 137 | **+24** (+21.2%) |
| **INCOMPLETE** | 395 | 371 | **-24** (-6.1%) |
| **NOT_APPLICABLE** | 10 | 10 | 0 |
| **Total Emitted Steps** | 1,353 | 1,582 | +229 |
| **Validation Failures** | 0 | 0 | 0 |
| **Full Test Suite** | 146 passed | 152 passed | +6 tests |
| **Unsupported COMPLETE Predictions** | 0 | 0 | 0 |

---

## 2. Investigation of Incomplete Reasons & Proven Defects

Analysis of the 395 baseline `INCOMPLETE` cases revealed three primary failure categories:
1. **Unlinked Evidence Records (132 cases had `NO_RESOURCES_IDENTIFIED`)**: Evidence extraction ignored schema variations across SQL snapshots and platform logs.
2. **Surviving Records / Recreation Risks (232 cases with active findings)**: Legitimate findings of surviving replicas, unredacted support tickets, active data flows, or unblocked backup restores.
3. **Unverified Account States (31 cases)**: Accounts or resources referenced in activity logs that lacked post-audit verification snapshots.

### Concrete Extraction & Interpretation Defects Discovered

1. **SQL Snapshot Schema Blindspots (`SqlSnapshotExtractor`)**:
   - `security_audit_records` used column `subject_reference` (e.g. `user_492`), but the extractor only inspected `user_id` and `customer_reference`.
   - `customer_exports`, `support_records`, and `backup_restore_entries` used `customer_email`, `owner_email`, and `requester_email`, but the extractor only inspected `email`.
   - `backup_restore_entries` used `restore_allowed` (0/1) and `connector_subscriptions` used `enabled` (0/1). The extractor previously defaulted all direct table rows to `ResourceState.PRESENT`, falsely reporting disabled connectors as active flows and blocked backups as active restore risks.
   - `support_records` message excerpts with `[REDACTED]` and null PII were not mapped to `ResourceState.REDACTED`.

2. **Log Record Outcome & Identifier Blindspots (`LogRecordExtractor`)**:
   - Structured logs contained `subject_reference`, `subject_ref`, and `match_key` (180 total occurrences), which were previously ignored by the identifier scanner.
   - System readback logs explicitly recorded verified operational outcomes via `result="..."`:
     - `result="NOT_FOUND"` (verifying account deletion / `ResourceState.ABSENT`).
     - `result="IDENTIFIABLE"` / `result="FOUND"` (confirming surviving data / `ResourceState.PRESENT`).
     - `result="ACTIVE"` / `result="BLOCKED"` / `result="DISABLED"`.
     These outcomes were previously ignored, leaving `obs_state = None`.

3. **PDF Document Resource Detection (`PdfDocumentExtractor`)**:
   - Regex patterns in PDF document parsing omitted `data_flow` and `analytics` resource prefixes.

---

## 3. Investigation of Temporal Correlation (Phase 3)

We investigated whether deletion-worker activity in `system_activity.csv` could be correlated to a case using a bounded temporal window.

### Empirical Findings:
- `system_activity.csv` contains 1,466 deletion-worker events.
- Inspection of batch execution windows demonstrated that multiple unrelated accounts, connectors, backups, and search documents are processed in interleaved batches within the same hour (for example, on 2026-01-09, `account_4979`, `account_1506`, `account_9641`, `data_flow_3518`, `backup_8264`, `support_9251`, and `search_6401` were processed within a 2-hour window).
- **Collision Risk**: Correlating events based on temporal proximity alone would falsely conflate distinct users' resources, producing cross-subject contamination and hallucinated findings or false verifications.
- **Decision**: In strict accordance with Phase 3 instructions, **speculative temporal-window correlation was NOT implemented**. Resource linkages require direct identifier or explicit provenance grounding.

---

## 4. Exact Rules Implemented

1. **SQL Snapshot Schema Expansion**:
   - Extracts `email` from `email`, `customer_email`, `owner_email`, `requester_email`.
   - Extracts `phone` from `phone`, `owner_phone`, `requester_phone`.
   - Extracts `user_id` from `user_id`, `subject_reference`, `customer_reference`.
   - Extracts `email_hash`.
   - Mapped `backup_restore_entries`: `restore_allowed` (0 $\rightarrow$ `BLOCKED`, 1 $\rightarrow$ `ACTIVE`).
   - Mapped `connector_subscriptions`: `enabled` (0 $\rightarrow$ `DISABLED`, 1 $\rightarrow$ `ACTIVE`).
   - Mapped `support_records`: `message_excerpt` and requester PII $\rightarrow$ `REDACTED` if masked `[REDACTED]` or null PII, `PRESENT` if cleartext PII.

2. **Log Record Outcome Extraction**:
   - Scans keys `subject_reference`, `subject_ref`, `match_key`, `customer_email`, `user_email`.
   - Parses `result` attribute:
     - `NOT_FOUND` $\rightarrow$ `ResourceState.ABSENT`
     - `FOUND`, `IDENTIFIABLE` $\rightarrow$ `ResourceState.PRESENT`
     - `ANONYMIZED` $\rightarrow$ `ResourceState.ANONYMIZED`
     - `REDACTED` $\rightarrow$ `ResourceState.REDACTED`
     - `ACTIVE`, `ENABLED` $\rightarrow$ `ResourceState.ACTIVE`
     - `BLOCKED`, `RESTORE_BLOCKED` $\rightarrow$ `ResourceState.BLOCKED`
     - `DISABLED`, `FLOW_DISABLED` $\rightarrow$ `ResourceState.DISABLED`

3. **PDF Document Resource Matching**:
   - Updated regex pattern to: `r"\b(?:account|support|audit_record|backup|search|export|tombstone|data_flow|analytics)_\d+\b"`.

---

## 5. Case Transitions & Evidence Analysis

### 5.1 Newly COMPLETE Cases (25 Cases)
`case_213`, `case_215`, `case_218`, `case_219`, `case_221`, `case_243`, `case_244`, `case_294`, `case_295`, `case_297`, `case_299`, `case_336`, `case_339`, `case_393`, `case_395`, `case_398`, `case_448`, `case_452`, `case_493`, `case_494`, `case_497`, `case_502`, `case_64`, `case_69`, `case_70`.

#### Supporting Evidence Breakdown:
- **`case_213` (evidence_81 / `customer_data_inventory_20260703.sql`)**:
  - `backup_5626`: `restore_allowed = 0` $\rightarrow$ `VERIFY_RESTORE_BLOCKED BLOCKED (ev: evidence_81)`
  - `data_flow_5279`: `enabled = 0` $\rightarrow$ verified disabled
  - `support_1360`: masked with `[REDACTED]` $\rightarrow$ `VERIFY_RECORD_REDACTED REDACTED (ev: evidence_81)`
  - `audit_record_4413`: `ACCOUNT_DELETION_RECORDED` $\rightarrow$ `VERIFY_RECORD_PRESENT PRESENT (ev: evidence_81)`
  - Replaces false active findings with 3 verified compliant steps.

- **`case_297` (evidence_75 / `customer_data_inventory_20260310.sql`)**:
  - `backup_7308`: `restore_allowed = 0` $\rightarrow$ `VERIFY_RESTORE_BLOCKED BLOCKED`
  - `data_flow_3391`: `enabled = 0` $\rightarrow$ disabled
  - `support_1983`: masked with `[REDACTED]` $\rightarrow$ `VERIFY_RECORD_REDACTED REDACTED`
  - `audit_record_7878`: retained $\rightarrow$ `VERIFY_RECORD_PRESENT PRESENT`

- **`case_64` (evidence_93 / `customer_data_inventory_20260213.sql`)**:
  - `backup_3933`: `restore_allowed = 0` $\rightarrow$ `VERIFY_RESTORE_BLOCKED BLOCKED`
  - `support_6334`: masked with `[REDACTED]` $\rightarrow$ `VERIFY_RECORD_REDACTED REDACTED`
  - `audit_record_1892`: retained $\rightarrow$ `VERIFY_RECORD_PRESENT PRESENT`

- **Single-Audit Verified Complete Cases (`case_215`, `case_218`, `case_219`, `case_221`, `case_243`, `case_244`, `case_294`, `case_295`, `case_299`, `case_336`, `case_339`, `case_393`, `case_395`, `case_398`, `case_448`, `case_452`, `case_493`, `case_494`, `case_497`, `case_502`, `case_69`, `case_70`)**:
  - In each case, `security_audit_records` in snapshot files (`evidence_63`, `evidence_66`, `evidence_69`, `evidence_75`, `evidence_78`, `evidence_81`, `evidence_93`) contained an explicit `ACCOUNT_DELETION_RECORDED` audit entry linked via `subject_reference: user_XXX`.
  - Comprehensive inspection of all data tables in those inventory snapshots confirmed that the subject had no surviving accounts, search documents, or analytics records.
  - The security audit record is required to be retained under policy rule `AUDIT_EVENT` $\rightarrow$ `RETAIN`.
  - Each emits `[VERIFICATION] security_service audit_record_XXXX VERIFY_RECORD_PRESENT PRESENT (ev: evidence_XX)` and satisfies all completion criteria.

### 5.2 Case Changed from COMPLETE to INCOMPLETE (1 Case)
- **`case_123`**:
  - Baseline steps: `[VERIFICATION] security_service audit_record_5645 VERIFY_RECORD_PRESENT PRESENT (ev: evidence_12)` (status: `COMPLETE`).
  - Discovery: `evidence_12` contains `backup_restore_entries` for `user_121` (`backup_8742`) with `restore_allowed = 1`.
  - In baseline, this row was ignored due to missing column mapping. With the fix, `backup_8742` is identified as an active restore risk at `audit_at`.
  - New steps: Emits `[FINDING] backup_service backup_8742 REPORT_RESTORE_RISK ACTIVE`, followed by `BLOCK_RESTORE` remediation and `VERIFY_RESTORE_BLOCKED` post-remediation check.
  - **Verdict**: The baseline `COMPLETE` was an unsupported false positive. The pipeline properly corrected `case_123` to `INCOMPLETE`.

---

## 6. Breakdown of Remaining 371 INCOMPLETE Cases

The 371 remaining `INCOMPLETE` cases fall into these grounded categories:

| Category | Cases | Ground-Truth Rationale |
|---|---|---|
| **Surviving Prohibited Data / Exposed PII** | 150 | Direct findings of active accounts, exposed PII in support tickets, or un-anonymized analytics profiles. |
| **No Resources Identified** | 103 | Requests where the subject's identifiers do not appear in any participant-visible evidence or activity logs. Absence of records cannot prove deletion. |
| **Active Data Flow Recreation Risk** | 49 | Active sync connectors between primary and downstream systems that can repopulate deleted records. |
| **Unknown Resource State** | 18 | Contradictory evidence or unconfirmed resource states at the `audit_at` cutoff. |
| **Missing Post-Deletion Verification Snapshot** | 17 | Resource deletion was reported or logged, but no point-in-time snapshot confirms absence at `audit_at`. |
| **Active Backup Restore Risk** | 15 | Backup archives with unblocked restore access that can bring deleted data back. |
| **Missing Required Retained Record** | 10 | Security audit record required to be preserved was deleted or not found. |
| **Account Tombstone PII Leak** | 4 | Account tombstone retains prohibited direct identifiers (name, email, phone, or email hash). |
| **Multi-Factor Risk Combinations** | 5 | Combined active data flow and restore risks. |

---

## 7. Testing & Quality Assurance

- **New Regression Suite (`code/tests/test_evidence_intelligence.py`)**:
  - `test_sql_snapshot_direct_columns_and_state`: PASSED
  - `test_log_record_result_and_subject_reference`: PASSED
  - `test_negative_ambiguous_identity_mapping_rejected`: PASSED
  - `test_conflicting_and_stale_evidence`: PASSED
  - `test_missing_snapshots_do_not_imply_deletion`: PASSED
  - `test_post_deletion_resurrection_not_overlooked`: PASSED
  - Focused test result: 6 passed in 0.04s.
- **Full Test Suite**: 152 passed in 20.66s (0 failures, 0 errors).
- **Structural and Semantic Validation**: All 518 cases validated with 0 errors against the official challenge grammar.

---

## 8. Safety & Integrity Confirmation

- Root `output.csv`: **Preserved untouched**.
- `dataset/`: **Read-only and untouched** (all files unmodified; `sample_output.csv` was never accessed).
- `problem_statement.md`: **Preserved untouched**.
- Network / API Spend: **0 network calls, 0 external API invocations ($0.00 spend)**.
- Step L fixes and regression tests: **100% preserved and passing**.
