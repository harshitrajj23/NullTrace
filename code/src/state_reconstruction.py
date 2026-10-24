"""code/src/state_reconstruction.py

State Reconstruction Module for HackerRank Orchestrate: Ghost Data Still Exists.

Reconstructs the ground-truth state of system resources at each case's audit_at cutoff:
- Gathers directly observed evidence (from evidence file snapshots and operational histories)
  and relevant activity events.
- Reconstructs the best-supported state at audit_at, respecting event timestamps.
- Distinguishes: PRESENT, ABSENT, REDACTED, ANONYMIZED, ACTIVE, DISABLED, BLOCKED, UNKNOWN.
- Tracks provenance: evidence_id, source_path, timestamp, is_direct.
- Strictly ignores events and evidence captured after audit_at.
- Treats reported_result alone as an uncorroborated claim (never assumed successful without proof).
- Marks conflicting observations or inadequate evidence as UNKNOWN.
"""

import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

# Standard library module 'code' conflict resolution
import sys
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if "code" in sys.modules and not hasattr(sys.modules["code"], "src"):
    del sys.modules["code"]

try:
    from code.src.models import EvidenceFile, SourceRef, SystemActivity
    from code.src.normalize import normalize_timestamp
except ImportError:
    from src.models import EvidenceFile, SourceRef, SystemActivity
    from src.normalize import normalize_timestamp

logger = logging.getLogger("nulltrace.state_reconstruction")


class ResourceState(str, Enum):
    """Ground-truth operational and data state of a resource."""
    PRESENT = "PRESENT"          # Record exists; prohibited data or exposed PII remains
    ABSENT = "ABSENT"            # Record has been confirmed deleted / does not exist
    REDACTED = "REDACTED"        # Record retained with prohibited direct identifiers removed
    ANONYMIZED = "ANONYMIZED"    # Record retained but irreversibly unlinked from subject
    ACTIVE = "ACTIVE"            # Active process flow or unblocked backup restore risk
    DISABLED = "DISABLED"        # Process flow confirmed disabled
    BLOCKED = "BLOCKED"          # Backup restore access confirmed blocked
    UNKNOWN = "UNKNOWN"          # Unobserved, contradictory, or uncorroborated claim


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensures a datetime is timezone-aware in UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_timestamp_to_utc(ts_str: Optional[str]) -> Optional[datetime]:
    """Parses an ISO timestamp string to UTC datetime."""
    if not ts_str:
        return None
    try:
        dt, _ = normalize_timestamp(ts_str)
        return ensure_utc(dt)
    except Exception:
        # Fallback to standard fromisoformat
        clean = ts_str.strip()
        if clean.endswith("Z") or clean.endswith("z"):
            clean = clean[:-1] + "+00:00"
        try:
            return ensure_utc(datetime.fromisoformat(clean))
        except Exception:
            return None


@dataclass
class EvidenceObservation:
    """A direct factual observation extracted from evidence files or system events."""
    resource_id: str
    observed_state: ResourceState
    timestamp: Optional[datetime]
    evidence_id: str
    source_path: str
    is_direct: bool
    details: Dict[str, Any] = field(default_factory=dict)
    collection: Optional[str] = None
    system_id: Optional[str] = None


@dataclass
class ReconstructedState:
    """Reconstructed state of a resource at a specific audit_at cutoff."""
    resource_id: str
    state: ResourceState
    provenance_evidence_id: str
    source_path: str
    timestamp: Optional[datetime]
    is_direct: bool
    rationale: str
    raw_details: Dict[str, Any] = field(default_factory=dict)
    has_conflict: bool = False
    is_uncorroborated_claim: bool = False
    post_audit_events_count: int = 0


def load_all_evidence_observations(data_dir: str = "./dataset") -> Dict[str, List[EvidenceObservation]]:
    """
    Scans dataset/evidence_files.csv and parses all structured JSON snapshot records under
    dataset/evidence/records/*.json to extract direct observations for all resources.
    """
    manifest_path = os.path.join(data_dir, "evidence_files.csv")
    path_to_meta: Dict[str, Tuple[str, Optional[datetime]]] = {}

    if os.path.isfile(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                fid = r["file_id"]
                fpath = r["file_path"].replace("\\", "/")
                dt = parse_timestamp_to_utc(r.get("captured_at"))
                path_to_meta[fpath] = (fid, dt)

    obs_by_res: Dict[str, List[EvidenceObservation]] = {}
    records_dir = os.path.join(data_dir, "evidence", "records")

    if not os.path.isdir(records_dir):
        return obs_by_res

    for fname in sorted(os.listdir(records_dir)):
        if not fname.endswith(".json"):
            continue
        full_path = os.path.join(records_dir, fname)
        rel_path = f"evidence/records/{fname}"
        fid, file_cap_time = path_to_meta.get(rel_path, ("", None))

        try:
            with open(full_path, "r", encoding="utf-8") as jf:
                data = json.load(jf)
        except Exception as e:
            logger.warning(f"Failed to parse evidence JSON {full_path}: {e}")
            continue

        snapshots = data.get("snapshots", [])
        for snap in snapshots:
            snap_time = parse_timestamp_to_utc(snap.get("captured_at")) or file_cap_time
            store = snap.get("data_store")
            coll = snap.get("collection")
            records = snap.get("records", [])

            for rec in records:
                rid = rec.get("resource_id")
                if not rid:
                    continue

                state = ResourceState.UNKNOWN
                details = dict(rec)

                # 1. Operational record histories
                if "operational_record_history" in str(coll):
                    res = rec.get("result", "").upper()
                    rec_time = parse_timestamp_to_utc(rec.get("recorded_at")) or snap_time
                    if res == "FOUND":
                        state = ResourceState.PRESENT
                    elif res == "NOT_FOUND":
                        state = ResourceState.ABSENT
                    elif res == "ANONYMIZED":
                        state = ResourceState.ANONYMIZED
                    elif res == "IDENTIFIABLE":
                        state = ResourceState.PRESENT
                    elif res == "REDACTED":
                        state = ResourceState.REDACTED
                    elif res == "ACTIVE":
                        state = ResourceState.ACTIVE
                    elif res == "DISABLED":
                        state = ResourceState.DISABLED
                    elif res == "BLOCKED":
                        state = ResourceState.BLOCKED
                    else:
                        state = ResourceState.UNKNOWN
                # 2. Connector configurations (Data flows)
                elif coll == "connector_configurations":
                    enabled = rec.get("enabled", True)
                    state = ResourceState.ACTIVE if enabled else ResourceState.DISABLED
                    rec_time = snap_time
                # 3. Backup catalogs
                elif coll == "backup_catalog":
                    restore_allowed = rec.get("restore_allowed", True)
                    state = ResourceState.ACTIVE if restore_allowed else ResourceState.BLOCKED
                    rec_time = snap_time
                # 4. Deleted customer references (Account tombstones)
                elif coll == "deleted_customer_references":
                    has_direct_pii = any(
                        bool(rec.get(k)) for k in ("name", "email", "phone", "email_hash")
                    )
                    state = ResourceState.PRESENT if has_direct_pii else ResourceState.REDACTED
                    rec_time = snap_time
                # 5. Customer analytics reports
                elif coll == "customer_analytics_reports":
                    is_identifiable = any(
                        bool(rec.get(k)) for k in ("user_id", "email", "phone", "email_hash")
                    )
                    state = ResourceState.PRESENT if is_identifiable else ResourceState.ANONYMIZED
                    rec_time = snap_time
                # 6. Standard record collections
                else:
                    state = ResourceState.PRESENT
                    rec_time = snap_time

                obs = EvidenceObservation(
                    resource_id=rid,
                    observed_state=state,
                    timestamp=rec_time,
                    evidence_id=fid,
                    source_path=rel_path,
                    is_direct=True,
                    details=details,
                    collection=coll,
                    system_id=store,
                )
                obs_by_res.setdefault(rid, []).append(obs)

    return obs_by_res


def index_system_activity_by_resource(
    activities: List[SystemActivity],
) -> Dict[str, List[SystemActivity]]:
    """Indexes system activity events by resource_id."""
    res_map: Dict[str, List[SystemActivity]] = {}
    for act in activities:
        if act.resource_id:
            res_map.setdefault(act.resource_id, []).append(act)
    return res_map


def reconstruct_resource_state(
    resource_id: str,
    audit_at: datetime,
    direct_observations: Optional[List[EvidenceObservation]] = None,
    activity_events: Optional[List[SystemActivity]] = None,
) -> ReconstructedState:
    """
    Reconstructs the ground-truth state of a single resource at audit_at cutoff:
    - Filters observations and activities strictly to those at or before audit_at.
    - Tracks and counts any events occurring after audit_at without using them as proof.
    - Treats reported_result alone as an uncorroborated claim.
    - Reconciles direct evidence observations chronologically.
    - Resolves conflicting observations at the same timestamp to UNKNOWN.
    """
    audit_dt = ensure_utc(audit_at)
    all_obs = direct_observations or []
    all_acts = activity_events or []

    # Filter strictly at or before audit_at
    valid_obs: List[EvidenceObservation] = []
    post_audit_obs_count = 0
    for obs in all_obs:
        obs_dt = ensure_utc(obs.timestamp)
        if obs_dt is not None:
            if obs_dt <= audit_dt:
                valid_obs.append(obs)
            else:
                post_audit_obs_count += 1
        else:
            # Undated observation cannot be validated as prior to audit_at
            post_audit_obs_count += 1

    valid_acts: List[SystemActivity] = []
    post_audit_acts_count = 0
    for act in all_acts:
        act_dt = ensure_utc(act.event_time)
        if act_dt is not None:
            if act_dt <= audit_dt:
                valid_acts.append(act)
            else:
                post_audit_acts_count += 1
        else:
            post_audit_acts_count += 1

    total_post_audit = post_audit_obs_count + post_audit_acts_count

    # Case 1: Direct evidence observations exist at or before audit_at
    if valid_obs:
        # Sort chronologically
        valid_obs.sort(key=lambda o: ensure_utc(o.timestamp) or datetime.min.replace(tzinfo=timezone.utc))
        latest_time = ensure_utc(valid_obs[-1].timestamp)
        latest_obs_group = [o for o in valid_obs if ensure_utc(o.timestamp) == latest_time]

        # Check for conflicts at latest timestamp
        states_at_latest = {o.observed_state for o in latest_obs_group}
        if len(states_at_latest) > 1:
            return ReconstructedState(
                resource_id=resource_id,
                state=ResourceState.UNKNOWN,
                provenance_evidence_id=latest_obs_group[0].evidence_id,
                source_path=latest_obs_group[0].source_path,
                timestamp=latest_time,
                is_direct=True,
                rationale=f"Conflicting direct observations at {latest_time}: {sorted(s.value for s in states_at_latest)}",
                raw_details={"observations": [o.details for o in latest_obs_group]},
                has_conflict=True,
                post_audit_events_count=total_post_audit,
            )

        best_direct_obs = latest_obs_group[0]
        direct_state = best_direct_obs.observed_state

        # Check if an activity event occurred AFTER this direct observation (and <= audit_at)
        later_acts = [
            a for a in valid_acts
            if ensure_utc(a.event_time) and ensure_utc(a.event_time) > (latest_time or datetime.min.replace(tzinfo=timezone.utc))
        ]
        if later_acts:
            later_acts.sort(key=lambda a: ensure_utc(a.event_time) or datetime.min.replace(tzinfo=timezone.utc))
            latest_act = later_acts[-1]

            # If activity claims SUCCESS on destructive/policy action without subsequent corroboration
            if latest_act.event_type in (
                "DELETE_RECORD", "DISABLE_DATA_FLOW", "BLOCK_RESTORE", "REDACT_RECORD", "ANONYMIZE_RECORD"
            ) and latest_act.reported_result == "SUCCESS":
                return ReconstructedState(
                    resource_id=resource_id,
                    state=ResourceState.UNKNOWN,
                    provenance_evidence_id=latest_act.activity_id,
                    source_path="system_activity.csv",
                    timestamp=ensure_utc(latest_act.event_time),
                    is_direct=False,
                    rationale=f"Uncorroborated activity claim: {latest_act.event_type} reported SUCCESS but lacks corroborating post-event evidence",
                    raw_details={"activity": latest_act.details},
                    is_uncorroborated_claim=True,
                    post_audit_events_count=total_post_audit,
                )

            # If activity reports FAILED on destructive action, original state persisted
            if latest_act.reported_result == "FAILED":
                return ReconstructedState(
                    resource_id=resource_id,
                    state=direct_state,
                    provenance_evidence_id=latest_act.activity_id,
                    source_path="system_activity.csv",
                    timestamp=ensure_utc(latest_act.event_time),
                    is_direct=False,
                    rationale=f"Attempted {latest_act.event_type} reported FAILED; prior state {direct_state.value} confirmed persisting",
                    raw_details={"activity": latest_act.details},
                    post_audit_events_count=total_post_audit,
                )

            # If activity is a check/refresh confirming active state
            if latest_act.event_type == "CHECK_DATA_FLOW":
                return ReconstructedState(
                    resource_id=resource_id,
                    state=ResourceState.ACTIVE,
                    provenance_evidence_id=latest_act.activity_id,
                    source_path="system_activity.csv",
                    timestamp=ensure_utc(latest_act.event_time),
                    is_direct=False,
                    rationale="Connector check confirmed data flow remains active",
                    raw_details={"activity": latest_act.details},
                    post_audit_events_count=total_post_audit,
                )
            if latest_act.event_type == "CHECK_RESTORE_ACCESS":
                return ReconstructedState(
                    resource_id=resource_id,
                    state=ResourceState.ACTIVE,
                    provenance_evidence_id=latest_act.activity_id,
                    source_path="system_activity.csv",
                    timestamp=ensure_utc(latest_act.event_time),
                    is_direct=False,
                    rationale="Restore-access check confirmed backup remains restorable",
                    raw_details={"activity": latest_act.details},
                    post_audit_events_count=total_post_audit,
                )

        # Direct observation remains the authoritative state
        return ReconstructedState(
            resource_id=resource_id,
            state=direct_state,
            provenance_evidence_id=best_direct_obs.evidence_id,
            source_path=best_direct_obs.source_path,
            timestamp=latest_time,
            is_direct=True,
            rationale=f"Direct observation from {best_direct_obs.collection or best_direct_obs.source_path}",
            raw_details=best_direct_obs.details,
            post_audit_events_count=total_post_audit,
        )

    # Case 2: No direct observations, but system activity events exist at or before audit_at
    if valid_acts:
        valid_acts.sort(key=lambda a: ensure_utc(a.event_time) or datetime.min.replace(tzinfo=timezone.utc))
        latest_act = valid_acts[-1]
        act_time = ensure_utc(latest_act.event_time)

        # Uncorroborated success claims
        if latest_act.event_type in (
            "DELETE_RECORD", "DISABLE_DATA_FLOW", "BLOCK_RESTORE", "REDACT_RECORD", "ANONYMIZE_RECORD"
        ) and latest_act.reported_result == "SUCCESS":
            return ReconstructedState(
                resource_id=resource_id,
                state=ResourceState.UNKNOWN,
                provenance_evidence_id=latest_act.activity_id,
                source_path="system_activity.csv",
                timestamp=act_time,
                is_direct=False,
                rationale=f"Uncorroborated {latest_act.event_type} SUCCESS claim without direct evidence",
                raw_details={"activity": latest_act.details},
                is_uncorroborated_claim=True,
                post_audit_events_count=total_post_audit,
            )

        # Confirmed active flows and restore checks
        if latest_act.event_type == "CHECK_DATA_FLOW":
            return ReconstructedState(
                resource_id=resource_id,
                state=ResourceState.ACTIVE,
                provenance_evidence_id=latest_act.activity_id,
                source_path="system_activity.csv",
                timestamp=act_time,
                is_direct=False,
                rationale="Activity event confirmed data flow remains active",
                raw_details={"activity": latest_act.details},
                post_audit_events_count=total_post_audit,
            )

        if latest_act.event_type == "CHECK_RESTORE_ACCESS":
            return ReconstructedState(
                resource_id=resource_id,
                state=ResourceState.ACTIVE,
                provenance_evidence_id=latest_act.activity_id,
                source_path="system_activity.csv",
                timestamp=act_time,
                is_direct=False,
                rationale="Activity event confirmed restore access remains active",
                raw_details={"activity": latest_act.details},
                post_audit_events_count=total_post_audit,
            )

        # Standard indexing, sync, export, retain events confirm presence
        if latest_act.event_type in (
            "INDEX_RECORD", "SYNC_RECORD", "UPDATE_RECORD", "CREATE_EXPORT", "REFRESH_CACHE", "RETAIN_RECORD", "SEND_EMAIL"
        ):
            return ReconstructedState(
                resource_id=resource_id,
                state=ResourceState.PRESENT,
                provenance_evidence_id=latest_act.activity_id,
                source_path="system_activity.csv",
                timestamp=act_time,
                is_direct=False,
                rationale=f"Activity event {latest_act.event_type} confirms resource was processed and present",
                raw_details={"activity": latest_act.details},
                post_audit_events_count=total_post_audit,
            )

        # Fallback for other unverified activity events
        return ReconstructedState(
            resource_id=resource_id,
            state=ResourceState.UNKNOWN,
            provenance_evidence_id=latest_act.activity_id,
            source_path="system_activity.csv",
            timestamp=act_time,
            is_direct=False,
            rationale=f"Activity {latest_act.event_type} ({latest_act.reported_result}) requires evidence verification",
            raw_details={"activity": latest_act.details},
            post_audit_events_count=total_post_audit,
        )

    # Case 3: Completely unobserved at or before audit_at
    return ReconstructedState(
        resource_id=resource_id,
        state=ResourceState.UNKNOWN,
        provenance_evidence_id="",
        source_path="",
        timestamp=None,
        is_direct=False,
        rationale="No observations or activity recorded at or before audit_at",
        raw_details={},
        post_audit_events_count=total_post_audit,
    )


def reconstruct_case_states(
    case_id: str,
    audit_at: datetime,
    resource_ids: List[str],
    evidence_obs_index: Dict[str, List[EvidenceObservation]],
    activity_index: Dict[str, List[SystemActivity]],
) -> Dict[str, ReconstructedState]:
    """Reconstructs the state for all resources linked to a deletion case at audit_at."""
    case_states: Dict[str, ReconstructedState] = {}
    for rid in sorted(resource_ids):
        obs_list = evidence_obs_index.get(rid, [])
        act_list = activity_index.get(rid, [])
        state = reconstruct_resource_state(
            resource_id=rid,
            audit_at=audit_at,
            direct_observations=obs_list,
            activity_events=act_list,
        )
        case_states[rid] = state
    return case_states
