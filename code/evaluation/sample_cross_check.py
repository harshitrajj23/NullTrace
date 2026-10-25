"""code/evaluation/sample_cross_check.py

Diagnostic cross-checking utilities comparing candidate clusters and resource sets
against dataset/sample_output.csv. Strictly for offline evaluation, not production pipelines.
"""

import os
import csv
import json
from typing import Dict, List, Tuple, Set, Any
from code.src.identity import Cluster
from code.src.resource_link import CandidateResource


def cross_check_sample_resources(
    clusters: Dict[str, Cluster],
    sample_output_path: str,
) -> Tuple[int, List[Tuple[str, str]]]:
    """
    Diagnostic cross-check against dataset/sample_output.csv.
    Checks whether each step's resource_id matches an identifier in that case's cluster.
    Returns (count_of_fully_covered_cases, list_of_uncovered_(case_id, resource_id)).
    """
    if not os.path.isfile(sample_output_path):
        return (0, [])

    with open(sample_output_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        sample_rows = list(reader)

    fully_covered = 0
    uncovered: List[Tuple[str, str]] = []

    for r in sample_rows:
        cid = r["case_id"]
        steps = json.loads(r["steps_json"])
        cluster = clusters.get(cid)

        # Collect all values present in cluster nodes
        cluster_values: Set[str] = set()
        if cluster:
            for node in cluster.nodes.values():
                cluster_values.add(node.value_raw)
                cluster_values.add(node.value_norm)

        case_uncovered = []
        for s in steps:
            rid = s["resource_id"]
            if rid not in cluster_values:
                case_uncovered.append(rid)
                uncovered.append((cid, rid))

        if not case_uncovered:
            fully_covered += 1

    return fully_covered, uncovered


def cross_check_sample_candidates(
    candidates_by_case: Dict[str, List[CandidateResource]],
    sample_output_path: str,
) -> Dict[str, Any]:
    """
    Compares candidate resource sets against expected resource_ids in sample_output.csv.
    Diagnostic only.
    """
    if not os.path.isfile(sample_output_path):
        raise FileNotFoundError(f"sample_output.csv not found at: {sample_output_path}")

    with open(sample_output_path, "r", encoding="utf-8") as f:
        sample_rows = list(csv.DictReader(f))

    expected_by_case: Dict[str, Set[str]] = {}
    all_expected_rids: Set[str] = set()

    for r in sample_rows:
        cid = r["case_id"]
        steps = json.loads(r["steps_json"])
        rids = set(s.get("resource_id") for s in steps if s.get("resource_id"))
        expected_by_case[cid] = rids
        all_expected_rids.update(rids)

    total_expected_pairs = sum(len(v) for v in expected_by_case.values())
    total_candidate_pairs = sum(len(set(c.resource_id for c in v)) for v in candidates_by_case.values())

    total_matched = 0
    total_missed = 0
    total_extra = 0
    full_miss_list: List[Tuple[str, str]] = []
    full_extra_list: List[Tuple[str, str]] = []

    for cid in sorted(expected_by_case.keys()):
        expected = expected_by_case[cid]
        candidates = set(c.resource_id for c in candidates_by_case.get(cid, []))

        matched = expected & candidates
        missed = expected - candidates
        extra = candidates - expected

        total_matched += len(matched)
        total_missed += len(missed)
        total_extra += len(extra)

        for m in sorted(missed):
            full_miss_list.append((cid, m))
        for x in sorted(extra):
            full_extra_list.append((cid, x))

    return {
        "expected_cases_count": len(expected_by_case),
        "total_expected_pairs": total_expected_pairs,
        "total_candidate_pairs": total_candidate_pairs,
        "total_matched_pairs": total_matched,
        "total_missed_pairs": total_missed,
        "total_extra_pairs": total_extra,
        "pair_precision": total_matched / total_candidate_pairs if total_candidate_pairs else 0.0,
        "pair_recall": total_matched / total_expected_pairs if total_expected_pairs else 0.0,
        "missed": full_miss_list,
        "extra": full_extra_list,
    }
