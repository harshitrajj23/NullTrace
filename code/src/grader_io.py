"""code/src/grader_io.py

I/O utilities for parsing and serializing steps and reading/writing grader CSVs.
"""

import csv
import json
from typing import Any, Dict, List

from .ops import Step


def parse_steps_json(text: str) -> List[Step]:
    """
    Parses a JSON string representing steps into a list of Step objects.
    Raises ValueError on invalid JSON or ill-formed structure.
    """
    if not isinstance(text, str):
        raise ValueError(f"Expected steps_json to be a string, got {type(text).__name__}")

    stripped = text.strip()
    if not stripped:
        return []

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON string in steps_json: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError(f"Expected steps_json to be a JSON array, got {type(data).__name__}")

    steps: List[Step] = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Step at index {idx} is not a JSON object: {item}")

        step = Step(
            step_no=int(item.get("step_no", idx + 1)),
            phase=str(item.get("phase", "")),
            system_id=str(item.get("system_id", "")),
            resource_id=str(item.get("resource_id", "")),
            operation=str(item.get("operation", "")),
            state=str(item.get("state", "")),
            evidence_id=str(item.get("evidence_id", "")),
        )
        steps.append(step)

    return steps


def serialize_steps(steps: List[Step]) -> str:
    """
    Produces canonical JSON with keys in the exact spec order:
    ["step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id"]
    and compact serialization (no whitespace around separators).
    """
    step_dicts = []
    for s in steps:
        ordered_dict = {
            "step_no": s.step_no,
            "phase": s.phase,
            "system_id": s.system_id,
            "resource_id": s.resource_id,
            "operation": s.operation,
            "state": s.state,
            "evidence_id": s.evidence_id,
        }
        step_dicts.append(ordered_dict)

    return json.dumps(step_dicts, separators=(",", ":"))


def read_sample_output(path: str) -> List[Dict[str, Any]]:
    """
    Reads a sample output CSV file and returns a list of row dicts containing:
    case_id, deletion_status, raw steps_json, and parsed steps.
    """
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            case_id = r["case_id"]
            deletion_status = r["deletion_status"]
            steps_json_str = r["steps_json"]
            steps = parse_steps_json(steps_json_str)
            rows.append({
                "case_id": case_id,
                "deletion_status": deletion_status,
                "steps_json": steps_json_str,
                "steps": steps,
            })
    return rows


def write_output_csv(rows: List[Dict[str, Any]], path: str) -> None:
    """
    Writes output rows to CSV matching the header `case_id,deletion_status,steps_json`
    and sorted strictly by case_id ascending.
    """
    # Sort strictly by case_id
    sorted_rows = sorted(rows, key=lambda r: r["case_id"])

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["case_id", "deletion_status", "steps_json"])
        for r in sorted_rows:
            case_id = r["case_id"]
            status = r["deletion_status"]
            if "steps" in r:
                steps_json = serialize_steps(r["steps"])
            else:
                steps_json = r.get("steps_json", "[]")
            writer.writerow([case_id, status, steps_json])
