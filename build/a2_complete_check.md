# NullTrace: Hand-Check of 10 Additional COMPLETE Rows (A2 Audit)

**Challenge**: HackerRank Orchestrate (October 2026) — *Ghost Data Still Exists*  
**Step**: Step 2 Hand-Check (`random.Random(7).sample` over candidate A2 `COMPLETE` cases)  
**Mode**: `DECISION: MODEL_OFF` (Read-only inspection; deterministic evidence audit)  
**Date**: 2026-10-25T10:42:00+05:30  

---

## 1. Selection Methodology

Using `random.Random(7).sample` over the sorted list of 161 `COMPLETE` case IDs from `build/nulltrace_candidate_a2.csv` (excluding previously audited `case_111`, `case_196`, `case_319`):
* Total eligible candidate `COMPLETE` cases: **159**
* Sampled 10 Case IDs: **`case_360`**, **`case_226`**, **`case_423`**, **`case_151`**, **`case_162`**, **`case_530`**, **`case_191`**, **`case_393`**, **`case_73`**, **`case_154`**

---

## 2. Per-Case Audits

### 2.1 Case `case_360`
* **Request & Cluster**:
  * Request Email: `mrahman973184@fastmail.com`
  * Requested At: `2026-03-27T08:00:00Z`
  * Cutoff (`audit_at`): `2026-04-24T08:00:00Z`
  * Cluster Identity: `user_358` (Mariam Rahman), phone `+971 54 561 5205`, current email `mrahman9731@fastmail.com`, historical email `mrahman973184@fastmail.com` (from `audit_136`).
* **Candidate Steps**:
  ```json
  [
    {
      "step_no": 1,
      "phase": "VERIFICATION",
      "system_id": "security_service",
      "resource_id": "audit_record_2605",
      "operation": "VERIFY_RECORD_PRESENT",
      "state": "PRESENT",
      "evidence_id": "evidence_33"
    }
  ]
  ```
* **Evidence Timestamps**:
  * `evidence_33`: `dataset/evidence/databases/customer_data_regional_replicas_20260424.sql`, captured at `2026-04-24T08:00:00Z` <= `2026-04-24T08:00:00Z` -> **PRE_AUDIT**.
* **Quoted Verbatim Lines**:
  * `dataset/evidence/databases/customer_data_regional_replicas_20260424.sql:21`:
    ```sql
    INSERT INTO "customer_data_primary" VALUES('audit_record_2605','security_service','security_audit_events','{"resource_id":"audit_record_2605","subject_reference":"user_358","event_name":"account_deletion_reviewed","actor_type":"automated_privacy_workflow","integrity_seal":"sha256:0000000000000000000000000000000000000000000000000000000000000a2d"}','2026-04-24T08:00:00Z');
    ```
  * `dataset/evidence/databases/customer_data_regional_replicas_20260424.sql:57`:
    ```sql
    INSERT INTO "customer_data_replica_ap_south" VALUES('audit_record_2605','security_service','security_audit_events','{"resource_id":"audit_record_2605","subject_reference":"user_358","event_name":"account_deletion_reviewed","actor_type":"automated_privacy_workflow","integrity_seal":"sha256:0000000000000000000000000000000000000000000000000000000000000a2d"}','2026-04-24T08:00:00Z');
    ```
  * `dataset/evidence/databases/customer_data_regional_replicas_20260424.sql:95`:
    ```sql
    INSERT INTO "customer_data_replica_eu_west" VALUES('audit_record_2605','security_service','security_audit_events','{"resource_id":"audit_record_2605","subject_reference":"user_358","event_name":"account_deletion_reviewed","actor_type":"automated_privacy_workflow","integrity_seal":"sha256:0000000000000000000000000000000000000000000000000000000000000a2d"}','2026-04-24T08:00:00Z');
    ```
* **System Activity & Flows**:
  * 0 activity rows touching cluster or resource. No active sync, import, replication, or restore events.
* **Verdict**: **PASS**

---

### 2.2 Case `case_226`
* **Request & Cluster**:
  * Request Email: `wright.sophie@icloud.com`
  * Requested At: `2026-06-14T07:00:00Z`
  * Cutoff (`audit_at`): `2026-06-28T07:00:00Z`
  * Cluster Identity: `user_224` (Sophie Wright), phone `+44 7700 900224`, email `wright.sophie@icloud.com`.
* **Candidate Steps**:
  ```json
  [
    {
      "step_no": 1,
      "phase": "VERIFICATION",
      "system_id": "security_service",
      "resource_id": "audit_record_9964",
      "operation": "VERIFY_RECORD_PRESENT",
      "state": "PRESENT",
      "evidence_id": "evidence_22"
    }
  ]
  ```
* **Evidence Timestamps**:
  * `evidence_22`: `dataset/evidence/records/customer_data_snapshot_bundle_20260630.json`, captured at `2026-06-30T07:00:00Z` > `2026-06-28T07:00:00Z` -> **POST_AUDIT** (Failure).
* **Quoted Verbatim Lines**:
  * `dataset/evidence/records/customer_data_snapshot_bundle_20260630.json:263`:
    ```json
    "resource_id": "audit_record_9964",
    ```
* **System Activity & Flows**:
  * 0 activity rows found.
* **Verdict**: **FAIL**
  * Failing Rule: Post-audit evidence cited (`evidence_22` captured 2026-06-30 vs audit cutoff 2026-06-28). Per contract §6.2 and §6.6, evidence captured after audit_at cannot prove state.
  * Demotion: Demoted to `INCOMPLETE`. No pre-audit evidence supports a finding, so it is listed as an unresolved exception in `build/unresolved_cases.csv`.

---

### 2.3 Case `case_423`
* **Request & Cluster**:
  * Request Email: `e.dahl28@gmail.com`
  * Requested At: `2026-03-09T08:00:00Z`
  * Cutoff (`audit_at`): `2026-03-20T08:00:00Z`
  * Cluster Identity: `user_421` (Erik Dahl), phone `+46 70 528 08 47`, email `e.dahl28@gmail.com`.
* **Candidate Steps**:
  ```json
  [
    {
      "step_no": 1,
      "phase": "VERIFICATION",
      "system_id": "account_service",
      "resource_id": "account_2420",
      "operation": "VERIFY_RECORD_ABSENT",
      "state": "ABSENT",
      "evidence_id": "evidence_68"
    },
    {
      "step_no": 2,
      "phase": "VERIFICATION",
      "system_id": "security_service",
      "resource_id": "audit_record_8082",
      "operation": "VERIFY_RECORD_PRESENT",
      "state": "PRESENT",
      "evidence_id": "evidence_40"
    }
  ]
  ```
* **Evidence Timestamps**:
  * `evidence_68`: `dataset/evidence/records/service_resource_export_20260320_072349.json`, captured at `2026-03-20T07:23:49Z` <= `2026-03-20T08:00:00Z` -> PRE_AUDIT.
  * `evidence_40`: `dataset/evidence/records/customer_data_snapshot_bundle_20260322.json`, captured at `2026-03-22T08:00:00Z` > `2026-03-20T08:00:00Z` -> **POST_AUDIT** (Failure).
* **Quoted Verbatim Lines**:
  * `dataset/evidence/records/service_resource_export_20260320_072349.json:10`:
    ```json
    "resource_id": "account_2420", "status_code": 404
    ```
  * `dataset/evidence/records/customer_data_snapshot_bundle_20260322.json:283`:
    ```json
    "resource_id": "audit_record_8082",
    ```
* **System Activity & Flows**:
  * `activity_952`: `DELETE_RECORD` on `account_2420`, reported_result `SUCCESS`.
* **Verdict**: **FAIL**
  * Failing Rule: Post-audit evidence cited (`evidence_40` captured 2026-03-22 vs audit cutoff 2026-03-20).
  * Demotion: Demoted to `INCOMPLETE`. Listed as an unresolved exception in `build/unresolved_cases.csv`.

---

### 2.4 Case `case_151`
* **Request & Cluster**:
  * Request Email: `elena.i4660@outlook.com`
  * Requested At: `2026-07-19T08:00:00Z`
  * Cutoff (`audit_at`): `2026-08-07T08:00:00Z`
  * Cluster Identity: `user_149` (Elena Ionescu), phone `+48 714 169 201`, email `elena.i4660@outlook.com`.
* **Candidate Steps**:
  ```json
  [
    {
      "step_no": 1,
      "phase": "VERIFICATION",
      "system_id": "security_service",
      "resource_id": "audit_record_8905",
      "operation": "VERIFY_RECORD_PRESENT",
      "state": "PRESENT",
      "evidence_id": "evidence_86"
    },
    {
      "step_no": 2,
      "phase": "VERIFICATION",
      "system_id": "support_platform",
      "resource_id": "support_5400",
      "operation": "VERIFY_RECORD_REDACTED",
      "state": "REDACTED",
      "evidence_id": "evidence_86"
    },
    {
      "step_no": 3,
      "phase": "VERIFICATION",
      "system_id": "backup_service",
      "resource_id": "backup_9557",
      "operation": "VERIFY_RESTORE_BLOCKED",
      "state": "BLOCKED",
      "evidence_id": "evidence_86"
    }
  ]
  ```
* **Evidence Timestamps**:
  * `evidence_86`: `dataset/evidence/records/service_resource_export_20260807_074104.json`, captured at `2026-08-07T07:41:04Z` <= `2026-08-07T08:00:00Z` -> **PRE_AUDIT** (All steps).
* **Quoted Verbatim Lines**:
  * `dataset/evidence/records/service_resource_export_20260807_074104.json:73`:
    ```json
    "resource_id": "backup_9557", "restore_allowed": false
    ```
  * `dataset/evidence/records/service_resource_export_20260807_074104.json:249`:
    ```json
    "resource_id": "support_5400", "requester_name": null, "requester_email": null
    ```
  * `dataset/evidence/records/service_resource_export_20260807_074104.json:234`:
    ```json
    "resource_id": "audit_record_8905", "subject_reference": "user_149"
    ```
* **System Activity & Flows**:
  * `activity_2908`: `REDACT_RECORD` on `support_5400`, SUCCESS.
  * `activity_2911`: `BLOCK_RESTORE` on `backup_9557`, SUCCESS.
  * Zero active flows.
* **Verdict**: **PASS**

---

### 2.5 Case `case_162`
* **Request & Cluster**:
  * Request Email: `cmercier1769@gmail.com`
  * Requested At: `2026-07-23T07:00:00Z`
  * Cutoff (`audit_at`): `2026-08-02T07:00:00Z`
  * Cluster Identity: `user_160` (Camille Mercier), phones `+33 6 69 34 42 56`, `+33 6 90 58 29 67`, email `cmercier1769@gmail.com`.
* **Candidate Steps**:
  ```json
  [
    {
      "step_no": 1,
      "phase": "VERIFICATION",
      "system_id": "security_service",
      "resource_id": "audit_record_6362",
      "operation": "VERIFY_RECORD_PRESENT",
      "state": "PRESENT",
      "evidence_id": "evidence_15"
    }
  ]
  ```
* **Evidence Timestamps**:
  * `evidence_15`: `dataset/evidence/databases/customer_data_read_replica_20260802.sql`, captured at `2026-08-02T07:00:00Z` <= `2026-08-02T07:00:00Z` -> **PRE_AUDIT**.
* **Quoted Verbatim Lines**:
  * `dataset/evidence/databases/customer_data_read_replica_20260802.sql:22`:
    ```sql
    INSERT INTO "customer_data_primary" VALUES('audit_record_6362','security_service','security_audit_events','{"resource_id":"audit_record_6362","subject_reference":"user_160","event_name":"account_deletion_reviewed","actor_type":"automated_privacy_workflow","integrity_seal":"sha256:00000000000000000000000000000000000000000000000000000000000018da"}','2026-08-02T07:00:00Z');
    ```
  * `dataset/evidence/databases/customer_data_read_replica_20260802.sql:54`:
    ```sql
    INSERT INTO "customer_data_read_replica" VALUES('audit_record_6362','security_service','security_audit_events','{"resource_id":"audit_record_6362","subject_reference":"user_160","event_name":"account_deletion_reviewed","actor_type":"automated_privacy_workflow","integrity_seal":"sha256:00000000000000000000000000000000000000000000000000000000000018da"}','2026-08-02T07:00:00Z');
    ```
* **System Activity & Flows**:
  * 0 activity rows found. Zero active flows.
* **Verdict**: **PASS**

---

### 2.6 Case `case_530`
* **Request & Cluster**:
  * Request Email: `chidi.oladipo78@gmail.com`
  * Requested At: `2026-01-11T12:00:00Z`
  * Cutoff (`audit_at`): `2026-01-29T12:00:00Z`
  * Cluster Identity: `user_528` (Chidi Oladipo), phone `+234 803 403 1181`, current email `chidi.oladipo@gmail.com`, historical email `chidi.oladipo78@gmail.com` (from `audit_61`).
* **Candidate Steps**:
  ```json
  [
    {
      "step_no": 1,
      "phase": "VERIFICATION",
      "system_id": "security_service",
      "resource_id": "audit_record_2152",
      "operation": "VERIFY_RECORD_PRESENT",
      "state": "PRESENT",
      "evidence_id": "evidence_49"
    }
  ]
  ```
* **Evidence Timestamps**:
  * `evidence_49`: `dataset/evidence/records/customer_data_snapshot_bundle_20260131.json`, captured at `2026-01-31T15:00:00Z` > `2026-01-29T12:00:00Z` -> **POST_AUDIT** (Failure).
* **Quoted Verbatim Lines**:
  * `dataset/evidence/records/customer_data_snapshot_bundle_20260131.json:357`:
    ```json
    "resource_id": "audit_record_2152",
    ```
* **System Activity & Flows**:
  * 0 activity rows found.
* **Verdict**: **FAIL**
  * Failing Rule: Post-audit evidence cited (`evidence_49` captured 2026-01-31 vs audit cutoff 2026-01-29).
  * Demotion: Demoted to `INCOMPLETE`. Listed as an unresolved exception in `build/unresolved_cases.csv`.

---

### 2.7 Case `case_191`
* **Request & Cluster**:
  * Request Email: `KARIM-HADDAD@PROTON.ME`
  * Requested At: `2026-06-29T11:00:00Z`
  * Cutoff (`audit_at`): `2026-07-18T11:00:00Z`
  * Cluster Identity: `user_189` (Karim Haddad), phone `+971 56 868 6752`, email `karim-haddad@proton.me`.
* **Candidate Steps**:
  ```json
  [
    {
      "step_no": 1,
      "phase": "VERIFICATION",
      "system_id": "security_service",
      "resource_id": "audit_record_7493",
      "operation": "VERIFY_RECORD_PRESENT",
      "state": "PRESENT",
      "evidence_id": "evidence_83"
    },
    {
      "step_no": 2,
      "phase": "VERIFICATION",
      "system_id": "support_platform",
      "resource_id": "support_5049",
      "operation": "VERIFY_RECORD_REDACTED",
      "state": "REDACTED",
      "evidence_id": "evidence_83"
    },
    {
      "step_no": 3,
      "phase": "VERIFICATION",
      "system_id": "backup_service",
      "resource_id": "backup_3010",
      "operation": "VERIFY_RESTORE_BLOCKED",
      "state": "BLOCKED",
      "evidence_id": "evidence_83"
    }
  ]
  ```
* **Evidence Timestamps**:
  * `evidence_83`: `dataset/evidence/records/service_resource_export_20260718_104335.json`, captured at `2026-07-18T10:43:35Z` <= `2026-07-18T11:00:00Z` -> **PRE_AUDIT** (All steps).
* **Quoted Verbatim Lines**:
  * `dataset/evidence/records/service_resource_export_20260718_104335.json:107`:
    ```json
    "resource_id": "backup_3010", "restore_allowed": false
    ```
  * `dataset/evidence/records/service_resource_export_20260718_104335.json:328`:
    ```json
    "resource_id": "support_5049", "requester_name": null, "requester_email": null
    ```
  * `dataset/evidence/records/service_resource_export_20260718_104335.json:304`:
    ```json
    "resource_id": "audit_record_7493", "subject_reference": "user_189"
    ```
* **System Activity & Flows**:
  * `activity_2594`: `REDACT_RECORD` on `support_5049`, SUCCESS.
  * `activity_2597`: `BLOCK_RESTORE` on `backup_3010`, SUCCESS.
  * Zero active flows.
* **Verdict**: **PASS**

---

### 2.8 Case `case_393`
* **Request & Cluster**:
  * Request Email: `a.menon58@yahoo.com`
  * Requested At: `2026-03-14T11:00:00Z`
  * Cutoff (`audit_at`): `2026-04-04T11:00:00Z`
  * Cluster Identity: `user_391` (Aarav Menon), phone `+91 98481 56511`, email `a.menon58@yahoo.com`.
* **Candidate Steps**:
  ```json
  [
    {
      "step_no": 1,
      "phase": "VERIFICATION",
      "system_id": "security_service",
      "resource_id": "audit_record_7330",
      "operation": "VERIFY_RECORD_PRESENT",
      "state": "PRESENT",
      "evidence_id": "evidence_69"
    }
  ]
  ```
* **Evidence Timestamps**:
  * `evidence_69`: `dataset/evidence/databases/customer_data_inventory_20260404.sql`, captured at `2026-04-04T10:04:19Z` <= `2026-04-04T11:00:00Z` -> **PRE_AUDIT**.
* **Quoted Verbatim Lines**:
  * `dataset/evidence/databases/customer_data_inventory_20260404.sql:34`:
    ```sql
    INSERT INTO security_audit_records VALUES ('audit_record_7330', 'user_391', 'ACCOUNT_DELETION_RECORDED', 'automated_privacy_workflow', '2026-04-04T10:04:19Z', '2031-12-31T23:59:59Z');
    ```
* **System Activity & Flows**:
  * 0 activity rows found. Zero active flows.
* **Verdict**: **PASS**

---

### 2.9 Case `case_73`
* **Request & Cluster**:
  * Request Email: `ana.k6978@zoho.com`
  * Requested At: `2026-08-21T08:00:00Z`
  * Cutoff (`audit_at`): `2026-09-11T08:00:00Z`
  * Cluster Identity: `user_71` (Ana Kowalski), phone `+48 572 027 769`, email `ana.k6978@zoho.com`.
* **Candidate Steps**:
  ```json
  [
    {
      "step_no": 1,
      "phase": "VERIFICATION",
      "system_id": "account_service",
      "resource_id": "account_6070",
      "operation": "VERIFY_RECORD_ABSENT",
      "state": "ABSENT",
      "evidence_id": "evidence_91"
    },
    {
      "step_no": 2,
      "phase": "VERIFICATION",
      "system_id": "security_service",
      "resource_id": "audit_record_5710",
      "operation": "VERIFY_RECORD_PRESENT",
      "state": "PRESENT",
      "evidence_id": "evidence_07"
    }
  ]
  ```
* **Evidence Timestamps**:
  * `evidence_91`: `dataset/evidence/logs/resource_lookup_trace_20260911_074253.log`, captured at `2026-09-11T07:42:53Z` <= `2026-09-11T08:00:00Z` -> PRE_AUDIT.
  * `evidence_07`: `dataset/evidence/records/customer_data_snapshot_bundle_20260913.json`, captured at `2026-09-13T08:00:00Z` > `2026-09-11T08:00:00Z` -> **POST_AUDIT** (Failure).
* **Quoted Verbatim Lines**:
  * `dataset/evidence/logs/resource_lookup_trace_20260911_074253.log:39`:
    ```text
    2026-09-11T06:55:19Z level=INFO service=account_service trace_id=rb-065519-019 event=profile_lookup_completed resource_id=account_6070 rows=0 http_status=404
    ```
  * `dataset/evidence/records/customer_data_snapshot_bundle_20260913.json:238`:
    ```json
    "resource_id": "audit_record_5710",
    ```
* **System Activity & Flows**:
  * `activity_3419`: `DELETE_RECORD` on `account_6070`, SUCCESS.
* **Verdict**: **FAIL**
  * Failing Rule: Post-audit evidence cited (`evidence_07` captured 2026-09-13 vs audit cutoff 2026-09-11).
  * Demotion: Demoted to `INCOMPLETE`. Listed as an unresolved exception in `build/unresolved_cases.csv`.

---

### 2.10 Case `case_154`
* **Request & Cluster**:
  * Request Email: `boateng.kofi@icloud.com`
  * Requested At: `2026-07-11T07:00:00Z`
  * Cutoff (`audit_at`): `2026-08-02T07:00:00Z`
  * Cluster Identity: `user_152` (Kofi Boateng), phone `+233 24 264 7521`, email `boateng.kofi@icloud.com`.
* **Candidate Steps**:
  ```json
  [
    {
      "step_no": 1,
      "phase": "VERIFICATION",
      "system_id": "security_service",
      "resource_id": "audit_record_2580",
      "operation": "VERIFY_RECORD_PRESENT",
      "state": "PRESENT",
      "evidence_id": "evidence_15"
    }
  ]
  ```
* **Evidence Timestamps**:
  * `evidence_15`: `dataset/evidence/databases/customer_data_read_replica_20260802.sql`, captured at `2026-08-02T07:00:00Z` <= `2026-08-02T07:00:00Z` -> **PRE_AUDIT**.
* **Quoted Verbatim Lines**:
  * `dataset/evidence/databases/customer_data_read_replica_20260802.sql:18`:
    ```sql
    INSERT INTO "customer_data_primary" VALUES('audit_record_2580','security_service','security_audit_events','{"resource_id":"audit_record_2580","subject_reference":"user_152","event_name":"account_deletion_reviewed","actor_type":"automated_privacy_workflow","integrity_seal":"sha256:00000000000000000000000000000000000000000000000000000000000000a0"}','2026-08-02T07:00:00Z');
    ```
  * `dataset/evidence/databases/customer_data_read_replica_20260802.sql:50`:
    ```sql
    INSERT INTO "customer_data_read_replica" VALUES('audit_record_2580','security_service','security_audit_events','{"resource_id":"audit_record_2580","subject_reference":"user_152","event_name":"account_deletion_reviewed","actor_type":"automated_privacy_workflow","integrity_seal":"sha256:00000000000000000000000000000000000000000000000000000000000000a0"}','2026-08-02T07:00:00Z');
    ```
* **System Activity & Flows**:
  * 0 activity rows found. Zero active flows.
* **Verdict**: **PASS**

---

## 3. Summary of Step 2 Audits & Demotion List

| Case ID | Candidate Status | Captured Timestamps | Active Flows / Contradictions | Audit Verdict | Action |
|:---|:---|:---|:---|:---|:---|
| `case_360` | COMPLETE | `evidence_33` (PRE_AUDIT) | None | **PASS** | Retain COMPLETE |
| `case_226` | COMPLETE | `evidence_22` (**POST_AUDIT**) | None | **FAIL** | Demote to INCOMPLETE |
| `case_423` | COMPLETE | `evidence_40` (**POST_AUDIT**) | None | **FAIL** | Demote to INCOMPLETE |
| `case_151` | COMPLETE | `evidence_86` (PRE_AUDIT) | None | **PASS** | Retain COMPLETE |
| `case_162` | COMPLETE | `evidence_15` (PRE_AUDIT) | None | **PASS** | Retain COMPLETE |
| `case_530` | COMPLETE | `evidence_49` (**POST_AUDIT**) | None | **FAIL** | Demote to INCOMPLETE |
| `case_191` | COMPLETE | `evidence_83` (PRE_AUDIT) | None | **PASS** | Retain COMPLETE |
| `case_393` | COMPLETE | `evidence_69` (PRE_AUDIT) | None | **PASS** | Retain COMPLETE |
| `case_73` | COMPLETE | `evidence_07` (**POST_AUDIT**) | None | **FAIL** | Demote to INCOMPLETE |
| `case_154` | COMPLETE | `evidence_15` (PRE_AUDIT) | None | **PASS** | Retain COMPLETE |

### Demotion List (4 Cases):
* **`case_226`**: Cited post-audit `evidence_22`. Zero pre-audit evidence of unfulfilled deletion; demoted to `INCOMPLETE` with `[]` as documented exception.
* **`case_423`**: Cited post-audit `evidence_40`. Zero pre-audit evidence of unfulfilled deletion; demoted to `INCOMPLETE` with `[]` as documented exception.
* **`case_530`**: Cited post-audit `evidence_49`. Zero pre-audit evidence of unfulfilled deletion; demoted to `INCOMPLETE` with `[]` as documented exception.
* **`case_73`**: Cited post-audit `evidence_07`. Zero pre-audit evidence of unfulfilled deletion; demoted to `INCOMPLETE` with `[]` as documented exception.
