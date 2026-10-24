"""code/tests/test_contract_roundtrip.py

Round-trip test against official sample outputs in dataset/sample_output.csv.
"""

import csv
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
    from code.src.ops import sort_steps, validate_steps
    from code.src.grader_io import parse_steps_json, serialize_steps, read_sample_output
except ImportError:
    from src.ops import sort_steps, validate_steps
    from src.grader_io import parse_steps_json, serialize_steps, read_sample_output




def get_known_evidence_ids() -> Set[str]:
    evidence_csv_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "dataset", "evidence_files.csv"
    )
    known: Set[str] = set()
    with open(evidence_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            known.add(r["file_id"])
    return known


def test_contract_roundtrip_all_samples():
    sample_csv_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "dataset", "sample_output.csv"
    )
    known_evidence_ids = get_known_evidence_ids()
    rows = read_sample_output(sample_csv_path)

    assert len(rows) == 32, f"Expected 32 sample rows, found {len(rows)}"

    total_checked = 0
    total_passing = 0
    failures = []

    for r in rows:
        total_checked += 1
        case_id = r["case_id"]
        status = r["deletion_status"]
        steps = r["steps"]

        # 1. Validate
        errors = validate_steps(steps, status, known_evidence_ids)
        if errors:
            failures.append((case_id, "validation", errors))
            continue

        # 2. Assert re-sorting leaves steps unchanged
        sorted_steps = sort_steps(steps)
        if steps != sorted_steps:
            failures.append((case_id, "sort_order", [f"Steps not equal to sorted: {steps} != {sorted_steps}"]))
            continue

        # 3. Serialize and re-parse equality
        serialized = serialize_steps(steps)
        reparsed = parse_steps_json(serialized)
        if steps != reparsed:
            failures.append((case_id, "serialization", [f"Steps not equal to reparsed: {steps} != {reparsed}"]))
            continue

        total_passing += 1

    print("\n=== CONTRACT ROUND-TRIP TEST SUMMARY ===")
    print(f"Rows checked: {total_checked}")
    print(f"Rows passing: {total_passing}")
    print(f"Rows failing: {len(failures)}")
    if failures:
        for cid, f_type, errs in failures:
            print(f"  FAILED {cid} [{f_type}]: {errs}")

    assert len(failures) == 0, f"{len(failures)} sample cases failed roundtrip: {failures}"


if __name__ == "__main__":
    test_contract_roundtrip_all_samples()
