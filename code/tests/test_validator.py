"""code/tests/test_validator.py

Unit tests for all validator rules and error codes in code/src/ops.py.
"""

import os
import sys

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if "code" in sys.modules and not hasattr(sys.modules["code"], "src"):
    del sys.modules["code"]

import pytest
from typing import Set

try:
    from code.src.ops import (
        Step,
        validate_steps,
        sort_steps,
        ERR_INVALID_STATUS,
        ERR_NOT_APPLICABLE_NON_EMPTY_STEPS,
        ERR_COMPLETE_NON_VERIFICATION_PHASE,
        ERR_COMPLETE_HAS_REMEDIATION,
        ERR_COMPLETE_EMPTY_EVIDENCE_ID,
        ERR_INCOMPLETE_FINDING_EMPTY_EVIDENCE,
        ERR_INCOMPLETE_NON_EMPTY_FUTURE_EVIDENCE,
        ERR_PHASE_OP_MISMATCH,
        ERR_INVALID_STATE,
        ERR_STEP_NO_POSITION_MISMATCH,
        ERR_STEP_NO_NON_CONSECUTIVE,
        ERR_NOT_SORTED,
        ERR_EMPTY_SYSTEM_ID,
        ERR_EMPTY_RESOURCE_ID,
        ERR_EMPTY_OPERATION,
        ERR_UNKNOWN_EVIDENCE_ID,
        ERR_INCOMPLETE_EMPTY,
    )
except ImportError:
    from src.ops import (
        Step,
        validate_steps,
        sort_steps,
        ERR_INVALID_STATUS,
        ERR_NOT_APPLICABLE_NON_EMPTY_STEPS,
        ERR_COMPLETE_NON_VERIFICATION_PHASE,
        ERR_COMPLETE_HAS_REMEDIATION,
        ERR_COMPLETE_EMPTY_EVIDENCE_ID,
        ERR_INCOMPLETE_FINDING_EMPTY_EVIDENCE,
        ERR_INCOMPLETE_NON_EMPTY_FUTURE_EVIDENCE,
        ERR_PHASE_OP_MISMATCH,
        ERR_INVALID_STATE,
        ERR_STEP_NO_POSITION_MISMATCH,
        ERR_STEP_NO_NON_CONSECUTIVE,
        ERR_NOT_SORTED,
        ERR_EMPTY_SYSTEM_ID,
        ERR_EMPTY_RESOURCE_ID,
        ERR_EMPTY_OPERATION,
        ERR_UNKNOWN_EVIDENCE_ID,
        ERR_INCOMPLETE_EMPTY,
    )

KNOWN_EVIDENCE: Set[str] = {"evidence_01", "evidence_02"}


def test_valid_complete():
    steps = [
        Step(
            step_no=1,
            phase="VERIFICATION",
            system_id="account_service",
            resource_id="acc_1",
            operation="VERIFY_RECORD_ABSENT",
            state="ABSENT",
            evidence_id="evidence_01",
        )
    ]
    errs = validate_steps(steps, "COMPLETE", KNOWN_EVIDENCE)
    assert errs == []


def test_valid_incomplete():
    steps = [
        Step(
            step_no=1,
            phase="FINDING",
            system_id="account_service",
            resource_id="acc_1",
            operation="REPORT_REMAINING_RECORD",
            state="PRESENT",
            evidence_id="evidence_01",
        ),
        Step(
            step_no=2,
            phase="REMEDIATION",
            system_id="account_service",
            resource_id="acc_1",
            operation="DELETE_RECORD",
            state="ABSENT",
            evidence_id="",
        ),
        Step(
            step_no=3,
            phase="VERIFICATION",
            system_id="account_service",
            resource_id="acc_1",
            operation="VERIFY_RECORD_ABSENT",
            state="ABSENT",
            evidence_id="",
        ),
    ]
    errs = validate_steps(steps, "INCOMPLETE", KNOWN_EVIDENCE)
    assert errs == []


def test_valid_not_applicable():
    errs = validate_steps([], "NOT_APPLICABLE", KNOWN_EVIDENCE)
    assert errs == []


def test_err_invalid_status():
    errs = validate_steps([], "UNKNOWN_STATUS", KNOWN_EVIDENCE)
    assert ERR_INVALID_STATUS in errs


def test_err_not_applicable_non_empty():
    steps = [
        Step(
            step_no=1,
            phase="VERIFICATION",
            system_id="sys",
            resource_id="res",
            operation="VERIFY_RECORD_ABSENT",
            state="ABSENT",
            evidence_id="evidence_01",
        )
    ]
    errs = validate_steps(steps, "NOT_APPLICABLE", KNOWN_EVIDENCE)
    assert ERR_NOT_APPLICABLE_NON_EMPTY_STEPS in errs


def test_err_complete_non_verification_phase():
    steps = [
        Step(
            step_no=1,
            phase="FINDING",
            system_id="sys",
            resource_id="res",
            operation="REPORT_REMAINING_RECORD",
            state="PRESENT",
            evidence_id="evidence_01",
        )
    ]
    errs = validate_steps(steps, "COMPLETE", KNOWN_EVIDENCE)
    assert ERR_COMPLETE_NON_VERIFICATION_PHASE in errs


def test_err_complete_has_remediation():
    steps = [
        Step(
            step_no=1,
            phase="REMEDIATION",
            system_id="sys",
            resource_id="res",
            operation="DELETE_RECORD",
            state="ABSENT",
            evidence_id="",
        )
    ]
    errs = validate_steps(steps, "COMPLETE", KNOWN_EVIDENCE)
    assert ERR_COMPLETE_HAS_REMEDIATION in errs
    assert ERR_COMPLETE_NON_VERIFICATION_PHASE in errs


def test_err_complete_empty_evidence_id():
    steps = [
        Step(
            step_no=1,
            phase="VERIFICATION",
            system_id="sys",
            resource_id="res",
            operation="VERIFY_RECORD_ABSENT",
            state="ABSENT",
            evidence_id="",
        )
    ]
    errs = validate_steps(steps, "COMPLETE", KNOWN_EVIDENCE)
    assert ERR_COMPLETE_EMPTY_EVIDENCE_ID in errs


def test_err_incomplete_finding_empty_evidence():
    steps = [
        Step(
            step_no=1,
            phase="FINDING",
            system_id="sys",
            resource_id="res",
            operation="REPORT_REMAINING_RECORD",
            state="PRESENT",
            evidence_id="",
        )
    ]
    errs = validate_steps(steps, "INCOMPLETE", KNOWN_EVIDENCE)
    assert ERR_INCOMPLETE_FINDING_EMPTY_EVIDENCE in errs


def test_err_incomplete_non_empty_future_evidence():
    steps = [
        Step(
            step_no=1,
            phase="REMEDIATION",
            system_id="sys",
            resource_id="res",
            operation="DELETE_RECORD",
            state="ABSENT",
            evidence_id="evidence_01",
        )
    ]
    errs = validate_steps(steps, "INCOMPLETE", KNOWN_EVIDENCE)
    assert ERR_INCOMPLETE_NON_EMPTY_FUTURE_EVIDENCE in errs


def test_err_phase_op_mismatch():
    steps = [
        Step(
            step_no=1,
            phase="FINDING",
            system_id="sys",
            resource_id="res",
            operation="DELETE_RECORD",
            state="ABSENT",
            evidence_id="evidence_01",
        )
    ]
    errs = validate_steps(steps, "INCOMPLETE", KNOWN_EVIDENCE)
    assert ERR_PHASE_OP_MISMATCH in errs


def test_err_invalid_state():
    steps = [
        Step(
            step_no=1,
            phase="FINDING",
            system_id="sys",
            resource_id="res",
            operation="REPORT_REMAINING_RECORD",
            state="ABSENT",
            evidence_id="evidence_01",
        )
    ]
    errs = validate_steps(steps, "INCOMPLETE", KNOWN_EVIDENCE)
    assert ERR_INVALID_STATE in errs


def test_err_step_no_position_and_consecutive_mismatch():
    steps = [
        Step(
            step_no=2,
            phase="VERIFICATION",
            system_id="sys",
            resource_id="res",
            operation="VERIFY_RECORD_ABSENT",
            state="ABSENT",
            evidence_id="evidence_01",
        ),
        Step(
            step_no=5,
            phase="VERIFICATION",
            system_id="sys",
            resource_id="res2",
            operation="VERIFY_RECORD_ABSENT",
            state="ABSENT",
            evidence_id="evidence_01",
        ),
    ]
    errs = validate_steps(steps, "COMPLETE", KNOWN_EVIDENCE)
    assert ERR_STEP_NO_POSITION_MISMATCH in errs
    assert ERR_STEP_NO_NON_CONSECUTIVE in errs


def test_err_not_sorted():
    # REMEDIATION placed before FINDING
    steps = [
        Step(
            step_no=1,
            phase="REMEDIATION",
            system_id="sys",
            resource_id="res",
            operation="DELETE_RECORD",
            state="ABSENT",
            evidence_id="",
        ),
        Step(
            step_no=2,
            phase="FINDING",
            system_id="sys",
            resource_id="res",
            operation="REPORT_REMAINING_RECORD",
            state="PRESENT",
            evidence_id="evidence_01",
        ),
    ]
    errs = validate_steps(steps, "INCOMPLETE", KNOWN_EVIDENCE)
    assert ERR_NOT_SORTED in errs


def test_err_empty_fields():
    steps = [
        Step(
            step_no=1,
            phase="VERIFICATION",
            system_id="",
            resource_id="   ",
            operation="",
            state="ABSENT",
            evidence_id="evidence_01",
        )
    ]
    errs = validate_steps(steps, "COMPLETE", KNOWN_EVIDENCE)
    assert ERR_EMPTY_SYSTEM_ID in errs
    assert ERR_EMPTY_RESOURCE_ID in errs
    assert ERR_EMPTY_OPERATION in errs


def test_err_unknown_evidence_id():
    steps = [
        Step(
            step_no=1,
            phase="VERIFICATION",
            system_id="sys",
            resource_id="res",
            operation="VERIFY_RECORD_ABSENT",
            state="ABSENT",
            evidence_id="evidence_unknown_999",
        )
    ]
    errs = validate_steps(steps, "COMPLETE", KNOWN_EVIDENCE)
    assert ERR_UNKNOWN_EVIDENCE_ID in errs


def test_err_incomplete_empty():
    """An INCOMPLETE case with steps_json=[] must return ERR_INCOMPLETE_EMPTY."""
    errs = validate_steps([], "INCOMPLETE", KNOWN_EVIDENCE)
    assert ERR_INCOMPLETE_EMPTY in errs
    assert "INCOMPLETE_EMPTY" in errs


def test_incomplete_with_steps_valid():
    """An INCOMPLETE case with valid steps must not return ERR_INCOMPLETE_EMPTY."""
    steps = [
        Step(1, "FINDING", "sys", "res", "REPORT_REMAINING_RECORD", "PRESENT", "evidence_01"),
        Step(2, "REMEDIATION", "sys", "res", "DELETE_RECORD", "ABSENT", ""),
        Step(3, "VERIFICATION", "sys", "res", "VERIFY_RECORD_ABSENT", "ABSENT", ""),
    ]
    errs = validate_steps(steps, "INCOMPLETE", KNOWN_EVIDENCE)
    assert ERR_INCOMPLETE_EMPTY not in errs
    assert errs == []

