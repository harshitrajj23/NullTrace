"""code/src/ops.py

Grammar, sorter, and validator for HackerRank Orchestrate: Ghost Data Still Exists.
"""

from dataclasses import dataclass
import os
import re
from typing import Dict, List, Optional, Set, Tuple


# Hard-coded specification of the 15 allowed operations copied verbatim from problem_statement.md
HARDCODED_OPERATIONS: List[Tuple[str, str, str]] = [
    ("FINDING", "REPORT_REMAINING_RECORD", "PRESENT"),
    ("FINDING", "REPORT_EXPOSED_PII", "PRESENT"),
    ("FINDING", "REPORT_ACTIVE_DATA_FLOW", "ACTIVE"),
    ("FINDING", "REPORT_RESTORE_RISK", "ACTIVE"),
    ("REMEDIATION", "DISABLE_DATA_FLOW", "DISABLED"),
    ("REMEDIATION", "BLOCK_RESTORE", "BLOCKED"),
    ("REMEDIATION", "DELETE_RECORD", "ABSENT"),
    ("REMEDIATION", "REDACT_RECORD", "REDACTED"),
    ("REMEDIATION", "ANONYMIZE_RECORD", "ANONYMIZED"),
    ("VERIFICATION", "VERIFY_RECORD_ABSENT", "ABSENT"),
    ("VERIFICATION", "VERIFY_RECORD_PRESENT", "PRESENT"),
    ("VERIFICATION", "VERIFY_RECORD_REDACTED", "REDACTED"),
    ("VERIFICATION", "VERIFY_RECORD_ANONYMIZED", "ANONYMIZED"),
    ("VERIFICATION", "VERIFY_DATA_FLOW_DISABLED", "DISABLED"),
    ("VERIFICATION", "VERIFY_RESTORE_BLOCKED", "BLOCKED"),
]


def load_operations_from_spec(spec_path: Optional[str] = None) -> List[Tuple[str, str, str]]:
    """
    Parses the Allowed Operations table from problem_statement.md.
    """
    if spec_path is None:
        # Search relative to current file or repo root
        current_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(current_dir, "..", "..", "problem_statement.md"),
            os.path.join(os.getcwd(), "problem_statement.md"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                spec_path = os.path.abspath(c)
                break
        if spec_path is None:
            raise FileNotFoundError("Could not find problem_statement.md to load Allowed Operations table")

    with open(spec_path, "r", encoding="utf-8") as f:
        text = f.read()

    match = re.search(r"## Allowed Operations\s*\n\s*\|.*?\n\|.*?\n((?:\|.*?\n)+)", text)
    if not match:
        raise ValueError("Could not find Allowed Operations table in problem_statement.md")

    parsed_ops: List[Tuple[str, str, str]] = []
    for line in match.group(1).strip().split("\n"):
        parts = [p.strip().strip("`") for p in line.split("|")[1:-1]]
        if len(parts) >= 3:
            phase, op, state = parts[0], parts[1], parts[2]
            parsed_ops.append((phase, op, state))

    return parsed_ops


# Parse and verify against hardcoded copy at module load time
OPERATIONS: List[Tuple[str, str, str]] = load_operations_from_spec()
assert OPERATIONS == HARDCODED_OPERATIONS, (
    f"Parsed operations from problem_statement.md do not match hardcoded specification:\n"
    f"Parsed: {OPERATIONS}\nHardcoded: {HARDCODED_OPERATIONS}"
)

PHASE_ORDER: List[str] = ["FINDING", "REMEDIATION", "VERIFICATION"]
PHASE_RANK: Dict[str, int] = {phase: i for i, phase in enumerate(PHASE_ORDER)}

# Global operation rank: position in the spec table (0-indexed)
OPERATION_RANK: Dict[str, int] = {op: i for i, (phase, op, state) in enumerate(OPERATIONS)}

# Mapping of (phase, operation) -> allowed state
ALLOWED_STATES_MAP: Dict[Tuple[str, str], str] = {
    (phase, op): state for (phase, op, state) in OPERATIONS
}


def ALLOWED_STATE(phase: str, operation: str) -> Optional[str]:
    """Returns the allowed state for a given (phase, operation) tuple, or None if invalid."""
    return ALLOWED_STATES_MAP.get((phase, operation))


@dataclass
class Step:
    step_no: int
    phase: str
    system_id: str
    resource_id: str
    operation: str
    state: str
    evidence_id: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "step_no": self.step_no,
            "phase": self.phase,
            "system_id": self.system_id,
            "resource_id": self.resource_id,
            "operation": self.operation,
            "state": self.state,
            "evidence_id": self.evidence_id,
        }


def sort_steps(steps: List[Step]) -> List[Step]:
    """
    Sorts steps deterministically by:
      1. Phase rank (FINDING < REMEDIATION < VERIFICATION)
      2. Operation rank (spec table order)
      3. system_id ascending
      4. resource_id ascending
    Then renumbers step_no from 1 with no gaps.
    Stable and deterministic. Does NOT look at evidence_id or state.
    """
    def sort_key(s: Step) -> Tuple[int, int, str, str]:
        p_rank = PHASE_RANK.get(s.phase, 999)
        op_rank = OPERATION_RANK.get(s.operation, 999)
        return (p_rank, op_rank, s.system_id, s.resource_id)

    sorted_list = sorted(steps, key=sort_key)
    renumbered: List[Step] = []
    for idx, s in enumerate(sorted_list, start=1):
        renumbered.append(
            Step(
                step_no=idx,
                phase=s.phase,
                system_id=s.system_id,
                resource_id=s.resource_id,
                operation=s.operation,
                state=s.state,
                evidence_id=s.evidence_id,
            )
        )
    return renumbered


# Error code constants for validator
ERR_INVALID_STATUS = "ERR_INVALID_STATUS"
ERR_NOT_APPLICABLE_NON_EMPTY_STEPS = "ERR_NOT_APPLICABLE_NON_EMPTY_STEPS"
ERR_COMPLETE_NON_VERIFICATION_PHASE = "ERR_COMPLETE_NON_VERIFICATION_PHASE"
ERR_COMPLETE_HAS_REMEDIATION = "ERR_COMPLETE_HAS_REMEDIATION"
ERR_COMPLETE_EMPTY_EVIDENCE_ID = "ERR_COMPLETE_EMPTY_EVIDENCE_ID"
ERR_INCOMPLETE_FINDING_EMPTY_EVIDENCE = "ERR_INCOMPLETE_FINDING_EMPTY_EVIDENCE"
ERR_INCOMPLETE_NON_EMPTY_FUTURE_EVIDENCE = "ERR_INCOMPLETE_NON_EMPTY_FUTURE_EVIDENCE"
ERR_PHASE_OP_MISMATCH = "ERR_PHASE_OP_MISMATCH"
ERR_INVALID_STATE = "ERR_INVALID_STATE"
ERR_STEP_NO_NON_CONSECUTIVE = "ERR_STEP_NO_NON_CONSECUTIVE"
ERR_STEP_NO_POSITION_MISMATCH = "ERR_STEP_NO_POSITION_MISMATCH"
ERR_NOT_SORTED = "ERR_NOT_SORTED"
ERR_EMPTY_SYSTEM_ID = "ERR_EMPTY_SYSTEM_ID"
ERR_EMPTY_RESOURCE_ID = "ERR_EMPTY_RESOURCE_ID"
ERR_EMPTY_OPERATION = "ERR_EMPTY_OPERATION"
ERR_UNKNOWN_EVIDENCE_ID = "ERR_UNKNOWN_EVIDENCE_ID"


def validate_steps(
    steps: List[Step],
    status: str,
    known_evidence_ids: Optional[Set[str]] = None,
) -> List[str]:
    """
    Validates a list of steps against the grader contract and case deletion status.
    Returns a list of error codes. An empty list signifies complete validity.
    """
    errors: List[str] = []

    valid_statuses = {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"}
    if status not in valid_statuses:
        errors.append(ERR_INVALID_STATUS)

    # 1. NOT_APPLICABLE rule: must have 0 steps
    if status == "NOT_APPLICABLE":
        if len(steps) > 0:
            errors.append(ERR_NOT_APPLICABLE_NON_EMPTY_STEPS)
        return errors

    # Check for empty / missing basic fields and grammar conformance per step
    for idx, s in enumerate(steps):
        # Empty field checks
        if not s.system_id or not s.system_id.strip():
            errors.append(ERR_EMPTY_SYSTEM_ID)
        if not s.resource_id or not s.resource_id.strip():
            errors.append(ERR_EMPTY_RESOURCE_ID)
        if not s.operation or not s.operation.strip():
            errors.append(ERR_EMPTY_OPERATION)

        # Grammar & state check
        expected_state = ALLOWED_STATE(s.phase, s.operation)
        if expected_state is None:
            errors.append(ERR_PHASE_OP_MISMATCH)
        elif s.state != expected_state:
            errors.append(ERR_INVALID_STATE)

        # Step numbering checks
        expected_step_no = idx + 1
        if s.step_no != expected_step_no:
            errors.append(ERR_STEP_NO_POSITION_MISMATCH)
        if idx > 0 and s.step_no != steps[idx - 1].step_no + 1:
            errors.append(ERR_STEP_NO_NON_CONSECUTIVE)

        # Evidence ID checks
        if s.evidence_id != "":
            if known_evidence_ids is not None and s.evidence_id not in known_evidence_ids:
                errors.append(ERR_UNKNOWN_EVIDENCE_ID)

        # Status COMPLETE rules:
        if status == "COMPLETE":
            if s.phase != "VERIFICATION":
                errors.append(ERR_COMPLETE_NON_VERIFICATION_PHASE)
            if s.phase == "REMEDIATION":
                errors.append(ERR_COMPLETE_HAS_REMEDIATION)
            if s.evidence_id == "":
                errors.append(ERR_COMPLETE_EMPTY_EVIDENCE_ID)

        # Status INCOMPLETE rules:
        elif status == "INCOMPLETE":
            if s.phase == "FINDING" and s.evidence_id == "":
                errors.append(ERR_INCOMPLETE_FINDING_EMPTY_EVIDENCE)
            elif s.phase in ("REMEDIATION", "VERIFICATION") and s.evidence_id != "":
                errors.append(ERR_INCOMPLETE_NON_EMPTY_FUTURE_EVIDENCE)

    # Check sorting order
    if len(steps) > 1:
        # Check if steps match sort_steps order
        sorted_steps_list = sort_steps(steps)
        for s_orig, s_sorted in zip(steps, sorted_steps_list):
            if (
                s_orig.phase != s_sorted.phase
                or s_orig.operation != s_sorted.operation
                or s_orig.system_id != s_sorted.system_id
                or s_orig.resource_id != s_sorted.resource_id
            ):
                errors.append(ERR_NOT_SORTED)
                break

    return errors
