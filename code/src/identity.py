"""code/src/identity.py

Deterministic identity resolution for deletion requests.
Builds identifier clusters with confidence levels (CONFIRMED, PROBABLE, UNRESOLVED),
preserves raw identifiers, attaches reason codes and SourceRefs to all links,
and detects conflicts without merging.
"""

from collections import Counter
from dataclasses import dataclass, field
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import (
    SourceRef,
    Identity,
    AuditEvent,
    DeletionRequest,
)
from .loader import Dataset
from .normalize import normalize_email, normalize_phone


@dataclass
class IdentifierNode:
    """Represents an identifier within an identity cluster."""
    kind: str  # 'email', 'phone', 'user_id', 'email_hash'
    value_raw: str
    value_norm: str
    role: str  # 'current', 'historical', 'unknown'
    source: List[SourceRef] = field(default_factory=list)

    @property
    def key(self) -> Tuple[str, str]:
        return (self.kind, self.value_norm)


@dataclass
class Link:
    """Represents a provenance-backed connection between two identifiers."""
    from_node: IdentifierNode
    to_node: IdentifierNode
    strength: str  # 'CONFIRMED', 'PROBABLE', 'UNRESOLVED'
    reason_code: str  # e.g. 'SHARED_USER_ID', 'AUDIT_OLD_NEW_SAME_USER', 'PLUS_ADDRESS_VARIANT', etc.
    source: SourceRef


@dataclass
class Conflict:
    """Represents an unresolved conflict encountered during resolution."""
    conflict_type: str  # e.g. 'EMAIL_CONFLICT'
    details: str
    nodes: List[IdentifierNode]
    source: SourceRef


@dataclass
class Cluster:
    """Collection of linked identifiers and conflicts for a deletion request."""
    case_id: str
    nodes: Dict[Tuple[str, str], IdentifierNode] = field(default_factory=dict)
    links: List[Link] = field(default_factory=list)
    conflicts: List[Conflict] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)

    def add_node(self, node: IdentifierNode) -> IdentifierNode:
        k = node.key
        if k in self.nodes:
            existing = self.nodes[k]
            # Merge sources preserving order and uniqueness
            for s in node.source:
                if s not in existing.source:
                    existing.source.append(s)
            if existing.role == "unknown" and node.role != "unknown":
                existing.role = node.role
            elif node.role == "historical":
                existing.role = "historical"
            elif node.role == "current" and existing.role != "historical":
                existing.role = "current"
            return existing
        self.nodes[k] = node
        return node


    def add_link(self, link: Link) -> None:
        # Check if identical link already exists
        for l in self.links:
            if (
                l.from_node.key == link.from_node.key
                and l.to_node.key == link.to_node.key
                and l.strength == link.strength
                and l.reason_code == link.reason_code
                and l.source == link.source
            ):
                return
        self.links.append(link)


def _strip_plus_tag(email_norm: str) -> Optional[str]:
    """Returns the base email if email contains a '+' tag, else None."""
    if "@" not in email_norm:
        return None
    local, domain = email_norm.split("@", 1)
    if "+" in local:
        base_local = local.split("+", 1)[0]
        if base_local:
            return f"{base_local}@{domain}"
    return None


class IdentityIndex:
    """Precomputed lookup indexes over the dataset for fast, deterministic resolution."""
    def __init__(self, dataset: Dataset):
        self.identities_by_email: Dict[str, List[Identity]] = {}
        self.identities_by_user_id: Dict[str, Identity] = {}
        self.identities_by_phone: Dict[str, List[Identity]] = {}
        self.identities_by_email_hash: Dict[str, List[Identity]] = {}
        self.identities_by_name: Dict[str, List[Identity]] = {}

        for ident in dataset.user_identities:
            self.identities_by_user_id[ident.user_id] = ident
            if ident.email_norm:
                self.identities_by_email.setdefault(ident.email_norm, []).append(ident)
            if ident.phone_norm:
                self.identities_by_phone.setdefault(ident.phone_norm, []).append(ident)
            if ident.email_hash:
                self.identities_by_email_hash.setdefault(ident.email_hash.lower(), []).append(ident)
            if ident.name:
                self.identities_by_name.setdefault(ident.name.strip().lower(), []).append(ident)

        self.audit_by_user_id: Dict[str, List[AuditEvent]] = {}
        self.audit_by_email: Dict[str, List[AuditEvent]] = {}
        self.audit_by_phone: Dict[str, List[AuditEvent]] = {}
        self.audit_by_email_hash: Dict[str, List[AuditEvent]] = {}

        for a in dataset.user_audit_log:
            self.audit_by_user_id.setdefault(a.user_id, []).append(a)
            if a.field_name == "email":
                if a.old_value_raw:
                    e_norm = normalize_email(a.old_value_raw)
                    if e_norm:
                        self.audit_by_email.setdefault(e_norm, []).append(a)
                if a.new_value_raw:
                    e_norm = normalize_email(a.new_value_raw)
                    if e_norm:
                        self.audit_by_email.setdefault(e_norm, []).append(a)
            elif a.field_name == "phone":
                if a.old_value_raw:
                    p_norm = normalize_phone(a.old_value_raw)
                    if p_norm:
                        self.audit_by_phone.setdefault(p_norm, []).append(a)
                if a.new_value_raw:
                    p_norm = normalize_phone(a.new_value_raw)
                    if p_norm:
                        self.audit_by_phone.setdefault(p_norm, []).append(a)
            elif a.field_name == "email_hash":
                if a.old_value_raw:
                    h_norm = a.old_value_raw.strip().lower()
                    if h_norm:
                        self.audit_by_email_hash.setdefault(h_norm, []).append(a)
                if a.new_value_raw:
                    h_norm = a.new_value_raw.strip().lower()
                    if h_norm:
                        self.audit_by_email_hash.setdefault(h_norm, []).append(a)


def resolve_request(
    case: DeletionRequest,
    dataset: Dataset,
    index: Optional[IdentityIndex] = None,
) -> Cluster:
    """
    Deterministically resolves all confirmed and probable identifiers for a single DeletionRequest.
    Follows decisions D1, D2, and D3.
    """
    if index is None:
        index = IdentityIndex(dataset)

    cluster = Cluster(case_id=case.case_id)

    seed_email_raw = case.email_raw
    seed_email_norm = case.email_norm or normalize_email(seed_email_raw) or seed_email_raw.strip().lower()

    initial_role = "unknown"
    if seed_email_norm in index.identities_by_email:
        initial_role = "current"
    elif seed_email_norm in index.audit_by_email:
        initial_role = "historical"

    seed_node = IdentifierNode(
        kind="email",
        value_raw=seed_email_raw,
        value_norm=seed_email_norm,
        role=initial_role,
        source=[case.source],
    )
    seed_node = cluster.add_node(seed_node)


    # Set of processed node keys to prevent infinite loops
    processed_node_keys: Set[Tuple[str, str]] = set()
    conflicted_emails: Set[str] = set()

    MAX_ITERATIONS = 20
    iteration = 0

    while iteration < MAX_ITERATIONS:
        iteration += 1
        nodes_to_process = [
            n for k, n in sorted(cluster.nodes.items()) if k not in processed_node_keys
        ]
        if not nodes_to_process:
            break

        for current_node in nodes_to_process:
            processed_node_keys.add(current_node.key)

            # ----------------------------------------------------
            # 1. Processing EMAIL nodes
            # ----------------------------------------------------
            if current_node.kind == "email":
                em = current_node.value_norm
                if em in conflicted_emails:
                    continue

                # Find all user_ids associated with this email
                # Check user_identities
                ident_matches = index.identities_by_email.get(em, [])
                audit_matches = index.audit_by_email.get(em, [])

                tied_user_ids: Set[str] = set()
                sources_by_user: Dict[str, SourceRef] = {}

                for i in ident_matches:
                    tied_user_ids.add(i.user_id)
                    sources_by_user[i.user_id] = i.source

                for a in audit_matches:
                    tied_user_ids.add(a.user_id)
                    if a.user_id not in sources_by_user:
                        sources_by_user[a.user_id] = a.source

                # Decision D2: An email tied to two different user_ids is a CONFLICT.
                if len(tied_user_ids) > 1:
                    conflicted_emails.add(em)
                    first_src = sources_by_user[sorted(tied_user_ids)[0]]
                    conflict_nodes = []
                    for uid in sorted(tied_user_ids):
                        uid_node = IdentifierNode(
                            kind="user_id",
                            value_raw=uid,
                            value_norm=uid,
                            role="unknown",
                            source=[sources_by_user[uid]],
                        )
                        conflict_nodes.append(uid_node)
                    cluster.conflicts.append(
                        Conflict(
                            conflict_type="EMAIL_CONFLICT",
                            details=f"Email '{em}' is tied to multiple distinct user_ids: {sorted(tied_user_ids)}",
                            nodes=[current_node] + conflict_nodes,
                            source=first_src,
                        )
                    )
                    # Stop expanding through this conflicted email
                    continue

                # Exactly one user_id tied: Add user_id as CONFIRMED (D3)
                if len(tied_user_ids) == 1:
                    uid = list(tied_user_ids)[0]
                    src = sources_by_user[uid]
                    uid_node = IdentifierNode(
                        kind="user_id",
                        value_raw=uid,
                        value_norm=uid,
                        role="current",
                        source=[src],
                    )
                    uid_node = cluster.add_node(uid_node)
                    cluster.add_link(
                        Link(
                            from_node=current_node,
                            to_node=uid_node,
                            strength="CONFIRMED",
                            reason_code="SHARED_USER_ID",
                            source=src,
                        )
                    )

                # Decision D1: Plus-addressing check
                # If current email has '+tag', find base email
                base_email = _strip_plus_tag(em)
                if base_email:
                    # Look up base email in identities or audit
                    base_idents = index.identities_by_email.get(base_email, [])
                    base_audits = index.audit_by_email.get(base_email, [])
                    if base_idents:
                        base_src = base_idents[0].source
                    elif base_audits:
                        base_src = base_audits[0].source
                    else:
                        base_src = current_node.source[0] if current_node.source else case.source

                    base_node = IdentifierNode(
                        kind="email",
                        value_raw=base_email,
                        value_norm=base_email,
                        role="unknown",
                        source=[base_src],
                    )
                    base_node = cluster.add_node(base_node)
                    cluster.add_link(
                        Link(
                            from_node=current_node,
                            to_node=base_node,
                            strength="PROBABLE",
                            reason_code="PLUS_ADDRESS_VARIANT",
                            source=base_src,
                        )
                    )

                # Check if base email matches any known plus variants in identities
                for known_em, idents in index.identities_by_email.items():
                    if _strip_plus_tag(known_em) == em:
                        var_src = idents[0].source
                        var_node = IdentifierNode(
                            kind="email",
                            value_raw=idents[0].email_raw,
                            value_norm=known_em,
                            role="unknown",
                            source=[var_src],
                        )
                        var_node = cluster.add_node(var_node)
                        cluster.add_link(
                            Link(
                                from_node=current_node,
                                to_node=var_node,
                                strength="PROBABLE",
                                reason_code="PLUS_ADDRESS_VARIANT",
                                source=var_src,
                            )
                        )

            # ----------------------------------------------------
            # 2. Processing USER_ID nodes
            # ----------------------------------------------------
            elif current_node.kind == "user_id":
                uid = current_node.value_norm

                # Pull current identity row for this user_id
                ident = index.identities_by_user_id.get(uid)
                if ident:
                    # Current email
                    if ident.email_norm:
                        e_node = IdentifierNode(
                            kind="email",
                            value_raw=ident.email_raw,
                            value_norm=ident.email_norm,
                            role="current",
                            source=[ident.source],
                        )
                        e_node = cluster.add_node(e_node)
                        cluster.add_link(
                            Link(
                                from_node=current_node,
                                to_node=e_node,
                                strength="CONFIRMED",
                                reason_code="SHARED_USER_ID",
                                source=ident.source,
                            )
                        )

                    # Current phone
                    if ident.phone_norm:
                        p_node = IdentifierNode(
                            kind="phone",
                            value_raw=ident.phone_raw,
                            value_norm=ident.phone_norm,
                            role="current",
                            source=[ident.source],
                        )
                        p_node = cluster.add_node(p_node)
                        cluster.add_link(
                            Link(
                                from_node=current_node,
                                to_node=p_node,
                                strength="CONFIRMED",
                                reason_code="SHARED_USER_ID",
                                source=ident.source,
                            )
                        )

                    # Current email_hash
                    if ident.email_hash:
                        h_node = IdentifierNode(
                            kind="email_hash",
                            value_raw=ident.email_hash,
                            value_norm=ident.email_hash.lower(),
                            role="current",
                            source=[ident.source],
                        )
                        h_node = cluster.add_node(h_node)
                        cluster.add_link(
                            Link(
                                from_node=current_node,
                                to_node=h_node,
                                strength="CONFIRMED",
                                reason_code="SHARED_USER_ID",
                                source=ident.source,
                            )
                        )

                # Pull all audit rows for this user_id
                user_audits = index.audit_by_user_id.get(uid, [])
                for a in user_audits:
                    if a.field_name in ("email", "phone", "email_hash"):
                        # Old value -> historical role
                        if a.old_value_raw:
                            if a.field_name == "email":
                                norm_val = normalize_email(a.old_value_raw) or a.old_value_raw.strip().lower()
                            elif a.field_name == "phone":
                                norm_val = normalize_phone(a.old_value_raw) or a.old_value_raw.strip()
                            else:
                                norm_val = a.old_value_raw.strip().lower()

                            hist_node = IdentifierNode(
                                kind=a.field_name,
                                value_raw=a.old_value_raw,
                                value_norm=norm_val,
                                role="historical",
                                source=[a.source],
                            )
                            hist_node = cluster.add_node(hist_node)
                            cluster.add_link(
                                Link(
                                    from_node=current_node,
                                    to_node=hist_node,
                                    strength="CONFIRMED",
                                    reason_code="AUDIT_OLD_NEW_SAME_USER",
                                    source=a.source,
                                )
                            )

                        # New value
                        if a.new_value_raw:
                            if a.field_name == "email":
                                norm_val = normalize_email(a.new_value_raw) or a.new_value_raw.strip().lower()
                            elif a.field_name == "phone":
                                norm_val = normalize_phone(a.new_value_raw) or a.new_value_raw.strip()
                            else:
                                norm_val = a.new_value_raw.strip().lower()

                            new_node = IdentifierNode(
                                kind=a.field_name,
                                value_raw=a.new_value_raw,
                                value_norm=norm_val,
                                role="current",
                                source=[a.source],
                            )
                            new_node = cluster.add_node(new_node)
                            cluster.add_link(
                                Link(
                                    from_node=current_node,
                                    to_node=new_node,
                                    strength="CONFIRMED",
                                    reason_code="AUDIT_OLD_NEW_SAME_USER",
                                    source=a.source,
                                )
                            )

            # ----------------------------------------------------
            # 3. Processing PHONE nodes (Decision D3: PROBABLE cross-user)
            # ----------------------------------------------------
            elif current_node.kind == "phone":
                p_norm = current_node.value_norm
                matched_idents = index.identities_by_phone.get(p_norm, [])
                for other_ident in matched_idents:
                    # Check if this user_id is already confirmed in cluster
                    uid_key = ("user_id", other_ident.user_id)
                    if uid_key not in cluster.nodes:
                        # Found matching phone with NO shared user_id -> PROBABLE
                        other_u_node = IdentifierNode(
                            kind="user_id",
                            value_raw=other_ident.user_id,
                            value_norm=other_ident.user_id,
                            role="unknown",
                            source=[other_ident.source],
                        )
                        other_u_node = cluster.add_node(other_u_node)
                        cluster.add_link(
                            Link(
                                from_node=current_node,
                                to_node=other_u_node,
                                strength="PROBABLE",
                                reason_code="PHONE_MATCH",
                                source=other_ident.source,
                            )
                        )

            # ----------------------------------------------------
            # 4. Processing EMAIL_HASH nodes (Decision D3: PROBABLE cross-user)
            # ----------------------------------------------------
            elif current_node.kind == "email_hash":
                h_norm = current_node.value_norm
                matched_idents = index.identities_by_email_hash.get(h_norm, [])
                for other_ident in matched_idents:
                    uid_key = ("user_id", other_ident.user_id)
                    if uid_key not in cluster.nodes:
                        # Matching hash with NO shared user_id -> PROBABLE
                        other_u_node = IdentifierNode(
                            kind="user_id",
                            value_raw=other_ident.user_id,
                            value_norm=other_ident.user_id,
                            role="unknown",
                            source=[other_ident.source],
                        )
                        other_u_node = cluster.add_node(other_u_node)
                        cluster.add_link(
                            Link(
                                from_node=current_node,
                                to_node=other_u_node,
                                strength="PROBABLE",
                                reason_code="EMAIL_HASH_MATCH",
                                source=other_ident.source,
                            )
                        )

    if iteration >= MAX_ITERATIONS:
        raise RuntimeError(
            f"Fixed-point iteration cap ({MAX_ITERATIONS}) reached while resolving case {case.case_id}"
        )

    return cluster


def resolve_all(
    dataset: Dataset,
    requests: Optional[List[DeletionRequest]] = None,
) -> Dict[str, Cluster]:
    """Resolves clusters for all deletion requests in the dataset deterministically."""
    index = IdentityIndex(dataset)
    clusters: Dict[str, Cluster] = {}

    target_requests = requests if requests is not None else dataset.deletion_requests
    # Sort deletion requests by case_id for strict determinism
    sorted_requests = sorted(target_requests, key=lambda r: r.case_id)
    for req in sorted_requests:
        cluster = resolve_request(req, dataset, index=index)
        clusters[req.case_id] = cluster

    return clusters


def build_identity_report(clusters: Dict[str, Cluster], dataset: Dataset) -> str:
    """Generates the Markdown identity report."""
    total_clusters = len(clusters)
    total_nodes = sum(len(c.nodes) for c in clusters.values())
    avg_cluster_size = (total_nodes / total_clusters) if total_clusters > 0 else 0.0

    strength_counts = Counter()
    reason_counts = Counter()
    total_conflicts = sum(len(c.conflicts) for c in clusters.values())
    all_open_questions: List[str] = []

    for c in clusters.values():
        for l in c.links:
            strength_counts[l.strength] += 1
            reason_counts[l.reason_code] += 1
        for q in c.open_questions:
            all_open_questions.append(f"{c.case_id}: {q}")

    report_lines = [
        "# NullTrace: Identity Resolution Report",
        "",
        "## Summary Statistics",
        f"- **Total Clusters Built**: {total_clusters}",
        f"- **Total Identifier Nodes**: {total_nodes}",
        f"- **Average Cluster Size**: {avg_cluster_size:.2f} nodes/cluster",
        f"- **Total Conflicts Detected**: {total_conflicts}",
        f"- **Total Open Questions**: {len(all_open_questions)}",
        "",
        "## Link Counts by Confidence Strength",
        f"- **CONFIRMED**: {strength_counts['CONFIRMED']}",
        f"- **PROBABLE**: {strength_counts['PROBABLE']}",
        f"- **UNRESOLVED**: {strength_counts['UNRESOLVED']}",
        "",
        "## Link Counts by Reason Code",
    ]
    for r_code, cnt in sorted(reason_counts.items()):
        report_lines.append(f"- **`{r_code}`**: {cnt}")

    report_lines.extend([
        "",
        "## Open Questions",
    ])
    if all_open_questions:
        for q in all_open_questions:
            report_lines.append(f"- {q}")
    else:
        report_lines.append("- None (all cases resolved cleanly without unhandled conditions).")


    return "\n".join(report_lines)

