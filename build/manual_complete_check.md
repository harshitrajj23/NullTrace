# NullTrace: Manual Verification of Three COMPLETE Rows

**Challenge**: HackerRank Orchestrate (October 2026) — *Ghost Data Still Exists*  
**Step**: Manual Complete Row Audit (`random.Random(42).sample`)  
**Mode**: `DECISION: MODEL_OFF` (Read-only inspection; zero predictions modified)  
**Date**: 2026-10-25T09:28:00+05:30  

---

## 1. Selection Methodology

Using `random.Random(42).sample` over the 162 sorted `COMPLETE` case IDs from `build/nulltrace_final.csv`:
* Total candidate `COMPLETE` cases: **162**
* Selected 3 Case IDs: **`case_111`**, **`case_196`**, **`case_319`**

---

## 2. Case Audit Details

### 2.1 Case `case_111`

#### a. Request & Cluster Identifiers
* **Case ID**: `case_111`
* **Request Email**: `O.ANDERSSON00@GMAIL.COM`
* **Requested At**: `2026-08-08T12:00:00Z`
* **Cutoff (`audit_at`)**: `2026-08-27T12:00:00Z`
* **Cluster Identifiers** (from `user_identities.csv` line 110):
  * `user_id`: `user_109`
  * `name`: `Oskar Andersson`
  * `email`: `o.andersson00@gmail.com`
  * `phone`: `+46 70 171 63 48`
  * `email_hash`: `0825a72aee9a82d2e82c5a48f90ffcabd7a7f75d33d88ae3c69f8ac534f74f08`
* **Audit History** (from `user_audit_log.csv`):
  * No historical changes recorded for `user_109`.

#### b. Full Steps JSON
```json
[
  {
    "step_no": 1,
    "phase": "VERIFICATION",
    "system_id": "security_service",
    "resource_id": "audit_record_8933",
    "operation": "VERIFY_RECORD_PRESENT",
    "state": "PRESENT",
    "evidence_id": "evidence_10"
  }
]
```

#### c. Quoted Evidence Lines
* **Evidence File**: `evidence_10` -> `dataset/evidence/databases/customer_data_read_replica_20260827.sql` (captured at `2026-08-27T12:00:00Z`, matching `audit_at`)
* **Resource**: `audit_record_8933`
* **Quoted Verbatim Lines**:
  * `dataset/evidence/databases/customer_data_read_replica_20260827.sql:28`:
    ```sql
    INSERT INTO "customer_data_primary" VALUES('audit_record_8933','security_service','security_audit_events','{"resource_id":"audit_record_8933","subject_reference":"user_109","event_name":"account_deletion_reviewed","actor_type":"automated_privacy_workflow","integrity_seal":"sha256:00000000000000000000000000000000000000000000000000000000000022e5"}','2026-08-27T12:00:00Z');
    ```
  * `dataset/evidence/databases/customer_data_read_replica_20260827.sql:65`:
    ```sql
    INSERT INTO "customer_data_read_replica" VALUES('audit_record_8933','security_service','security_audit_events','{"resource_id":"audit_record_8933","subject_reference":"user_109","event_name":"account_deletion_reviewed","actor_type":"automated_privacy_workflow","integrity_seal":"sha256:00000000000000000000000000000000000000000000000000000000000022e5"}','2026-08-27T12:00:00Z');
    ```
* **State Confirmation**: Confirms `audit_record_8933` is `PRESENT` in both primary and read-replica tables as a mandatory security audit event (`rule_12`: RETAIN).

#### d. System Activity Review
* Searched `dataset/system_activity.csv` for `audit_record_8933`, `user_109`, and `o.andersson00@gmail.com`:
  * **Result**: **0 rows found**.
  * No activity rows touch the cluster or resource; no active data flows or restore jobs exist.

#### e. Evidence Scan for Active Flows
* Searched `dataset/evidence/` for active sync, import, replication, or restore touching `user_109`, `o.andersson00@gmail.com`, or `audit_record_8933`:
  * **Result**: **0 active flow matches**.

#### f. Verdict
* **Verdict**: **PASS**
* **Reason**: Mandatory retained security audit record `audit_record_8933` is confirmed PRESENT in primary and replica tables at audit cutoff (`evidence_10`: lines 28 and 65) with zero active data flows or restore risks touching the cluster.

---

### 2.2 Case `case_196`

#### a. Request & Cluster Identifiers
* **Case ID**: `case_196`
* **Request Email**: `kim.hyunwoo@gmail.com`
* **Requested At**: `2026-06-19T10:00:00Z`
* **Cutoff (`audit_at`)**: `2026-07-13T10:00:00Z`
* **Cluster Identifiers** (from `user_identities.csv` line 195):
  * `user_id`: `user_194`
  * `name`: `Hyun-woo Kim`
  * `email`: `kim.hyunwoo@gmail.com`
  * `phone`: `+82 10 7737 5984`
  * `email_hash`: `e309b34b240a416dead8071e4c34b64f675d3171bf11cf1a0f6fe80e01130a45`
* **Audit History** (from `user_audit_log.csv`):
  * No historical changes recorded for `user_194`.

#### b. Full Steps JSON
```json
[
  {
    "step_no": 1,
    "phase": "VERIFICATION",
    "system_id": "account_service",
    "resource_id": "account_5599",
    "operation": "VERIFY_RECORD_ABSENT",
    "state": "ABSENT",
    "evidence_id": "evidence_82"
  },
  {
    "step_no": 2,
    "phase": "VERIFICATION",
    "system_id": "security_service",
    "resource_id": "audit_record_6389",
    "operation": "VERIFY_RECORD_PRESENT",
    "state": "PRESENT",
    "evidence_id": "evidence_82"
  }
]
```

#### c. Quoted Evidence Lines
* **Evidence File**: `evidence_82` -> `dataset/evidence/logs/resource_lookup_trace_20260713_093359.log` (captured at `2026-07-13T09:33:59Z`, prior to `audit_at` `2026-07-13T10:00:00Z`)
* **Resources**:
  1. `account_5599` (`ABSENT`):
     * `dataset/evidence/logs/resource_lookup_trace_20260713_093359.log:12`:
       ```text
       2026-07-13T07:20:27Z level=DEBUG service=account_service trace_id=rb-072027-006 event=profile_lookup_started resource_id=account_5599 lookup_key=kim.hyunwoo@gmail.com
       ```
     * `dataset/evidence/logs/resource_lookup_trace_20260713_093359.log:13`:
       ```text
       2026-07-13T07:20:27Z level=INFO service=account_service trace_id=rb-072027-006 event=profile_lookup_completed resource_id=account_5599 rows=0 http_status=404
       ```
     * **State Confirmation**: `rows=0 http_status=404` confirms `account_5599` is `ABSENT`.
  2. `audit_record_6389` (`PRESENT`):
     * `dataset/evidence/logs/resource_lookup_trace_20260713_093359.log:36`:
       ```text
       2026-07-13T08:28:57Z level=DEBUG service=security_service trace_id=rb-082857-018 event=audit_record_read_started resource_id=audit_record_6389 lookup_key=user_194
       ```
     * `dataset/evidence/logs/resource_lookup_trace_20260713_093359.log:37`:
       ```text
       2026-07-13T08:28:57Z level=INFO service=security_service trace_id=rb-082857-018 event=audit_record_read_completed resource_id=audit_record_6389 rows=1 subject_reference=user_194 event_code=IDENTITY_CHANGE_RECORDED retention_until=2034-09-30T23:59:59Z
       ```
     * **State Confirmation**: `rows=1 subject_reference=user_194 event_code=IDENTITY_CHANGE_RECORDED` confirms `audit_record_6389` is `PRESENT` as a mandatory retained security log.

#### d. System Activity Review
* Searched `dataset/system_activity.csv` for `account_5599`, `audit_record_6389`, `user_194`, and `kim.hyunwoo@gmail.com`:
  * `dataset/system_activity.csv:2473`:
    ```csv
    activity_2472,2026-06-22T08:49:27Z,DELETE_RECORD,deletion_worker,account_service,account_5599,SUCCESS,Deletion worker submitted primary profile account_5599 to account_service.
    ```
  * **Flag Check**: Operation is `DELETE_RECORD`, result is `SUCCESS`. No active sync, import, backup, or restore flows exist for this user.

#### e. Evidence Scan for Active Flows
* Searched `dataset/evidence/` for active sync, import, replication, or restore touching `user_194`, `kim.hyunwoo@gmail.com`, `account_5599`, or `audit_record_6389`:
  * **Result**: **0 active flow matches**.

#### f. Verdict
* **Verdict**: **PASS**
* **Reason**: Primary profile `account_5599` is confirmed absent (`http_status=404`, `rows=0`) and mandatory audit record `audit_record_6389` is confirmed present (`rows=1`) via `evidence_82` readback logs, with zero active data flows or restore risks.

---

### 2.3 Case `case_319`

#### a. Request & Cluster Identifiers
* **Case ID**: `case_319`
* **Request Email**: `lars.e5052@outlook.com`
* **Requested At**: `2026-04-17T12:00:00Z`
* **Cutoff (`audit_at`)**: `2026-05-14T12:00:00Z`
* **Cluster Identifiers** (from `user_identities.csv` line 318):
  * `user_id`: `user_317`
  * `name`: `Lars Eriksen`
  * `email`: `lars.e5052@outlook.com`
  * `phone`: `+46 70 103 87 47`
  * `email_hash`: `9f67397f42cb24ae15568abc54cef69600177d30ae259d6360ccb49b82902ec7`
* **Audit History** (from `user_audit_log.csv`):
  * No historical changes recorded for `user_317`.

#### b. Full Steps JSON
```json
[
  {
    "step_no": 1,
    "phase": "VERIFICATION",
    "system_id": "account_service",
    "resource_id": "account_2088",
    "operation": "VERIFY_RECORD_ABSENT",
    "state": "ABSENT",
    "evidence_id": "evidence_30"
  },
  {
    "step_no": 2,
    "phase": "VERIFICATION",
    "system_id": "security_service",
    "resource_id": "audit_record_7337",
    "operation": "VERIFY_RECORD_PRESENT",
    "state": "PRESENT",
    "evidence_id": "evidence_30"
  }
]
```

#### c. Quoted Evidence Lines
* **Evidence File**: `evidence_30` -> `dataset/evidence/logs/service_events_sa_east_20260516.log`
  * **Critical Temporal Finding**: `evidence_30` was captured at `2026-05-16T11:58:25Z`, which is **two days after** `case_319`'s cutoff `audit_at` (`2026-05-14T12:00:00Z`). Under AGENTS.md §6.2 and §6.6, evidence captured after `audit_at` must not be used to decide the case.
* **Quoted Lines from `evidence_30`**:
  * `dataset/evidence/logs/service_events_sa_east_20260516.log:92`:
    ```text
    2026-05-14T11:58:45Z level=INFO service=account_service instance=account-6 pod=account-3740 region=ap-south-1 trace_id=tr-9048368 resource_id=account_2088 event=profile_lookup_completed rows=0 http_status=404 duration_ms=21
    ```
  * `dataset/evidence/logs/service_events_sa_east_20260516.log:97`:
    ```text
    2026-05-14T11:58:51Z level=DEBUG service=security_service instance=security-6 pod=security-2e4a region=us-east-2 trace_id=tr-0719928 resource_id=audit_record_7337 event=audit_record_read_completed integrity_check=passed rows=1
    ```
  * `dataset/evidence/logs/service_events_sa_east_20260516.log:109`:
    ```text
    2026-05-16T11:58:23Z level=DEBUG service=account_service instance=account-1 pod=account-380a region=us-east-2 trace_id=tr-9257826 resource_id=account_2088 event=profile_lookup_completed rows=1 http_status=200 duration_ms=21
    ```
* **State Contradiction**: While line 92 shows a regional lookup in `ap-south-1` returning 404, line 109 shows a lookup in `us-east-2` returning `rows=1 http_status=200` (`PRESENT`). The primary account profile was not deleted globally.

#### d. System Activity Review
* Searched `dataset/system_activity.csv` for `account_2088`, `audit_record_7337`, `user_317`, and `lars.e5052@outlook.com`:
  * `dataset/system_activity.csv:1516`:
    ```csv
    activity_1515,2026-04-20T11:00:49Z,DELETE_RECORD,deletion_worker,account_service,account_2088,FAILED,Deletion worker submitted primary profile account_2088 to account_service.
    ```
  * **Critical Activity Finding**: `activity_1515` explicitly documents that `DELETE_RECORD` for `account_2088` **FAILED**. No subsequent successful deletion activity row exists.

#### e. Evidence Scan for Active Flows
* `account_2088` lookup failed deletion in activity and remains present in `us-east-2` in `evidence_30:109`.

#### f. Verdict
* **Verdict**: **FAIL**
* **Reason**: Cited evidence file `evidence_30` was captured after `audit_at` (2026-05-16 > 2026-05-14), `activity_1515` documents that deletion of `account_2088` failed, and `evidence_30` line 109 confirms `account_2088` remains present in `us-east-2` (`http_status=200`, `rows=1`).

---

## 3. Recommended Demotion

Per user instruction (Rule 4: *"Do not change any prediction. If a case FAILS, do not edit the CSV. List it under 'Recommended demotion' with its reason, and stop for my decision"*):

| Case ID | Current Status | Recommended Status | Failed Rules / Root Cause | Recommended Next Action |
|---|---|---|---|---|
| **`case_319`** | `COMPLETE` | `INCOMPLETE` | 1. **Temporal Cutoff Violation**: `evidence_30` capture time (`2026-05-16T11:58:25Z`) postdates `audit_at` (`2026-05-14T12:00:00Z`).<br>2. **Deletion Failure**: `activity_1515` states `DELETE_RECORD` on `account_2088` `FAILED`.<br>3. **Remaining Record**: `evidence_30:L109` shows `account_2088` present in `us-east-2` (`rows=1, http_status=200`). | Demote `case_319` to `INCOMPLETE` with finding `REPORT_REMAINING_RECORD` citing `activity_1515`, pending user authorization. |

**No predictions in `output.csv` or `build/nulltrace_final.csv` have been modified.**
