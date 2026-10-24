# NullTrace — Completion Validator Integration-Readiness Audit Report

**Report Version:** 1.0  
**Phase:** Step I.1 Completion Validator Integration-Readiness Audit  
**Date:** 2026-10-25  
**Audit Scope:** `identity.py`, `state_reconstruction.py`, `rule_engine.py`, `resurrection_detector.py`, `planner.py`, `completion_validator.py`, `pipeline.py`, `main.py`, `grader_io.py`, `ops.py`.

---

## 1. Executive Summary

A comprehensive architectural and integrity audit was performed across all NullTrace modules to verify that they can be wired together in Step J without inventing evidence, losing resource coverage, violating dependencies, or prematurely marking cases `COMPLETE`.

- **Audit Accuracy Disclaimer:** In strict compliance with the challenge rules, `dataset/sample_output.csv` was **NEVER** read by production code or used to tune rules. **Audit accuracy remains completely unmeasured.**
- **Can COMPLETE currently be reached safely in the integrated pipeline?** **NO.** In the current standalone baseline pipeline (`pipeline.py`), `COMPLETE` is unreachable because state reconstruction, rule evaluation, resurrection detection, and the completion validator have not yet been wired into the 518-case processing loop. In unit fixtures with simulated evidence, `completion_validator.py` behaves deterministically and fail-closed.
- **Concrete Vulnerability Identified & Fixed:** Prior to this audit, `completion_validator.py` checked only whether an evidence ID was present in the global `known_evidence_ids` set, which would have allowed an arbitrary evidence ID (e.g., a backup file) to be cited for an unrelated user profile. This was patched with `resource_evidence_map` enforcement and a regression test.

---

## 2. Confirmed Integration Paths & Missing Connections

### 2.1 Confirmed Integration Paths
1. **Request Ingestion -> Identity Resolution:** `pipeline.py` and `main.py` successfully ingest `dataset/deletion_requests.csv` and resolve subject identifier clusters via `identity.resolve_all()`.
2. **Cluster -> System Activity Linking:** `resource_link.link_cluster_resources()` successfully queries `system_activity.csv` across all confirmed and historical identifiers in the cluster.
3. **State Reconstruction -> Rule Engine -> Planner (CLI Level):** Demonstrated in `main.py state-eval`, which loads evidence observations, indexes system activity, reconstructs resource states at `audit_at`, evaluates policy rules, detects resurrection risks, and synthesizes 15-operation plans.
4. **Step Sorting & Serialization -> Grader Output:** `ops.sort_steps()`, `ops.validate_steps()`, and `grader_io.serialize_steps()` / `write_output_csv()` form a validated end-to-end serialization path that strictly conforms to the grader specification.

### 2.2 Missing Connections
1. **Full Pipeline Orchestration:** `pipeline.py` still runs the Step E conservative baseline (FINDING steps only, conservative INCOMPLETE). It does not yet invoke `reconstruct_case_states`, `assess_case_policies`, `detect_case_resurrection_risks`, or `validate_case_completion`.
2. **SQL & Document Evidence Observations:** `state_reconstruction.load_all_evidence_observations` currently only ingests `dataset/evidence/records/*.json`. SQL database snapshots, PDF handover documents, screenshots, and logs are not yet converted into structured `EvidenceObservation` objects.
3. **Per-Case Evidence Map Feeding:** `validate_case_completion` requires a `resource_evidence_map` populated from direct observations and activity logs for each case to verify evidence-to-resource consistency.

---

## 3. Evidence-ID Integrity Audit

### 3.1 Validation Semantics
- **Valid Participant-Facing IDs:** Only `file_id` (from `evidence_files.csv`), `activity_id` (from `system_activity.csv`), and `audit_id` (from `user_audit_log.csv`) are valid.
- **Granularity:** `file_id` identifies the containing artifact (e.g., `records/record_001.json`), not internal JSON object lines. `activity_id` identifies the discrete activity row.
- **Finding vs Remediation Semantics:** In `ops.validate_steps()`, findings must cite a non-empty, valid evidence ID. Proposed remediation and future verification steps for `INCOMPLETE` cases must have `evidence_id == ""`. For `COMPLETE` cases, every verification step must cite a non-empty, valid evidence ID.

### 3.2 Evidence Integrity Behavior & Gaps Matrix

| Evidence ID Scenario | Confirmed Behavior | Identified Gap | Synthetic Example | Resolution |
| :--- | :--- | :--- | :--- | :--- |
| **Unknown ID Citation** | Replaced/rejected by `ops.validate_steps` with `ERR_UNKNOWN_EVIDENCE_ID`. | None | `evidence_id = "fake_ev_999"` | Blocked by validator. |
| **Empty ID on Finding** | Rejected by `ops.validate_steps` with `ERR_INCOMPLETE_FINDING_EMPTY_EVIDENCE`. | None | `FINDING` with `evidence_id = ""` | Blocked by planner & validator. |
| **Future Proposed Step with ID** | Rejected by `ops.validate_steps` with `ERR_INCOMPLETE_NON_EMPTY_FUTURE_EVIDENCE`. | None | `REMEDIATION` with `evidence_id = "ev_01"` | Planner strictly emits `""`. |
| **Arbitrary Evidence ID from Inventory** | *Pre-audit:* Accepted if ID existed in global manifest. | **DEFECT:** Did not check if evidence supported that specific resource. | Profile `account_01` citing `evidence_06` (which belongs to a backup restore job). | **FIXED:** Added `resource_evidence_map` checking in `completion_validator.py`. |
| **Post-Audit Evidence Citation** | Filtered by `state_reconstruction.py` using `event_time <= audit_at`. | None | Activity occurring 2 days after `audit_at`. | Blocked from pre-audit state reconstruction. |

---

## 4. Resource Coverage & Identity Completeness Audit

1. **Historical Identifier Propagation:**
   - Confirmed: Identifiers from `user_audit_log.csv` are attached to the subject's `Cluster` as `IdentifierNode(role="historical")`.
   - Confirmed: `resource_link.link_cluster_resources` iterates over all cluster nodes, querying both current and historical identifiers against system activity.
2. **Ambiguous or Conflicting Identities:**
   - Confirmed: `identity.py` records conflicting nodes into `cluster.conflicts`.
   - Confirmed: `completion_validator.py` explicitly inspects `cluster.conflicts` and immediately adds `IncompleteReasonCode.IDENTITY_CONFLICT`, preventing false merges or false completion.
3. **Absence of Resource vs Absence of String:**
   - Confirmed: An absence of a matching record in scanned JSON files does **NOT** infer deletion. A case with zero identified resources triggers `IncompleteReasonCode.NO_RESOURCES_IDENTIFIED` and remains `INCOMPLETE`.
4. **Corpus Inspection Completeness Signal:**
   - **AUDIT FINDING:** **No completeness signal exists in the current pipeline.** The system cannot definitively prove that all database tables, PDFs, and log files across the platform have been exhaustively searched for a given case. This absence of proof reinforces the requirement that cases must fail-closed to `INCOMPLETE` unless corroborated by positive verification evidence.

---

## 5. COMPLETE-Gate Findings

Inspection of `completion_validator.py` confirms that `COMPLETE` is strictly blocked when any of the following apply:
1. `NO_RESOURCES_IDENTIFIED`: 0 identified resources blocks completion.
2. `IDENTITY_CONFLICT`: Any conflict in `cluster.conflicts` blocks completion.
3. `UNKNOWN_RESOURCE_STATE`: Any resource with observed state `UNKNOWN` blocks completion.
4. `UNSATISFIED_POLICY`: Any policy assessment where `policy_satisfied is False` blocks completion.
5. `MISSING_RETAINED_RECORD`: Any required retained record (e.g., `SECURITY_AUDIT_LOG`, `LEGAL_HOLD_RECORD`) not `PRESENT` blocks completion.
6. `TOMBSTONE_DIRECT_PII_EXPOSED`: Any `ACCOUNT_TOMBSTONE` with direct PII remaining (`tombstone_direct_pii_removed is False`) blocks completion.
7. `ACTIVE_DATA_FLOW`: Any flow with status `ACTIVE` blocks completion.
8. `ACTIVE_RESTORE_RISK`: Any restore risk with status `ACTIVE` blocks completion.
9. `UNCORROBORATED_OPERATION_CLAIM`: Any claim marked `UNCORROBORATED_CLAIM` blocks completion.
10. `MISSING_VERIFICATION_EVIDENCE`: Any verification step lacking an evidence ID or citing an arbitrary ID not mapped to the resource blocks completion.

---

## 6. Planner Ordering & Grader Contract Findings

### 6.1 Phase and Operation Order
The grader contract requires strict sorting by:
1. `PHASE`: `FINDING` (rank 0) < `REMEDIATION` (rank 1) < `VERIFICATION` (rank 2).
2. `OPERATION`: Table position in problem statement:
   - Remediation: `DISABLE_DATA_FLOW` (rank 4) < `BLOCK_RESTORE` (rank 5) < `DELETE_RECORD` (rank 6) < `REDACT_RECORD` (rank 7) < `ANONYMIZE_RECORD` (rank 8).
3. `system_id`: Lexicographical ascending.
4. `resource_id`: Lexicographical ascending.

### 6.2 Conflict Analysis: Global Sorting vs Dependency Ordering
- **Inter-Operation Dependencies:** Global operation sorting naturally satisfies dependencies: `DISABLE_DATA_FLOW` and `BLOCK_RESTORE` automatically precede `DELETE_RECORD`, ensuring active recreation paths are halted before record deletion.
- **Intra-Operation Dependencies:** Within the same operation (e.g. downstream replica vs primary database under `DELETE_RECORD`), the grader contract enforces tie-breaking by `system_id` and `resource_id`.
- **Proposed Resolution:** Respect the grader's required `sort_steps` ordering without modification. Attempting topological reordering within the same operation would trigger `ERR_NOT_SORTED` in `ops.validate_steps`.

---

## 7. Tests Executed & Results

- **Full Pytest Suite:** `pytest -v` executed across the entire repository.
- **Results:** **91 passed in 8.03s** (0 failures, 0 errors, 0 warnings).
- **Regression Test Added:**
  - `test_arbitrary_evidence_id_not_supporting_resource_blocks_complete` in `code/tests/test_completion_validator.py`. Verifies that citing an arbitrary inventory evidence ID not mapped to the specific resource is rejected with `MISSING_VERIFICATION_EVIDENCE` and resolves to `INCOMPLETE`.

---

## 8. High-Priority Blockers Before Step J

Before executing Step J (Full Pipeline Integration):
1. **Pipeline Orchestrator (`pipeline.py`):** Replace the conservative baseline loop with the full state reconstruction, policy assessment, resurrection detection, and completion validation flow for all 518 cases.
2. **Per-Case Evidence Map Construction:** Build the `resource_evidence_map` mapping `resource_id -> Set[evidence_id]` during pipeline execution from ingested observations and system activities.
3. **Multi-Modality Evidence Extraction:** Expand observation ingestion to include relational SQL snapshot exports and support documents so that verifiable complete deletions can be supported by evidence.
