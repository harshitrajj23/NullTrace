# NullTrace: Team Synthetic Test Cases

**Challenge**: HackerRank Orchestrate (October 2026) — *Ghost Data Still Exists*  
**Document**: Synthetic Fixtures and Verification Suite  
**Evaluation Mode**: `MODEL_OFF` (Deterministic execution)  

---

## 1. Overview and Objectives

Per problem statement requirements (§6.8), the team authored three synthetic evaluation test fixtures completely separate from the competition dataset. These test cases probe edge cases in temporal boundaries, active data flows, and conflicting evidence signals:

1. **Synthetic Case 1 (`synth_case_01`)**: A verified `COMPLETE` deletion where all records are confirmed pre-audit and verified.
2. **Synthetic Case 2 (`synth_case_02`)**: An `INCOMPLETE` case with an unlinked active data flow touching a cluster resource.
3. **Synthetic Case 3 (`synth_case_03`)**: A contradictory evidence case where a pre-audit HTTP 404 lookup contradicts a recorded failed deletion (`activity_id`).

---

## 2. Test Fixtures

### Fixture 1: Pre-Audit Verified COMPLETE Case (`synth_case_01`)

* **Scenario**: Subject requests deletion. Account profile was deleted before cutoff, and mandatory security audit record is present in a pre-audit SQL snapshot. No active flows or restore jobs touch the user.
* **Input Fixture**:
  * Request: `synth_case_01,alice.synth@example.com,2026-05-01T10:00:00Z,COMPLETE,2026-05-03T10:00:00Z,2026-05-15T10:00:00Z,"Please delete my account and personal data."`
  * Identity: `synth_user_01`, `Alice Synthetic`, `alice.synth@example.com`, `+1 555 0101`
  * Evidence: `synth_ev_01` (SQL snapshot, captured `2026-05-10T08:00:00Z` <= audit cutoff `2026-05-15T10:00:00Z`), containing `audit_record_9001` with `subject_reference=synth_user_01` (rule_12: RETAIN).
  * System Activity: `DELETE_RECORD` on `account_9001` with reported_result `SUCCESS` at `2026-05-02T11:00:00Z`.
* **Expected Output**:
  * `deletion_status`: `COMPLETE`
  * `steps_json`:
    ```json
    [
      {
        "step_no": 1,
        "phase": "VERIFICATION",
        "system_id": "security_service",
        "resource_id": "audit_record_9001",
        "operation": "VERIFY_RECORD_PRESENT",
        "state": "PRESENT",
        "evidence_id": "synth_ev_01"
      }
    ]
    ```
* **Actual Pipeline Output**:
  * `deletion_status`: `COMPLETE`
  * `steps_json`: Exactly matches expected verification step with consecutive numbering.
* **Result**: **PASS**

---

### Fixture 2: Active Data Flow Unlinked to Subject (`synth_case_02`)

* **Scenario**: Subject `synth_user_02` requested deletion. Direct profile `account_9002` was deleted, but an active data synchronization connector (`data_flow_9002`) operates between `account_service` and `analytics_platform` replicating `account_9002`. The connector event in system activity does not state `synth_user_02` in its subject column, but references the cluster resource `account_9002`.
* **Input Fixture**:
  * Request: `synth_case_02,bob.synth@example.com,2026-06-01T12:00:00Z,COMPLETE,2026-06-04T12:00:00Z,2026-06-20T12:00:00Z,"Kindly delete my personal details and account."`
  * Identity: `synth_user_02`, `Bob Synthetic`, `bob.synth@example.com`, `+1 555 0102`
  * Activity: `DATA_SYNC` on `data_flow_9002` at `2026-06-15T09:00:00Z` with status `ACTIVE`, referencing target resource `account_9002`.
* **Expected Output**:
  * `deletion_status`: `INCOMPLETE`
  * `steps_json`:
    ```json
    [
      {
        "step_no": 1,
        "phase": "FINDING",
        "system_id": "integration_service",
        "resource_id": "data_flow_9002",
        "operation": "REPORT_ACTIVE_DATA_FLOW",
        "state": "ACTIVE",
        "evidence_id": "activity_9002"
      },
      {
        "step_no": 2,
        "phase": "REMEDIATION",
        "system_id": "integration_service",
        "resource_id": "data_flow_9002",
        "operation": "DISABLE_DATA_FLOW",
        "state": "DISABLED",
        "evidence_id": ""
      },
      {
        "step_no": 3,
        "phase": "VERIFICATION",
        "system_id": "integration_service",
        "resource_id": "data_flow_9002",
        "operation": "VERIFY_DATA_FLOW_DISABLED",
        "state": "DISABLED",
        "evidence_id": ""
      }
    ]
    ```
* **Actual Pipeline Output**:
  * `deletion_status`: `INCOMPLETE`
  * `steps_json`: Emits finding for `data_flow_9002` followed by ordered remediation and verification.
* **Result**: **PASS**

---

### Fixture 3: Contradictory Evidence (Pre-Audit 404 vs Failed Deletion Activity) (`synth_case_03`)

* **Scenario**: Modelled after the real defect uncovered in `case_319`. A pre-audit lookup log reports HTTP 404 (`profile: null`) for `account_9003`, but an earlier pre-audit system activity row records `DELETE_RECORD` on `account_9003` with reported_result `FAILED`.
* **Input Fixture**:
  * Request: `synth_case_03,charlie.synth@example.com,2026-04-10T08:00:00Z,COMPLETE,2026-04-15T08:00:00Z,2026-05-01T08:00:00Z,"Please delete all my data."`
  * Identity: `synth_user_03`, `Charlie Synthetic`, `charlie.synth@example.com`
  * Pre-Audit Activity: `activity_9003` at `2026-04-12T09:00:00Z`, `DELETE_RECORD`, `account_9003`, reported_result `FAILED`.
  * Pre-Audit Evidence: `synth_ev_03` log line showing `profile_lookup_completed resource_id=account_9003 http_status=404` at `2026-04-28T11:00:00Z`.
* **Expected Output**:
  * `deletion_status`: `INCOMPLETE`
  * Rationale: The system must fail-closed. When deletion failed and subsequent absence lookups might reflect regional replica drift or lookup caching, the deletion cannot be established as COMPLETE.
  * Steps: Emits FINDING citing `activity_9003`, ordered REMEDIATION `DELETE_RECORD`, and future VERIFICATION `VERIFY_RECORD_ABSENT`.
* **Actual Pipeline Output**:
  * `deletion_status`: `INCOMPLETE`
  * `steps_json`: Emitted 3 steps: `FINDING` (`REPORT_REMAINING_RECORD`, `activity_9003`), `REMEDIATION` (`DELETE_RECORD`), `VERIFICATION` (`VERIFY_RECORD_ABSENT`).
* **Result**: **PASS**

---

## 3. Failure Found During Authoring & Resolution

* **Failure Found**: When authoring `synth_case_03`, an earlier version of the pipeline's completion checker treated any pre-audit 404 as sufficient proof of deletion, ignoring conflicting `FAILED` deletion operations in `system_activity.csv`. This caused the case to falsely pass as `COMPLETE` without verifying why deletion failed.
* **Resolution**: The pipeline was updated to check all pre-audit `DELETE_RECORD` activities. If any deletion operation on a cluster resource is recorded as `FAILED`, the resource state is marked `UNKNOWN` / `CONTRADICTORY`, immediately blocking `COMPLETE` promotion and routing the case to `INCOMPLETE` with a finding citing the failed activity.
