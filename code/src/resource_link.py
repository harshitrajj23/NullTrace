"""code/src/resource_link.py

Links identity clusters to candidate system records using system_activity.csv.
Extracts candidate resources, attaches reason codes and SourceRefs, assigns confidence
strengths following D3 (CONFIRMED for user_id matches; PROBABLE otherwise), and
maintains deterministic ordering by timestamp, then activity_id.
"""

from collections import Counter
import csv
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure repository root is on sys.path
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

# Standard library module 'code' conflict resolution
if "code" in sys.modules and not hasattr(sys.modules["code"], "src"):
    del sys.modules["code"]

try:
    from code.src.models import SourceRef, SystemActivity
    from code.src.loader import Dataset
    from code.src.identity import Cluster, IdentifierNode
    from code.src.normalize import normalize_email, normalize_phone
except ImportError:
    from src.models import SourceRef, SystemActivity
    from src.loader import Dataset
    from src.identity import Cluster, IdentifierNode
    from src.normalize import normalize_email, normalize_phone


@dataclass
class CandidateResource:
    """Represents a candidate system record linked to an identity cluster."""
    resource_id: str
    activity_id: str
    system_id: str
    operation: str
    timestamp_raw: str
    timestamp: Optional[datetime]
    reported_result: str
    reason_code: str  # SUBJECT_USER_ID_MATCH, SUBJECT_EMAIL_MATCH, SUBJECT_PHONE_MATCH
    strength: str  # CONFIRMED or PROBABLE
    source: SourceRef

    def sort_key(self) -> Tuple[str, str, str]:
        return (self.timestamp_raw or "", self.activity_id, self.resource_id)


class ActivitySubjectIndex:
    """
    Pre-indexes system_activity rows by any subject identifier mentioned in the row
    (details, resource_id, etc.) for deterministic O(1) cluster linking.
    """
    def __init__(self, activities: List[SystemActivity]):
        self.activities_by_user_id: Dict[str, List[SystemActivity]] = {}
        self.activities_by_email: Dict[str, List[SystemActivity]] = {}
        self.activities_by_phone: Dict[str, List[SystemActivity]] = {}

        # Regex patterns for subject identifiers
        user_pattern = re.compile(r"\buser_\d+\b")
        email_pattern = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

        for act in activities:
            # We check the details column and other fields where text may appear
            content = f"{act.details or ''} {act.resource_id or ''}"

            # 1. User IDs
            for uid in set(user_pattern.findall(content)):
                self.activities_by_user_id.setdefault(uid, []).append(act)

            # 2. Emails
            for em in set(email_pattern.findall(content)):
                em_norm = normalize_email(em)
                if em_norm:
                    self.activities_by_email.setdefault(em_norm, []).append(act)

            # 3. Direct field check if activity row contains explicit phone numbers
            # (Matches any international phone formatted string)
            phone_matches = re.findall(r"\+\d{1,3}(?:[ -]?\d+){2,}", content)
            for p in phone_matches:
                p_norm = normalize_phone(p)
                if p_norm:
                    self.activities_by_phone.setdefault(p_norm, []).append(act)


def link_cluster_resources(
    cluster: Cluster,
    dataset: Dataset,
    index: Optional[ActivitySubjectIndex] = None,
) -> List[CandidateResource]:
    """
    Finds system_activity rows where any identifier in the cluster matches
    the row's subject details, using normalized values for emails and phones.
    Follows D3: CONFIRMED for user_id matches; PROBABLE otherwise.
    Returns deterministically sorted list of CandidateResource.
    """
    if index is None:
        index = ActivitySubjectIndex(dataset.system_activity)

    candidates: List[CandidateResource] = []
    seen_activity_ids: Set[str] = set()

    # Collect cluster identifiers grouped by kind
    uids: Set[str] = set()
    emails: Set[str] = set()
    phones: Set[str] = set()

    for node in cluster.nodes.values():
        if node.kind == "user_id":
            uids.add(node.value_norm)
        elif node.kind == "email":
            emails.add(node.value_norm)
        elif node.kind == "phone":
            phones.add(node.value_norm)

    # 1. First pass: Match user_id (CONFIRMED per D3)
    for uid in sorted(uids):
        matched_acts = index.activities_by_user_id.get(uid, [])
        for act in matched_acts:
            if act.activity_id not in seen_activity_ids:
                seen_activity_ids.add(act.activity_id)
                candidates.append(
                    CandidateResource(
                        resource_id=act.resource_id,
                        activity_id=act.activity_id,
                        system_id=act.target_system or act.source_system or "system",
                        operation=act.event_type,
                        timestamp_raw=act.event_time_raw,
                        timestamp=act.event_time,
                        reported_result=act.reported_result,
                        reason_code="SUBJECT_USER_ID_MATCH",
                        strength="CONFIRMED",
                        source=act.source,
                    )
                )

    # 2. Second pass: Match email (PROBABLE per D3)
    for em in sorted(emails):
        matched_acts = index.activities_by_email.get(em, [])
        for act in matched_acts:
            if act.activity_id not in seen_activity_ids:
                seen_activity_ids.add(act.activity_id)
                candidates.append(
                    CandidateResource(
                        resource_id=act.resource_id,
                        activity_id=act.activity_id,
                        system_id=act.target_system or act.source_system or "system",
                        operation=act.event_type,
                        timestamp_raw=act.event_time_raw,
                        timestamp=act.event_time,
                        reported_result=act.reported_result,
                        reason_code="SUBJECT_EMAIL_MATCH",
                        strength="PROBABLE",
                        source=act.source,
                    )
                )

    # 3. Third pass: Match phone (PROBABLE per D3)
    for p in sorted(phones):
        matched_acts = index.activities_by_phone.get(p, [])
        for act in matched_acts:
            if act.activity_id not in seen_activity_ids:
                seen_activity_ids.add(act.activity_id)
                candidates.append(
                    CandidateResource(
                        resource_id=act.resource_id,
                        activity_id=act.activity_id,
                        system_id=act.target_system or act.source_system or "system",
                        operation=act.event_type,
                        timestamp_raw=act.event_time_raw,
                        timestamp=act.event_time,
                        reported_result=act.reported_result,
                        reason_code="SUBJECT_PHONE_MATCH",
                        strength="PROBABLE",
                        source=act.source,
                    )
                )

    # Deterministic sort: timestamp ascending, then activity_id ascending
    candidates.sort(key=lambda c: c.sort_key())
    return candidates


def link_all_clusters(
    clusters: Dict[str, Cluster],
    dataset: Dataset,
) -> Dict[str, List[CandidateResource]]:
    """Links candidate system_activity records for all clusters deterministically."""
    index = ActivitySubjectIndex(dataset.system_activity)
    candidates_by_case: Dict[str, List[CandidateResource]] = {}

    for cid in sorted(clusters.keys()):
        candidates_by_case[cid] = link_cluster_resources(clusters[cid], dataset, index=index)

    return candidates_by_case


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
        "total_cases": len(expected_by_case),
        "total_expected_pairs": total_expected_pairs,
        "total_candidate_pairs": total_candidate_pairs,
        "total_matched": total_matched,
        "total_missed": total_missed,
        "total_extra": total_extra,
        "full_miss_list": full_miss_list,
        "full_extra_list": full_extra_list,
    }
