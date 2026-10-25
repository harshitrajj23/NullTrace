"""code/src/planner.py

Evidence-Grounded Remediation Planner for HackerRank Orchestrate: Ghost Data Still Exists.

Converts the deterministic outputs of identity resolution, state reconstruction,
the rule engine, and the resurrection detector into valid, ordered step sequences:
- Strictly enforces the 15 allowed operations and states from the project contract.
- Orders phases: FINDING -> REMEDIATION -> VERIFICATION.
- Sorts within phases by exact specification operation rank, then system_id, then resource_id ascending.
- Renumbers step_no consecutively starting from 1.
- For INCOMPLETE:
  - Findings cite real participant-visible evidence IDs.
  - Proposed remediation and future verification steps carry evidence_id: "".
  - Uncorroborated claims do not emit concrete findings.
  - Mitigations for active data flows and restore risks precede affected record actions.
- For NOT_APPLICABLE: emits steps_json = [].
- Never emits COMPLETE in this step (deferred to validator).
"""

from dataclasses import dataclass, field
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
    from code.src.models import DeletionRequest, DeletionRule
    from code.src.ops import Step, sort_steps, validate_steps
    from code.src.rule_engine import PolicyAssessment, get_canonical_system_id
    from code.src.state_reconstruction import ReconstructedState, ResourceState
    from code.src.resurrection_detector import (
        ResurrectionRiskFinding,
        RiskCategory,
        TimeRelation,
    )
except ImportError:
    from src.models import DeletionRequest, DeletionRule
    from src.ops import Step, sort_steps, validate_steps
    from src.rule_engine import PolicyAssessment, get_canonical_system_id
    from src.state_reconstruction import ReconstructedState, ResourceState
    from src.resurrection_detector import (
        ResurrectionRiskFinding,
        RiskCategory,
        TimeRelation,
    )

logger = logging.getLogger("nulltrace.planner")


@dataclass
class CasePlanResult:
    """Complete planned outcome for a deletion case."""
    case_id: str
    deletion_status: str
    steps: List[Step]
    unresolved_gaps: List[str] = field(default_factory=list)
    has_policy_violations: bool = False
    has_active_flows_or_restores: bool = False


def build_candidate_verification_steps(
    policy_assessments: Dict[str, PolicyAssessment],
    flow_risks: List[ResurrectionRiskFinding],
) -> List[Step]:
    """
    Builds a candidate verification-only step list proving compliant state at audit_at.
    Cites real evidence IDs for satisfied resources. For use by future completion validator.
    """
    candidate_steps: List[Step] = []

    for rid, assess in sorted(policy_assessments.items()):
        if not assess.policy_satisfied or assess.observed_state == ResourceState.UNKNOWN:
            continue
        ev_id = assess.supporting_evidence_ids[0] if assess.supporting_evidence_ids else ""
        if not ev_id:
            continue

        sys_id = assess.system_id

        if assess.required_action == "DELETE" and assess.observed_state == ResourceState.ABSENT:
            candidate_steps.append(
                Step(0, "VERIFICATION", sys_id, rid, "VERIFY_RECORD_ABSENT", "ABSENT", ev_id)
            )
        elif assess.required_action == "RETAIN":
            if assess.data_category == "BACKUP_ARCHIVE" and assess.observed_state == ResourceState.BLOCKED:
                candidate_steps.append(
                    Step(0, "VERIFICATION", sys_id, rid, "VERIFY_RESTORE_BLOCKED", "BLOCKED", ev_id)
                )
            elif assess.observed_state == ResourceState.PRESENT:
                candidate_steps.append(
                    Step(0, "VERIFICATION", sys_id, rid, "VERIFY_RECORD_PRESENT", "PRESENT", ev_id)
                )
        elif assess.required_action == "REDACT" and assess.observed_state == ResourceState.REDACTED:
            candidate_steps.append(
                Step(0, "VERIFICATION", sys_id, rid, "VERIFY_RECORD_REDACTED", "REDACTED", ev_id)
            )
        elif assess.required_action == "ANONYMIZE" and assess.observed_state == ResourceState.ANONYMIZED:
            candidate_steps.append(
                Step(0, "VERIFICATION", sys_id, rid, "VERIFY_RECORD_ANONYMIZED", "ANONYMIZED", ev_id)
            )

    return sort_steps(candidate_steps)


def plan_case(
    case_id: str,
    is_non_deletion: bool,
    policy_assessments: Dict[str, PolicyAssessment],
    flow_risks: Optional[List[ResurrectionRiskFinding]] = None,
    known_evidence_ids: Optional[Set[str]] = None,
) -> CasePlanResult:
    """
    Plans an ordered, evidence-grounded remediation sequence for a single request:
    - If non-deletion inquiry: returns NOT_APPLICABLE with steps = [].
    - For deletion requests: conservatively returns INCOMPLETE.
    - Emits FINDING steps citing participant-visible evidence IDs.
    - Emits REMEDIATION and future VERIFICATION steps with evidence_id: "".
    - Mitigations for active data flows and restore risks precede record treatments.
    - Preserves retained records (never generates destructive actions for RETAIN policy).
    - Excludes uncorroborated claims from concrete findings.
    - Validates all generated steps against the ops validator.
    """
    # 1. NOT_APPLICABLE Rule
    if is_non_deletion:
        return CasePlanResult(
            case_id=case_id,
            deletion_status="NOT_APPLICABLE",
            steps=[],
            unresolved_gaps=[],
            has_policy_violations=False,
            has_active_flows_or_restores=False,
        )

    # 2. Deletion requests: evaluate findings, remediation, and verification
    raw_findings: List[Step] = []
    raw_remediations: List[Step] = []
    raw_verifications: List[Step] = []
    unresolved_gaps: List[str] = []

    has_policy_violations = False
    has_active_flows_or_restores = False

    risks = flow_risks or []

    # A. Active Data Flows and Restore Risks
    for fr in risks:
        # Ignore uncorroborated claims and post-audit events for pre-audit findings
        if fr.confidence == "UNCORROBORATED_CLAIM":
            unresolved_gaps.append(f"Excluded uncorroborated claim for {fr.implicated_resource}: {fr.reason}")
            continue
        if fr.is_post_audit_resurrection:
            unresolved_gaps.append(f"Noted post-audit recreation for {fr.implicated_resource}: {fr.reason}")
            continue

        rid = fr.implicated_resource
        sys_id = fr.source_system
        if not sys_id or sys_id in ("deletion_worker", "unknown_system", "system_worker", "audit_log", "activity_log"):
            sys_id = get_canonical_system_id(rid)
        ev_id = fr.evidence_ids[0] if fr.evidence_ids else ""

        if not ev_id:
            unresolved_gaps.append(f"Active risk for {rid} lacked evidence_id; excluded finding")
            continue

        if fr.risk_category == RiskCategory.ACTIVE_DATA_FLOW:
            has_active_flows_or_restores = True
            raw_findings.append(
                Step(0, "FINDING", sys_id, rid, "REPORT_ACTIVE_DATA_FLOW", "ACTIVE", ev_id)
            )
            raw_remediations.append(
                Step(0, "REMEDIATION", sys_id, rid, "DISABLE_DATA_FLOW", "DISABLED", "")
            )
            raw_verifications.append(
                Step(0, "VERIFICATION", sys_id, rid, "VERIFY_DATA_FLOW_DISABLED", "DISABLED", "")
            )

        elif fr.risk_category == RiskCategory.RESTORE_RISK:
            has_active_flows_or_restores = True
            raw_findings.append(
                Step(0, "FINDING", sys_id, rid, "REPORT_RESTORE_RISK", "ACTIVE", ev_id)
            )
            raw_remediations.append(
                Step(0, "REMEDIATION", sys_id, rid, "BLOCK_RESTORE", "BLOCKED", "")
            )
            raw_verifications.append(
                Step(0, "VERIFICATION", sys_id, rid, "VERIFY_RESTORE_BLOCKED", "BLOCKED", "")
            )

    # B. Record Policy Violations
    for rid, assess in sorted(policy_assessments.items()):
        if assess.observed_state == ResourceState.UNKNOWN:
            unresolved_gaps.append(f"Resource {rid} observed state is UNKNOWN; concrete finding not emitted")
            continue

        # If policy is already satisfied, no finding or remediation is needed
        if assess.policy_satisfied:
            continue

        has_policy_violations = True
        sys_id = assess.system_id
        ev_id = assess.supporting_evidence_ids[0] if assess.supporting_evidence_ids else ""

        if not ev_id:
            unresolved_gaps.append(f"Policy violation for {rid} lacked evidence ID; concrete finding not emitted")
            continue

        # 1. DELETE policy violation (record still PRESENT)
        if assess.required_action == "DELETE":
            raw_findings.append(
                Step(0, "FINDING", sys_id, rid, "REPORT_REMAINING_RECORD", "PRESENT", ev_id)
            )
            raw_remediations.append(
                Step(0, "REMEDIATION", sys_id, rid, "DELETE_RECORD", "ABSENT", "")
            )
            raw_verifications.append(
                Step(0, "VERIFICATION", sys_id, rid, "VERIFY_RECORD_ABSENT", "ABSENT", "")
            )

        # 2. REDACT policy violation (exposed PII on tombstones, support messages, email logs)
        elif assess.required_action == "REDACT":
            raw_findings.append(
                Step(0, "FINDING", sys_id, rid, "REPORT_EXPOSED_PII", "PRESENT", ev_id)
            )
            raw_remediations.append(
                Step(0, "REMEDIATION", sys_id, rid, "REDACT_RECORD", "REDACTED", "")
            )
            raw_verifications.append(
                Step(0, "VERIFICATION", sys_id, rid, "VERIFY_RECORD_REDACTED", "REDACTED", "")
            )

        # 3. ANONYMIZE policy violation (identifiable analytics or telemetry)
        elif assess.required_action == "ANONYMIZE":
            raw_findings.append(
                Step(0, "FINDING", sys_id, rid, "REPORT_EXPOSED_PII", "PRESENT", ev_id)
            )
            raw_remediations.append(
                Step(0, "REMEDIATION", sys_id, rid, "ANONYMIZE_RECORD", "ANONYMIZED", "")
            )
            raw_verifications.append(
                Step(0, "VERIFICATION", sys_id, rid, "VERIFY_RECORD_ANONYMIZED", "ANONYMIZED", "")
            )

        # 4. BACKUP_ARCHIVE (RETAIN action with restore unblocked)
        elif assess.data_category == "BACKUP_ARCHIVE" and assess.required_action == "RETAIN":
            has_active_flows_or_restores = True
            raw_findings.append(
                Step(0, "FINDING", sys_id, rid, "REPORT_RESTORE_RISK", "ACTIVE", ev_id)
            )
            raw_remediations.append(
                Step(0, "REMEDIATION", sys_id, rid, "BLOCK_RESTORE", "BLOCKED", "")
            )
            raw_verifications.append(
                Step(0, "VERIFICATION", sys_id, rid, "VERIFY_RESTORE_BLOCKED", "BLOCKED", "")
            )

        # 5. DATA_FLOW policy violation
        elif assess.data_category == "DATA_FLOW":
            has_active_flows_or_restores = True
            raw_findings.append(
                Step(0, "FINDING", sys_id, rid, "REPORT_ACTIVE_DATA_FLOW", "ACTIVE", ev_id)
            )
            raw_remediations.append(
                Step(0, "REMEDIATION", sys_id, rid, "DISABLE_DATA_FLOW", "DISABLED", "")
            )
            raw_verifications.append(
                Step(0, "VERIFICATION", sys_id, rid, "VERIFY_DATA_FLOW_DISABLED", "DISABLED", "")
            )

    # Deduplicate steps by (phase, operation, system_id, resource_id)
    seen_step_keys: Set[Tuple[str, str, str, str]] = set()
    all_raw_steps: List[Step] = []

    for s in raw_findings + raw_remediations + raw_verifications:
        k = (s.phase, s.operation, s.system_id, s.resource_id)
        if k not in seen_step_keys:
            seen_step_keys.add(k)
            all_raw_steps.append(s)

    # Sort strictly: phase order -> operation order -> system_id -> resource_id
    sorted_steps = sort_steps(all_raw_steps)

    # Validate generated steps against project validator
    if sorted_steps:
        errs = validate_steps(sorted_steps, "INCOMPLETE", known_evidence_ids)
        if errs:
            logger.error(f"Validation failure planning {case_id}: {errs}")
            raise ValueError(f"Step validation failed for {case_id}: {errs}")

    return CasePlanResult(
        case_id=case_id,
        deletion_status="INCOMPLETE",
        steps=sorted_steps,
        unresolved_gaps=unresolved_gaps,
        has_policy_violations=has_policy_violations,
        has_active_flows_or_restores=has_active_flows_or_restores,
    )
