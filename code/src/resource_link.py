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


def get_canonical_account_id(user_id: str) -> Optional[str]:
    """
    Derives the canonical account ID for a user_id, preserving leading-zero semantics.
    e.g.:
      user_01 -> account_001
      user_05 -> account_005
      user_34 -> account_034
      user_106 -> account_106
      user_8741 -> account_8741
    """
    m = re.match(r"^user_(\d+)$", user_id.strip())
    if not m:
        return None
    digits = m.group(1)
    if len(digits) < 3:
        return f"account_{int(digits):03d}"
    return f"account_{digits}"


def check_canonical_account_corroboration(
    canonical_rid: str,
    cluster: Cluster,
    dataset: Dataset,
    evidence_observations: Optional[List[Any]] = None,
) -> Tuple[bool, Optional[CandidateResource]]:
    """
    Evaluates whether canonical_rid is corroborated by repository evidence
    and has no conflicting identity links.
    Returns (is_valid, optional_candidate_resource).
    """
    c_vals = {node.value_norm for node in cluster.nodes.values()}

    # 0. Check if cluster already has a distinct, directly grounded account in evidence observations
    if evidence_observations:
        for obs in evidence_observations:
            for ikind, ival in getattr(obs, "associated_identifiers", {}).items():
                if ival and ival in c_vals:
                    if obs.resource_id and obs.resource_id.startswith("account_") and obs.resource_id != canonical_rid:
                        # Cluster already has an authoritative directly-grounded account (e.g. account_2420 for user_421)
                        return False, None

    # 1. Check for conflicting identity links in evidence observations
    if evidence_observations:
        for obs in evidence_observations:
            if obs.resource_id == canonical_rid:
                for ikind, ival in getattr(obs, "associated_identifiers", {}).items():
                    if ival and ival not in c_vals:
                        # Conflicting identity! e.g. account_246 belongs to user_173, not user_246
                        return False, None

    # 2. Check for conflicting identity in system_activity details
    for act in dataset.system_activity:
        if act.resource_id == canonical_rid:
            content = f"{act.details or ''}"
            # Check if details mentions an unrelated user_id
            found_uids = re.findall(r"\buser_\d+\b", content)
            for fuid in found_uids:
                if fuid not in c_vals:
                    return False, None
            # Check if details mentions an unrelated email
            found_emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", content)
            for fem in found_emails:
                norm_e = normalize_email(fem)
                if norm_e and norm_e not in c_vals:
                    return False, None

    # 3. Check for corroborating evidence
    # (A) System activity row targeting or originating from account_service
    matching_act: Optional[SystemActivity] = None
    for act in dataset.system_activity:
        if act.resource_id == canonical_rid:
            if act.target_system in ("account_service", "account_failover_replica") or act.source_system in ("deletion_worker", "account_service"):
                matching_act = act
                break

    # (B) Evidence observation in account_service / customer_profiles
    has_evidence_obs = False
    if evidence_observations:
        for obs in evidence_observations:
            if obs.resource_id == canonical_rid:
                has_evidence_obs = True
                break

    # Must have at least matching activity or direct evidence observation
    if not matching_act and not has_evidence_obs:
        return False, None

    cand: Optional[CandidateResource] = None
    if matching_act:
        cand = CandidateResource(
            resource_id=canonical_rid,
            activity_id=matching_act.activity_id,
            system_id=matching_act.target_system or matching_act.source_system or "account_service",
            operation=matching_act.event_type,
            timestamp_raw=matching_act.event_time_raw,
            timestamp=matching_act.event_time,
            reported_result=matching_act.reported_result,
            reason_code="CANONICAL_ACCOUNT_MATCH",
            strength="CONFIRMED",
            source=matching_act.source,
        )

    return True, cand


def link_cluster_resources(
    cluster: Cluster,
    dataset: Dataset,
    index: Optional[ActivitySubjectIndex] = None,
    evidence_observations: Optional[List[Any]] = None,
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

    # 4. Fourth pass: Canonical account matching (CONFIRMED per D3)
    has_account_linked = any(c.resource_id.startswith("account_") for c in candidates)
    if not has_account_linked:
        for uid in sorted(uids):
            canon_id = get_canonical_account_id(uid)
            if canon_id:
                is_valid, canon_cand = check_canonical_account_corroboration(
                    canonical_rid=canon_id,
                    cluster=cluster,
                    dataset=dataset,
                    evidence_observations=evidence_observations,
                )
                if is_valid and canon_cand:
                    if canon_cand.activity_id not in seen_activity_ids:
                        seen_activity_ids.add(canon_cand.activity_id)
                        candidates.append(canon_cand)

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

