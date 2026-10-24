"""code/src/resurrection_detector.py

Resurrection and Restore-Risk Detector for HackerRank Orchestrate: Ghost Data Still Exists.

Constructs a directed temporal flow graph from system_activity.csv and structured evidence:
- Identifies active data flows (sync connectors, replication pipelines) that can recreate data.
- Identifies unblocked restore risks from backup archives.
- Detects downstream recreation events (e.g. backup restore or sync repopulating downstream targets).
- Distinguishes observed facts from inferred multi-hop paths.
- Respects temporal boundaries: events <= audit_at determine state at audit; events > audit_at
  are explicitly flagged as POST_AUDIT recreation and never used as proof of prior state.
- Requires corroboration before asserting that data was recreated.
- Prevents attribution of unrelated system activity to deletion requests.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Standard library module 'code' conflict resolution
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if "code" in sys.modules and not hasattr(sys.modules["code"], "src"):
    del sys.modules["code"]

try:
    from code.src.models import DeletionRequest, SystemActivity
    from code.src.state_reconstruction import (
        EvidenceObservation,
        ResourceState,
        ensure_utc,
        parse_timestamp_to_utc,
    )
except ImportError:
    from src.models import DeletionRequest, SystemActivity
    from src.state_reconstruction import (
        EvidenceObservation,
        ResourceState,
        ensure_utc,
        parse_timestamp_to_utc,
    )

logger = logging.getLogger("nulltrace.resurrection_detector")


class RiskCategory(str, Enum):
    """Category of data resurrection or recreation risk."""
    ACTIVE_DATA_FLOW = "ACTIVE_DATA_FLOW"            # Continuous sync / connector active
    RESTORE_RISK = "RESTORE_RISK"                    # Backup archive with unblocked restore access
    REPOPULATED_DOWNSTREAM = "REPOPULATED_DOWNSTREAM"# Sync/restore actively repopulated downstream target
    SYNC_REPLICATION_RISK = "SYNC_REPLICATION_RISK"  # Sync from surviving source to deleted target


class FlowStatus(str, Enum):
    """Operational status of a flow or restore path."""
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    BLOCKED = "BLOCKED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class TimeRelation(str, Enum):
    """Temporal relationship of an event relative to case audit_at."""
    PRIOR_TO_AUDIT = "PRIOR_TO_AUDIT"
    AT_AUDIT = "AT_AUDIT"
    POST_AUDIT = "POST_AUDIT"


@dataclass
class FlowEdge:
    """An edge in the temporal flow graph representing a data or control pathway."""
    edge_id: str
    source_system: str
    target_system: str
    resource_id: str
    event_type: str
    timestamp: Optional[datetime]
    status: FlowStatus
    is_direct_observation: bool
    provenance_evidence_id: str
    source_path: str
    details: Dict[str, Any] = field(default_factory=dict)
    downstream_target_resource: Optional[str] = None


@dataclass
class ResurrectionRiskFinding:
    """An actionable finding detailing an active flow, restore risk, or recreation event."""
    case_id: str
    risk_category: RiskCategory
    source_system: str
    target_system: str
    implicated_resource: str
    downstream_resource: Optional[str]
    evidence_ids: List[str]
    event_times: List[datetime]
    time_relation: TimeRelation
    confidence: str                              # CONFIRMED, HIGH, UNCORROBORATED_CLAIM, SUSPECTED
    flow_status: FlowStatus
    reason: str
    unresolved_gaps: List[str] = field(default_factory=list)
    is_post_audit_resurrection: bool = False


class TemporalFlowGraph:
    """Directed temporal graph of systems, resources, and data propagation flows."""

    def __init__(self) -> None:
        self.edges: List[FlowEdge] = []
        self.edges_by_resource: Dict[str, List[FlowEdge]] = {}
        self.edges_by_source: Dict[str, List[FlowEdge]] = {}
        self.edges_by_target: Dict[str, List[FlowEdge]] = {}

    def add_edge(self, edge: FlowEdge) -> None:
        self.edges.append(edge)
        self.edges_by_resource.setdefault(edge.resource_id, []).append(edge)
        self.edges_by_source.setdefault(edge.source_system, []).append(edge)
        self.edges_by_target.setdefault(edge.target_system, []).append(edge)

    def get_edges_for_resource(self, resource_id: str) -> List[FlowEdge]:
        return self.edges_by_resource.get(resource_id, [])

    def find_multi_hop_paths(
        self,
        start_system: str,
        end_system: Optional[str] = None,
        max_hops: int = 3,
        visited: Optional[Set[str]] = None,
    ) -> List[List[FlowEdge]]:
        """Finds multi-hop propagation paths starting from start_system."""
        if visited is None:
            visited = set()
        if max_hops <= 0 or start_system in visited:
            return []

        visited.add(start_system)
        paths: List[List[FlowEdge]] = []

        for edge in self.edges_by_source.get(start_system, []):
            if end_system is None or edge.target_system == end_system:
                paths.append([edge])
            if edge.target_system not in visited:
                sub_paths = self.find_multi_hop_paths(
                    edge.target_system,
                    end_system=end_system,
                    max_hops=max_hops - 1,
                    visited=set(visited),
                )
                for sp in sub_paths:
                    paths.append([edge] + sp)

        return paths


def parse_downstream_repopulated_resource(details: str) -> Optional[str]:
    """Extracts downstream resource ID if details declare repopulation."""
    match = re.search(r"repopulated downstream resource\s+([a-zA-Z0-9_]+)", details, re.IGNORECASE)
    if match:
        return match.group(1).rstrip(".")
    return None


def determine_time_relation(
    event_time: Optional[datetime],
    audit_at: datetime,
) -> TimeRelation:
    """Classifies an event's time relative to audit_at."""
    if event_time is None:
        return TimeRelation.PRIOR_TO_AUDIT
    ev_dt = ensure_utc(event_time)
    au_dt = ensure_utc(audit_at)
    if ev_dt is None or au_dt is None:
        return TimeRelation.PRIOR_TO_AUDIT
    if ev_dt < au_dt:
        return TimeRelation.PRIOR_TO_AUDIT
    elif ev_dt == au_dt:
        return TimeRelation.AT_AUDIT
    else:
        return TimeRelation.POST_AUDIT


def build_temporal_flow_graph(
    activity_events: List[SystemActivity],
    direct_observations: Optional[List[EvidenceObservation]] = None,
) -> TemporalFlowGraph:
    """
    Constructs the TemporalFlowGraph using verified fields from system_activity.csv
    and direct evidence observations.
    """
    graph = TemporalFlowGraph()
    obs_list = direct_observations or []

    # 1. Add direct evidence observations as ground-truth edges
    for obs in obs_list:
        rid = obs.resource_id
        sys_id = obs.system_id or "unknown_system"
        det = obs.details or {}

        # Connector configurations (Data flows)
        if obs.collection == "connector_configurations":
            dest = det.get("destination", "downstream_target")
            enabled = det.get("enabled", True)
            st = FlowStatus.ACTIVE if enabled else FlowStatus.DISABLED
            edge = FlowEdge(
                edge_id=f"obs_{rid}_{obs.evidence_id}",
                source_system=sys_id,
                target_system=dest,
                resource_id=rid,
                event_type="CONNECTOR_CONFIG",
                timestamp=ensure_utc(obs.timestamp),
                status=st,
                is_direct_observation=True,
                provenance_evidence_id=obs.evidence_id,
                source_path=obs.source_path,
                details=det,
            )
            graph.add_edge(edge)

        # Backup catalog
        elif obs.collection == "backup_catalog":
            restore_allowed = det.get("restore_allowed", True)
            st = FlowStatus.ACTIVE if restore_allowed else FlowStatus.BLOCKED
            edge = FlowEdge(
                edge_id=f"obs_{rid}_{obs.evidence_id}",
                source_system=sys_id,
                target_system="restored_environment",
                resource_id=rid,
                event_type="BACKUP_CATALOG_ENTRY",
                timestamp=ensure_utc(obs.timestamp),
                status=st,
                is_direct_observation=True,
                provenance_evidence_id=obs.evidence_id,
                source_path=obs.source_path,
                details=det,
            )
            graph.add_edge(edge)

        # Operational record history for flows / backups
        elif "operational_record_history" in str(obs.collection):
            res = det.get("result", "").upper()
            st = FlowStatus.UNKNOWN
            if res in ("ACTIVE", "FOUND"):
                st = FlowStatus.ACTIVE
            elif res == "DISABLED":
                st = FlowStatus.DISABLED
            elif res == "BLOCKED":
                st = FlowStatus.BLOCKED

            edge = FlowEdge(
                edge_id=f"obs_op_{rid}_{obs.evidence_id}",
                source_system=det.get("system", sys_id),
                target_system="operational_store",
                resource_id=rid,
                event_type=f"OPERATIONAL_{det.get('record_type', 'RECORD')}",
                timestamp=ensure_utc(obs.timestamp),
                status=st,
                is_direct_observation=True,
                provenance_evidence_id=obs.evidence_id,
                source_path=obs.source_path,
                details=det,
            )
            graph.add_edge(edge)

    # 2. Add system_activity events
    for act in activity_events:
        rid = act.resource_id
        if not rid:
            continue

        downstream_res = parse_downstream_repopulated_resource(act.details)
        res_upper = act.reported_result.upper()

        st = FlowStatus.UNKNOWN
        if act.event_type in ("CHECK_DATA_FLOW", "CHECK_RESTORE_ACCESS"):
            st = FlowStatus.ACTIVE if res_upper == "SUCCESS" else FlowStatus.FAILED
        elif act.event_type == "DISABLE_DATA_FLOW":
            st = FlowStatus.DISABLED if res_upper == "SUCCESS" else FlowStatus.ACTIVE
        elif act.event_type == "BLOCK_RESTORE":
            st = FlowStatus.BLOCKED if res_upper == "SUCCESS" else FlowStatus.ACTIVE
        elif act.event_type in ("RESTORE_BACKUP", "SYNC_RECORD"):
            st = FlowStatus.EXECUTED if res_upper == "SUCCESS" else FlowStatus.FAILED

        edge = FlowEdge(
            edge_id=act.activity_id,
            source_system=act.source_system,
            target_system=act.target_system,
            resource_id=rid,
            event_type=act.event_type,
            timestamp=ensure_utc(act.event_time),
            status=st,
            is_direct_observation=False,
            provenance_evidence_id=act.activity_id,
            source_path="system_activity.csv",
            details={"reported_result": act.reported_result, "details": act.details},
            downstream_target_resource=downstream_res,
        )
        graph.add_edge(edge)

    return graph


def detect_case_resurrection_risks(
    case_id: str,
    audit_at: datetime,
    linked_resource_ids: Set[str],
    graph: TemporalFlowGraph,
    direct_observations_index: Optional[Dict[str, List[EvidenceObservation]]] = None,
) -> List[ResurrectionRiskFinding]:
    """
    Evaluates resurrection and restore risks for a deletion request:
    - Analyzes only resources confirmed linked to this case.
    - Evaluates flow status at audit_at cutoff.
    - Explicitly detects post-audit recreation events without using them as proof of earlier state.
    - Requires corroboration before asserting that data was recreated.
    """
    findings: List[ResurrectionRiskFinding] = []
    audit_dt = ensure_utc(audit_at)
    obs_index = direct_observations_index or {}

    for rid in sorted(linked_resource_ids):
        edges = graph.get_edges_for_resource(rid)
        if not edges:
            continue

        # Sort edges chronologically
        edges.sort(key=lambda e: ensure_utc(e.timestamp) or datetime.min.replace(tzinfo=timezone.utc))

        # Separate pre-audit and post-audit edges
        pre_audit_edges = [e for e in edges if e.timestamp and ensure_utc(e.timestamp) <= audit_dt]
        post_audit_edges = [e for e in edges if e.timestamp and ensure_utc(e.timestamp) > audit_dt]

        # -------------------------------------------------------------
        # 1. Active Data Flow Risks (data_flow_...)
        # -------------------------------------------------------------
        if rid.startswith("data_flow_"):
            # Check status as of audit_at
            if pre_audit_edges:
                latest_edge = pre_audit_edges[-1]
                t_rel = determine_time_relation(latest_edge.timestamp, audit_at)

                # If flow was active at audit_at
                if latest_edge.status == FlowStatus.ACTIVE:
                    findings.append(
                        ResurrectionRiskFinding(
                            case_id=case_id,
                            risk_category=RiskCategory.ACTIVE_DATA_FLOW,
                            source_system=latest_edge.source_system,
                            target_system=latest_edge.target_system,
                            implicated_resource=rid,
                            downstream_resource=latest_edge.downstream_target_resource,
                            evidence_ids=[latest_edge.provenance_evidence_id],
                            event_times=[ensure_utc(latest_edge.timestamp)] if latest_edge.timestamp else [],
                            time_relation=t_rel,
                            confidence="CONFIRMED" if latest_edge.is_direct_observation else "HIGH",
                            flow_status=FlowStatus.ACTIVE,
                            reason=f"Data flow {rid} confirmed active at audit cutoff; can replicate or copy user data",
                        )
                    )
                elif latest_edge.status == FlowStatus.DISABLED:
                    # Flow safely disabled before audit_at
                    logger.debug(f"{case_id}: data flow {rid} confirmed disabled prior to audit")

            # Check for repopulation events (SYNC_RECORD repopulating downstream)
            for edge in edges:
                if edge.downstream_target_resource and "repopulated" in edge.details.get("details", "").lower():
                    t_rel = determine_time_relation(edge.timestamp, audit_at)
                    is_post = (t_rel == TimeRelation.POST_AUDIT)

                    # Corroboration check
                    has_corroboration = (edge.status == FlowStatus.EXECUTED)
                    conf = "CONFIRMED" if has_corroboration else "UNCORROBORATED_CLAIM"
                    gaps = [] if has_corroboration else ["Logged sync repopulation lacked independent downstream proof"]

                    findings.append(
                        ResurrectionRiskFinding(
                            case_id=case_id,
                            risk_category=RiskCategory.REPOPULATED_DOWNSTREAM,
                            source_system=edge.source_system,
                            target_system=edge.target_system,
                            implicated_resource=rid,
                            downstream_resource=edge.downstream_target_resource,
                            evidence_ids=[edge.provenance_evidence_id],
                            event_times=[ensure_utc(edge.timestamp)] if edge.timestamp else [],
                            time_relation=t_rel,
                            confidence=conf,
                            flow_status=edge.status,
                            reason=f"Active connector {rid} repopulated downstream resource {edge.downstream_target_resource}"
                                   + (" [POST-AUDIT EVENT]" if is_post else ""),
                            unresolved_gaps=gaps,
                            is_post_audit_resurrection=is_post,
                        )
                    )

        # -------------------------------------------------------------
        # 2. Restore Risks (backup_...)
        # -------------------------------------------------------------
        elif rid.startswith("backup_"):
            if pre_audit_edges:
                latest_edge = pre_audit_edges[-1]
                t_rel = determine_time_relation(latest_edge.timestamp, audit_at)

                if latest_edge.status == FlowStatus.ACTIVE:
                    findings.append(
                        ResurrectionRiskFinding(
                            case_id=case_id,
                            risk_category=RiskCategory.RESTORE_RISK,
                            source_system=latest_edge.source_system,
                            target_system=latest_edge.target_system,
                            implicated_resource=rid,
                            downstream_resource=latest_edge.downstream_target_resource,
                            evidence_ids=[latest_edge.provenance_evidence_id],
                            event_times=[ensure_utc(latest_edge.timestamp)] if latest_edge.timestamp else [],
                            time_relation=t_rel,
                            confidence="CONFIRMED" if latest_edge.is_direct_observation else "HIGH",
                            flow_status=FlowStatus.ACTIVE,
                            reason=f"Backup archive {rid} has unblocked restore access at audit cutoff; can recreate deleted data",
                        )
                    )

            # Check for RESTORE_BACKUP repopulation events
            for edge in edges:
                if edge.event_type == "RESTORE_BACKUP":
                    t_rel = determine_time_relation(edge.timestamp, audit_at)
                    is_post = (t_rel == TimeRelation.POST_AUDIT)

                    # Corroboration: reported_result SUCCESS with downstream resource specified
                    is_success = (edge.status == FlowStatus.EXECUTED)
                    has_corrob = is_success and bool(edge.downstream_target_resource)
                    conf = "CONFIRMED" if has_corrob else "UNCORROBORATED_CLAIM"
                    gaps = [] if has_corrob else ["Logged restore attempt lacked corroborating downstream evidence"]

                    findings.append(
                        ResurrectionRiskFinding(
                            case_id=case_id,
                            risk_category=RiskCategory.REPOPULATED_DOWNSTREAM,
                            source_system=edge.source_system,
                            target_system=edge.target_system,
                            implicated_resource=rid,
                            downstream_resource=edge.downstream_target_resource,
                            evidence_ids=[edge.provenance_evidence_id],
                            event_times=[ensure_utc(edge.timestamp)] if edge.timestamp else [],
                            time_relation=t_rel,
                            confidence=conf,
                            flow_status=edge.status,
                            reason=f"Restore operation from archive {rid} repopulated downstream resource {edge.downstream_target_resource or 'unspecified'}"
                                   + (" [POST-AUDIT RESURRECTION]" if is_post else ""),
                            unresolved_gaps=gaps,
                            is_post_audit_resurrection=is_post,
                        )
                    )

        # -------------------------------------------------------------
        # 3. Active Sync from Surviving Source to Target (account_... / profile)
        # -------------------------------------------------------------
        elif rid.startswith("account_") or rid.startswith("user_"):
            # If the account profile has active sync edges to search or analytics
            for edge in pre_audit_edges:
                if edge.event_type in ("SYNC_RECORD", "INDEX_RECORD", "REFRESH_CACHE") and edge.status == FlowStatus.EXECUTED:
                    findings.append(
                        ResurrectionRiskFinding(
                            case_id=case_id,
                            risk_category=RiskCategory.SYNC_REPLICATION_RISK,
                            source_system=edge.source_system,
                            target_system=edge.target_system,
                            implicated_resource=rid,
                            downstream_resource=edge.downstream_target_resource,
                            evidence_ids=[edge.provenance_evidence_id],
                            event_times=[ensure_utc(edge.timestamp)] if edge.timestamp else [],
                            time_relation=determine_time_relation(edge.timestamp, audit_at),
                            confidence="HIGH",
                            flow_status=FlowStatus.ACTIVE,
                            reason=f"Active replication flow {edge.event_type} from {edge.source_system} to {edge.target_system} propagates {rid}",
                        )
                    )

    # Deterministic sorting of findings: by time_relation, risk_category, implicated_resource
    findings.sort(key=lambda f: (f.time_relation.value, f.risk_category.value, f.implicated_resource))
    return findings
