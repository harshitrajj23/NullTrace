# NullTrace — Integration Contract

**Document Version:** 1.0  
**Phase:** Step I.1 Integration-Readiness Audit  
**Date:** 2026-10-25  

This document details the interface contracts, type signatures, data-flow dependencies, and integration status of all core modules in NullTrace.

---

## 1. Module Call Graph & Data Flow

```mermaid
flowchart TD
    DR[dataset/deletion_requests.csv] --> Pipe[pipeline.py]
    UI[dataset/user_identities.csv] --> Ident[identity.py: resolve_all]
    UAL[dataset/user_audit_log.csv] --> Ident
    
    Ident --> ClusterMap[Dict[str, Cluster]]
    ClusterMap --> RL[resource_link.py / record_cooccurrence]
    SA[dataset/system_activity.csv] --> RL
    
    RL --> ResList[Linked Resource IDs]
    EF[dataset/evidence/records/*.json] --> SR[state_reconstruction.py]
    SA --> SR
    ResList --> SR
    
    SR --> StateMap[Dict[str, ReconstructedState]]
    StateMap --> RE[rule_engine.py: assess_case_policies]
    Rules[dataset/deletion_rules.csv] --> RE
    
    RE --> AssessMap[Dict[str, PolicyAssessment]]
    SA --> RD[resurrection_detector.py]
    SR --> RD
    ResList --> RD
    
    RD --> FlowRisks[List[ResurrectionRiskFinding]]
    
    AssessMap --> Planner[planner.py: plan_case]
    FlowRisks --> Planner
    
    Planner --> PlanResult[CasePlanResult: steps]
    
    AssessMap --> CV[completion_validator.py: validate_case_completion]
    FlowRisks --> CV
    ClusterMap --> CV
    PlanResult --> CV
    
    CV --> Decision[ValidationDecision: status, steps]
    Decision --> GIO[grader_io.py: serialize_steps]
    GIO --> OutCSV[output.csv]
```

---

## 2. Interface Specifications & Signatures

### 2.1 Identity Resolution (`code/src/identity.py`)
- **Key Function:**
  ```python
  def resolve_cluster(request: DeletionRequest, dataset: Dataset, index: Optional[IdentityIndex] = None) -> Cluster
  def resolve_all(dataset: Dataset) -> Dict[str, Cluster]
  ```
- **Inputs:** `DeletionRequest` (case_id, email, requested_at, etc.), `Dataset` (user_identities, user_audit_log).
- **Returned Outputs:** `Cluster` containing:
  - `case_id: str`
  - `nodes: Dict[Tuple[str, str], IdentifierNode]` (normalized emails, phones, user_ids, email_hashes with roles `current` or `historical`)
  - `links: List[Link]` (provenance, confidence strength `CONFIRMED`, `PROBABLE`, `UNRESOLVED`)
  - `conflicts: List[Conflict]` (detected contradictory or multi-subject collisions)
- **Role in Pipeline:** Resolves subject identity spanning current and historical identifiers before searching activity logs and evidence.

---

### 2.2 State Reconstruction (`code/src/state_reconstruction.py`)
- **Key Functions:**
  ```python
  def load_all_evidence_observations(data_dir: str = "./dataset") -> Dict[str, List[EvidenceObservation]]
  def index_system_activity_by_resource(activities: List[SystemActivity]) -> Dict[str, List[SystemActivity]]
  def reconstruct_case_states(
      case_id: str,
      audit_at: datetime,
      resource_ids: List[str],
      evidence_obs_index: Dict[str, List[EvidenceObservation]],
      activity_index: Dict[str, List[SystemActivity]],
  ) -> Dict[str, ReconstructedState]
  ```
- **Inputs:** `audit_at` cutoff timestamp, list of linked `resource_ids`, direct evidence observations, activity index.
- **Returned Outputs:** `Dict[str, ReconstructedState]`:
  - `state: ResourceState` (PRESENT, ABSENT, REDACTED, ANONYMIZED, ACTIVE, DISABLED, BLOCKED, UNKNOWN)
  - `provenance_evidence_id: str` (participant-visible file_id or activity_id)
  - `is_direct: bool`, `has_conflict: bool`, `is_uncorroborated_claim: bool`, `post_audit_events_count: int`
- **Role in Pipeline:** Reconstructs the factual operational state at or before `audit_at`. Enforces that post-audit events cannot prove pre-audit state and that reported success without evidence remains `UNKNOWN`.

---

### 2.3 Rule Engine (`code/src/rule_engine.py`)
- **Key Functions:**
  ```python
  def assess_case_policies(
      case_id: str,
      states: Dict[str, ReconstructedState],
      rules: List[DeletionRule],
      system_mapping: Optional[Dict[str, str]] = None,
  ) -> Dict[str, PolicyAssessment]
  ```
- **Inputs:** Reconstructed states map, loaded `deletion_rules.csv`.
- **Returned Outputs:** `Dict[str, PolicyAssessment]`:
  - `applicable_rule_id: Optional[str]`, `required_action: str` (DELETE, REDACT, RETAIN, ANONYMIZE)
  - `observed_state: ResourceState`, `policy_satisfied: bool`
  - `supporting_evidence_ids: List[str]`, `is_tombstone: bool`, `tombstone_direct_pii_removed: Optional[bool]`
- **Role in Pipeline:** Deterministically evaluates whether each resource's reconstructed state satisfies policy rules. Tracks explicit gaps for missing/ambiguous rules or unobserved states.

---

### 2.4 Resurrection & Restore-Risk Detector (`code/src/resurrection_detector.py`)
- **Key Functions:**
  ```python
  def build_temporal_flow_graph(
      system_activities: List[SystemActivity],
      evidence_observations: List[EvidenceObservation],
  ) -> TemporalFlowGraph
  def detect_case_resurrection_risks(
      case_id: str,
      audit_at: datetime,
      case_resource_ids: Set[str],
      graph: TemporalFlowGraph,
  ) -> List[ResurrectionRiskFinding]
  ```
- **Inputs:** Global `system_activity`, evidence observations, case resource IDs, case `audit_at`.
- **Returned Outputs:** `List[ResurrectionRiskFinding]`:
  - `risk_category: RiskCategory` (ACTIVE_DATA_FLOW, RESTORE_RISK, REPOPULATED_DOWNSTREAM)
  - `flow_status: FlowStatus` (ACTIVE, DISABLED, BLOCKED, etc.)
  - `evidence_ids: List[str]`, `confidence: str`, `time_relation: TimeRelation`
- **Role in Pipeline:** Traverses temporal propagation pathways to find active synchronization flows and restorable backup archives that could recreate deleted data.

---

### 2.5 Remediation Planner (`code/src/planner.py`)
- **Key Function:**
  ```python
  def plan_case(
      case_id: str,
      is_non_deletion: bool,
      policy_assessments: Dict[str, PolicyAssessment],
      flow_risks: Optional[List[ResurrectionRiskFinding]] = None,
      known_evidence_ids: Optional[Set[str]] = None,
  ) -> CasePlanResult
  ```
- **Inputs:** Policy assessments, resurrection findings, known evidence IDs.
- **Returned Outputs:** `CasePlanResult`:
  - `deletion_status: str` (always `INCOMPLETE` or `NOT_APPLICABLE` in planner)
  - `steps: List[Step]` (strictly ordered, deduplicated, consecutively numbered)
  - `has_policy_violations: bool`, `has_active_flows_or_restores: bool`, `unresolved_gaps: List[str]`
- **Role in Pipeline:** Synthesizes valid 15-operation sequences: findings cite real evidence; proposed remediation and future verification carry empty evidence IDs. Prioritizes data flows and restore risks ahead of record deletions.

---

### 2.6 Completion Validator (`code/src/completion_validator.py`)
- **Key Function:**
  ```python
  def validate_case_completion(
      case_id: str,
      is_non_deletion: bool,
      policy_assessments: Dict[str, PolicyAssessment],
      flow_risks: Optional[List[ResurrectionRiskFinding]] = None,
      identity_cluster: Optional[Cluster] = None,
      known_evidence_ids: Optional[Set[str]] = None,
      resource_evidence_map: Optional[Dict[str, Set[str]]] = None,
  ) -> ValidationDecision
  ```
- **Inputs:** Policy assessments, flow risks, identity cluster, evidence inventories, resource-to-evidence mapping.
- **Returned Outputs:** `ValidationDecision`:
  - `deletion_status: str` (`COMPLETE`, `INCOMPLETE`, or `NOT_APPLICABLE`)
  - `steps: List[Step]` (verification-only for COMPLETE; planner steps for INCOMPLETE; `[]` for NOT_APPLICABLE)
  - `is_complete: bool`, `reasons_incomplete: List[str]` (machine-readable `IncompleteReasonCode`)
  - `evidence_ids_cited: List[str]`, `audit_notes: Dict[str, Any]`
- **Role in Pipeline:** Deterministic gatekeeper enforcing all 10 project contract criteria. Fail-closes all uncertainty, conflicts, and gaps to INCOMPLETE.

---

### 2.7 Pipeline, Main CLI, & Grader I/O (`code/src/pipeline.py`, `code/main.py`, `code/src/grader_io.py`)
- **`grader_io.py`**:
  - `serialize_steps(steps: List[Step]) -> str`: Encodes steps into compact JSON array matching exact key order `["step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id"]`.
  - `write_output_csv(rows: List[Dict[str, Any]], path: str)`: Formats and writes `case_id,deletion_status,steps_json` sorted strictly by `case_id` ascending.
- **`ops.py`**:
  - `sort_steps(steps: List[Step]) -> List[Step]`: Sorts by `(phase_rank, operation_rank, system_id, resource_id)` and consecutively numbers `step_no` from 1.
  - `validate_steps(steps: List[Step], status: str, known_evidence_ids: Optional[Set[str]]) -> List[str]`: Full contract validation.
- **`pipeline.py` & `main.py`**:
  - `run_baseline_pipeline`: Currently runs the conservative Step E baseline (FINDING steps only, conservative INCOMPLETE).
  - `main.py`: Houses CLI subcommands: `inspect`, `identity`, `baseline`, and `state-eval`.

---

## 3. Integration Gap Analysis

| Pipeline Stage | Implementation Status | Integration Status | Gap / Missing Connection |
| :--- | :--- | :--- | :--- |
| **Request Ingestion & Non-Deletion Filter** | Fully implemented (`is_non_deletion_inquiry`) | Integrated in `pipeline.py` | None |
| **Identity Resolution** | Fully implemented (`identity.py`) | Integrated in `pipeline.py` | Clusters resolved; conflicts checked in validator |
| **Resource Linking** | Implemented (`resource_link.py` & `record_cooccurrence.csv`) | Partially integrated in `pipeline.py` | Only links activity & JSON records; does not yet link SQL join paths or document evidence |
| **State Reconstruction** | Fully implemented (`state_reconstruction.py`) | Integrated in `main.py state-eval` | Not yet wired into `pipeline.py` for 518 cases |
| **Policy Assessment** | Fully implemented (`rule_engine.py`) | Integrated in `main.py state-eval` | Not yet wired into `pipeline.py` for 518 cases |
| **Resurrection Detection** | Fully implemented (`resurrection_detector.py`) | Integrated in `main.py state-eval` | Not yet wired into `pipeline.py` for 518 cases |
| **Remediation Planner** | Fully implemented (`planner.py`) | Integrated in `main.py state-eval` | Not yet wired into `pipeline.py` for 518 cases |
| **Strict Completion Validator** | Fully implemented (`completion_validator.py`) | Unit tested (14 tests pass) | Not yet wired into `pipeline.py` or `main.py` |
| **Final Output Generation** | Fully implemented (`grader_io.py`) | Integrated in `pipeline.py` | Writes to `build/nulltrace_baseline.csv`; Step J will target submission pipeline |

---

## 4. Summary of Wiring Requirements for Step J
To safely assemble the full end-to-end pipeline in Step J:
1. For each of the 518 requests:
   - Run `is_non_deletion_inquiry` -> if True, return `NOT_APPLICABLE` with `[]`.
   - Retrieve subject `Cluster` from `resolve_all(dataset)`.
   - Collect candidate resource IDs from all available linkers.
   - Run `reconstruct_case_states(case_id, audit_at, rids, evidence_obs, activity_idx)`.
   - Run `assess_case_policies(case_id, states, deletion_rules)`.
   - Run `detect_case_resurrection_risks(case_id, audit_at, rids, flow_graph)`.
   - Pass all structures into `validate_case_completion(...)`.
   - Pass result steps to `validate_steps` and `serialize_steps`.
2. Sort rows by `case_id` ascending and write to destination using `write_output_csv`.
