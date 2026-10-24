"""code/src/completion_validator.py

Strict Deterministic Completion Validator for HackerRank Orchestrate: Ghost Data Still Exists.

Decides whether a deletion case can legitimately be marked COMPLETE based strictly on evidence:
- Enforces all 10 project contract criteria.
- Fail-closed: any failure, unknown state, conflict, or uncorroborated claim resolves to INCOMPLETE.
- Prohibits false completion from empty resources or absence of findings.
- Generates verification-only steps citing participant-visible evidence IDs for COMPLETE cases.
- Produces machine-readable reason codes for all INCOMPLETE cases.
- Emits steps_json = [] for NOT_APPLICABLE non-deletion requests.
"""

from dataclasses import dataclass, field
from enum import Enum
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Standard library module 'code' conflict resolution
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if "code" in sys.modules and not hasattr(sys.modules["code"], "src"):
    del sys.modules["code"]

try:
    from code.src.identity import Cluster
    from code.src.models import DeletionRequest
    from code.src.ops import Step, sort_steps, validate_steps
    from code.src.planner import CasePlanResult, plan_case
    from code.src.rule_engine import PolicyAssessment
    from code.src.state_reconstruction import ResourceState
    from code.src.resurrection_detector import (
        FlowStatus,
        ResurrectionRiskFinding,
        RiskCategory,
        TimeRelation,
    )
except ImportError:
    from src.identity import Cluster
    from src.models import DeletionRequest
    from src.ops import Step, sort_steps, validate_steps
    from src.planner import CasePlanResult, plan_case
    from src.rule_engine import PolicyAssessment
    from src.state_reconstruction import ResourceState
    from src.resurrection_detector import (
        FlowStatus,
        ResurrectionRiskFinding,
        RiskCategory,
        TimeRelation,
    )

logger = logging.getLogger("nulltrace.completion_validator")


class IncompleteReasonCode(str, Enum):
    """Machine-readable reason codes explaining why a case cannot be COMPLETE."""
    NON_DELETION_REQUEST = "NON_DELETION_REQUEST"
    NO_RESOURCES_IDENTIFIED = "NO_RESOURCES_IDENTIFIED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"
    INCOMPLETE_EVIDENCE_COVERAGE = "INCOMPLETE_EVIDENCE_COVERAGE"
    UNKNOWN_RESOURCE_STATE = "UNKNOWN_RESOURCE_STATE"
    UNSATISFIED_POLICY = "UNSATISFIED_POLICY"
    MISSING_RETAINED_RECORD = "MISSING_RETAINED_RECORD"
    TOMBSTONE_DIRECT_PII_EXPOSED = "TOMBSTONE_DIRECT_PII_EXPOSED"
    ACTIVE_DATA_FLOW = "ACTIVE_DATA_FLOW"
    ACTIVE_RESTORE_RISK = "ACTIVE_RESTORE_RISK"
    UNCORROBORATED_OPERATION_CLAIM = "UNCORROBORATED_OPERATION_CLAIM"
    MISSING_VERIFICATION_EVIDENCE = "MISSING_VERIFICATION_EVIDENCE"
    VALIDATION_CONTRACT_ERROR = "VALIDATION_CONTRACT_ERROR"


@dataclass
class ValidationDecision:
    """Final validated decision for a deletion case."""
    case_id: str
    deletion_status: str                       # COMPLETE, INCOMPLETE, or NOT_APPLICABLE
    steps: List[Step]
    is_complete: bool
    reasons_incomplete: List[str]              # List of IncompleteReasonCode values
    evidence_ids_cited: List[str]
    audit_notes: Dict[str, Any] = field(default_factory=dict)


def build_evidence_backed_verification_steps(
    policy_assessments: Dict[str, PolicyAssessment],
    flow_risks: List[ResurrectionRiskFinding],
    known_evidence_ids: Optional[Set[str]] = None,
    resource_evidence_map: Optional[Dict[str, Set[str]]] = None,
) -> Tuple[List[Step], List[str]]:
    """
    Builds the verification step sequence for a COMPLETE case:
    - Only verification operations.
    - Every step cites a real, verified evidence ID.
    - Enforces evidence-to-resource consistency when resource_evidence_map is provided.
    - Returns (steps, errors).
    """
    steps: List[Step] = []
    errors: List[str] = []

    # 1. Policy-assessed resources
    for rid, assess in sorted(policy_assessments.items()):
        sys_id = assess.system_id
        ev_id = assess.supporting_evidence_ids[0] if assess.supporting_evidence_ids else ""

        if not ev_id:
            errors.append(f"Resource {rid} lacks evidence ID for verification")
            continue
        if known_evidence_ids is not None and ev_id not in known_evidence_ids:
            errors.append(f"Resource {rid} cites unknown evidence ID: {ev_id}")
            continue
        if resource_evidence_map is not None:
            supported = resource_evidence_map.get(rid, set())
            if ev_id not in supported:
                errors.append(f"Resource {rid} cites arbitrary evidence ID {ev_id} not mapped to this resource")
                continue

        if assess.required_action == "DELETE":
            steps.append(
                Step(0, "VERIFICATION", sys_id, rid, "VERIFY_RECORD_ABSENT", "ABSENT", ev_id)
            )
        elif assess.required_action == "RETAIN":
            if assess.data_category == "BACKUP_ARCHIVE":
                steps.append(
                    Step(0, "VERIFICATION", sys_id, rid, "VERIFY_RESTORE_BLOCKED", "BLOCKED", ev_id)
                )
            else:
                steps.append(
                    Step(0, "VERIFICATION", sys_id, rid, "VERIFY_RECORD_PRESENT", "PRESENT", ev_id)
                )
        elif assess.required_action == "REDACT":
            steps.append(
                Step(0, "VERIFICATION", sys_id, rid, "VERIFY_RECORD_REDACTED", "REDACTED", ev_id)
            )
        elif assess.required_action == "ANONYMIZE":
            steps.append(
                Step(0, "VERIFICATION", sys_id, rid, "VERIFY_RECORD_ANONYMIZED", "ANONYMIZED", ev_id)
            )

    # 2. Flow risks (disabled flows / blocked restores)
    for fr in flow_risks:
        rid = fr.implicated_resource
        sys_id = fr.source_system
        ev_id = fr.evidence_ids[0] if fr.evidence_ids else ""

        if not ev_id:
            errors.append(f"Flow {rid} lacks evidence ID for verification")
            continue
        if known_evidence_ids is not None and ev_id not in known_evidence_ids:
            errors.append(f"Flow {rid} cites unknown evidence ID: {ev_id}")
            continue
        if resource_evidence_map is not None:
            supported = resource_evidence_map.get(rid, set()) | resource_evidence_map.get(sys_id, set())
            if ev_id not in supported:
                errors.append(f"Flow {rid} cites arbitrary evidence ID {ev_id} not mapped to this flow")
                continue

        if fr.risk_category == RiskCategory.ACTIVE_DATA_FLOW and fr.flow_status == FlowStatus.DISABLED:
            steps.append(
                Step(0, "VERIFICATION", sys_id, rid, "VERIFY_DATA_FLOW_DISABLED", "DISABLED", ev_id)
            )
        elif fr.risk_category == RiskCategory.RESTORE_RISK and fr.flow_status == FlowStatus.BLOCKED:
            steps.append(
                Step(0, "VERIFICATION", sys_id, rid, "VERIFY_RESTORE_BLOCKED", "BLOCKED", ev_id)
            )

    # Deduplicate steps by (phase, operation, system_id, resource_id)
    seen: Set[Tuple[str, str, str, str]] = set()
    deduped: List[Step] = []
    for s in steps:
        k = (s.phase, s.operation, s.system_id, s.resource_id)
        if k not in seen:
            seen.add(k)
            deduped.append(s)

    sorted_steps = sort_steps(deduped)
    return sorted_steps, errors


def validate_case_completion(
    case_id: str,
    is_non_deletion: bool,
    policy_assessments: Dict[str, PolicyAssessment],
    flow_risks: Optional[List[ResurrectionRiskFinding]] = None,
    identity_cluster: Optional[Cluster] = None,
    known_evidence_ids: Optional[Set[str]] = None,
    resource_evidence_map: Optional[Dict[str, Set[str]]] = None,
) -> ValidationDecision:
    """
    Evaluates whether a deletion case legitimately qualifies for COMPLETE status:
    - 10 strict criteria must pass with evidence.
    - Fail-closed: any failure, unknown state, or uncorroborated claim produces INCOMPLETE.
    - A lack of findings is not evidence of deletion (empty resources -> INCOMPLETE).
    - If non-deletion inquiry -> NOT_APPLICABLE with steps = [].
    - Validates evidence existence and evidence-to-resource consistency.
    - Returns ValidationDecision with machine-readable reasons.
    """
    reasons_incomplete: List[str] = []
    risks = flow_risks or []

    # 1. NOT_APPLICABLE check
    if is_non_deletion:
        return ValidationDecision(
            case_id=case_id,
            deletion_status="NOT_APPLICABLE",
            steps=[],
            is_complete=False,
            reasons_incomplete=[IncompleteReasonCode.NON_DELETION_REQUEST.value],
            evidence_ids_cited=[],
            audit_notes={"reason": "Non-deletion inquiry; no deletion authorized"},
        )

    # 2. Non-empty resource coverage check (lack of findings is NOT evidence of complete deletion)
    if not policy_assessments:
        reasons_incomplete.append(IncompleteReasonCode.NO_RESOURCES_IDENTIFIED.value)

    # 3. Identity cluster conflict check
    if identity_cluster is not None:
        if getattr(identity_cluster, "has_conflicts", False) or bool(getattr(identity_cluster, "conflicts", [])):
            reasons_incomplete.append(IncompleteReasonCode.IDENTITY_CONFLICT.value)

    # 4. Resource state and policy checks
    for rid, assess in sorted(policy_assessments.items()):
        # Check for unknown resource states
        if assess.observed_state == ResourceState.UNKNOWN:
            if IncompleteReasonCode.UNKNOWN_RESOURCE_STATE.value not in reasons_incomplete:
                reasons_incomplete.append(IncompleteReasonCode.UNKNOWN_RESOURCE_STATE.value)

        # Check for policy satisfaction
        if not assess.policy_satisfied:
            if IncompleteReasonCode.UNSATISFIED_POLICY.value not in reasons_incomplete:
                reasons_incomplete.append(IncompleteReasonCode.UNSATISFIED_POLICY.value)

        # Check missing retained records
        if assess.required_action == "RETAIN" and assess.data_category != "BACKUP_ARCHIVE":
            if assess.observed_state != ResourceState.PRESENT:
                if IncompleteReasonCode.MISSING_RETAINED_RECORD.value not in reasons_incomplete:
                    reasons_incomplete.append(IncompleteReasonCode.MISSING_RETAINED_RECORD.value)

        # Check tombstone direct PII exposure
        if assess.is_tombstone:
            if assess.tombstone_direct_pii_removed is False or assess.observed_state == ResourceState.PRESENT:
                if IncompleteReasonCode.TOMBSTONE_DIRECT_PII_EXPOSED.value not in reasons_incomplete:
                    reasons_incomplete.append(IncompleteReasonCode.TOMBSTONE_DIRECT_PII_EXPOSED.value)

        # Check supporting evidence IDs
        if not assess.supporting_evidence_ids or not assess.supporting_evidence_ids[0]:
            if IncompleteReasonCode.MISSING_VERIFICATION_EVIDENCE.value not in reasons_incomplete:
                reasons_incomplete.append(IncompleteReasonCode.MISSING_VERIFICATION_EVIDENCE.value)
        else:
            if known_evidence_ids is not None:
                for evid in assess.supporting_evidence_ids:
                    if evid not in known_evidence_ids:
                        if IncompleteReasonCode.MISSING_VERIFICATION_EVIDENCE.value not in reasons_incomplete:
                            reasons_incomplete.append(IncompleteReasonCode.MISSING_VERIFICATION_EVIDENCE.value)
            if resource_evidence_map is not None:
                supported_evs = resource_evidence_map.get(rid, set())
                for evid in assess.supporting_evidence_ids:
                    if evid not in supported_evs:
                        if IncompleteReasonCode.MISSING_VERIFICATION_EVIDENCE.value not in reasons_incomplete:
                            reasons_incomplete.append(IncompleteReasonCode.MISSING_VERIFICATION_EVIDENCE.value)

    # 5. Flow and restore risk checks
    for fr in risks:
        if fr.confidence == "UNCORROBORATED_CLAIM":
            if IncompleteReasonCode.UNCORROBORATED_OPERATION_CLAIM.value not in reasons_incomplete:
                reasons_incomplete.append(IncompleteReasonCode.UNCORROBORATED_OPERATION_CLAIM.value)

        if fr.risk_category == RiskCategory.ACTIVE_DATA_FLOW and fr.flow_status == FlowStatus.ACTIVE:
            if IncompleteReasonCode.ACTIVE_DATA_FLOW.value not in reasons_incomplete:
                reasons_incomplete.append(IncompleteReasonCode.ACTIVE_DATA_FLOW.value)

        if fr.risk_category == RiskCategory.RESTORE_RISK and fr.flow_status == FlowStatus.ACTIVE:
            if IncompleteReasonCode.ACTIVE_RESTORE_RISK.value not in reasons_incomplete:
                reasons_incomplete.append(IncompleteReasonCode.ACTIVE_RESTORE_RISK.value)

        if fr.risk_category == RiskCategory.REPOPULATED_DOWNSTREAM:
            if IncompleteReasonCode.ACTIVE_DATA_FLOW.value not in reasons_incomplete:
                reasons_incomplete.append(IncompleteReasonCode.ACTIVE_DATA_FLOW.value)

        if resource_evidence_map is not None and fr.evidence_ids:
            supported_evs = resource_evidence_map.get(fr.implicated_resource, set()) | resource_evidence_map.get(fr.source_system, set())
            for evid in fr.evidence_ids:
                if evid not in supported_evs:
                    if IncompleteReasonCode.MISSING_VERIFICATION_EVIDENCE.value not in reasons_incomplete:
                        reasons_incomplete.append(IncompleteReasonCode.MISSING_VERIFICATION_EVIDENCE.value)

    # 6. Evaluation of Completion
    if not reasons_incomplete:
        # All 10 criteria pass! Attempt to build evidence-backed verification steps
        verif_steps, verif_errors = build_evidence_backed_verification_steps(
            policy_assessments=policy_assessments,
            flow_risks=risks,
            known_evidence_ids=known_evidence_ids,
            resource_evidence_map=resource_evidence_map,
        )

        if verif_errors or not verif_steps:
            reasons_incomplete.append(IncompleteReasonCode.MISSING_VERIFICATION_EVIDENCE.value)
        else:
            # Validate generated verification-only steps against grader contract
            contract_errors = validate_steps(verif_steps, "COMPLETE", known_evidence_ids)
            if contract_errors:
                reasons_incomplete.append(IncompleteReasonCode.VALIDATION_CONTRACT_ERROR.value)
            else:
                # Legitimate COMPLETE case!
                cited_ev = [s.evidence_id for s in verif_steps if s.evidence_id]
                return ValidationDecision(
                    case_id=case_id,
                    deletion_status="COMPLETE",
                    steps=verif_steps,
                    is_complete=True,
                    reasons_incomplete=[],
                    evidence_ids_cited=cited_ev,
                    audit_notes={"verified_resources_count": len(verif_steps)},
                )

    # Case remains INCOMPLETE: fallback to planner's proposed steps
    planned = plan_case(
        case_id=case_id,
        is_non_deletion=False,
        policy_assessments=policy_assessments,
        flow_risks=risks,
        known_evidence_ids=known_evidence_ids,
    )

    cited_ev = [s.evidence_id for s in planned.steps if s.evidence_id]
    return ValidationDecision(
        case_id=case_id,
        deletion_status="INCOMPLETE",
        steps=planned.steps,
        is_complete=False,
        reasons_incomplete=reasons_incomplete,
        evidence_ids_cited=cited_ev,
        audit_notes={"gaps": planned.unresolved_gaps},
    )
