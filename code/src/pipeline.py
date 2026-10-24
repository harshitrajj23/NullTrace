"""code/src/pipeline.py

Baseline Pipeline for HackerRank Orchestrate: Ghost Data Still Exists.
Produces a conservative, fully-validated baseline result for all 518 evaluation requests:
- Deterministic non-deletion classifier: flags explicit inquiries as NOT_APPLICABLE with steps_json = [].
- Conservative deletion handling: returns INCOMPLETE for all deletion requests.
- Evidence-grounded findings: emits FINDING steps only for resources with confirmed
  evidence links from system activity (activity_id) or JSON evidence manifests (file_id).
- Never reads sample_output.csv or output.csv.
- Validates every generated step through code.src.ops.validate_steps.
"""

import csv
import json
import logging
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
    from code.src.loader import Dataset, load_dataset
    from code.src.identity import Cluster, resolve_all
    from code.src.resource_link import ActivitySubjectIndex, link_cluster_resources
    from code.src.ops import Step, sort_steps, validate_steps
    from code.src.grader_io import serialize_steps, write_output_csv
    from code.src.evidence_coverage import CorpusCoverageTracker, CorpusCoverageSummary
    from code.src.evidence_extraction import ExtractedObservation
    from code.src.vision_extraction import GeminiVisionExtractor, VisionConfig
    from code.src.local_vision_extraction import AppleVisionExtractor, LocalVisionConfig
    from code.src.state_reconstruction import (
        reconstruct_resource_state,
        parse_timestamp_to_utc,
        ensure_utc,
        ResourceState,
    )
    from code.src.rule_engine import assess_resource_policy
    from code.src.resurrection_detector import (
        build_temporal_flow_graph,
        detect_case_resurrection_risks,
    )
    from code.src.planner import plan_case
    from code.src.completion_validator import validate_case_completion
except ImportError:
    from src.loader import Dataset, load_dataset
    from src.identity import Cluster, resolve_all
    from src.resource_link import ActivitySubjectIndex, link_cluster_resources
    from src.ops import Step, sort_steps, validate_steps
    from src.grader_io import serialize_steps, write_output_csv
    from src.evidence_coverage import CorpusCoverageTracker, CorpusCoverageSummary
    from src.evidence_extraction import ExtractedObservation
    from src.vision_extraction import GeminiVisionExtractor, VisionConfig
    from src.local_vision_extraction import AppleVisionExtractor, LocalVisionConfig
    from src.state_reconstruction import (
        reconstruct_resource_state,
        parse_timestamp_to_utc,
        ensure_utc,
        ResourceState,
    )
    from src.rule_engine import assess_resource_policy
    from src.resurrection_detector import (
        build_temporal_flow_graph,
        detect_case_resurrection_risks,
    )
    from src.planner import plan_case
    from src.completion_validator import validate_case_completion

logger = logging.getLogger("nulltrace.pipeline")


def is_non_deletion_inquiry(text: str) -> bool:
    """
    General deterministic rule to identify clear non-deletion inquiries:
    - Access / GDPR Art. 15 information requests
    - Rectification / correction requests
    - Data portability / export downloads without account closure
    - Marketing / newsletter opt-out requests
    - Support / login assistance inquiries
    - Explicit non-deletion assertions ('not asking for deletion', 'leave account active', etc.)
    Does not infer status from reported_status.
    """
    t = text.strip().lower()

    explicit_non_deletion = [
        "not asking for deletion",
        "leave the account active",
        "keep the account as it is",
        "do not close the account",
        "without removing any of my records",
        "marketing lists only",
        "information request, not a request to erase",
        "leave my profile and purchase history in place",
        "want to continue using the service",
        "don't delete or change anything",
        "do not delete or change anything",
    ]
    for phrase in explicit_non_deletion:
        if phrase in t:
            return True

    non_del_starters = [
        "can you tell me what personal information you hold",
        "could you send me a copy of the information held",
        "i can't access my profile and need help resetting",
        "i need a copy of last year's invoices",
        "i'd like to download my account information in a portable format",
        "my surname is misspelled on the account",
        "please change the email address used for this account",
        "the mobile number on my profile is out of date",
        "please stop the promotional emails",
        "please remove me from marketing lists",
    ]
    for starter in non_del_starters:
        if t.startswith(starter):
            return True

    return False


def get_system_id_for_resource(resource_id: str) -> str:
    """Canonical mapping from resource prefix to target system ID."""
    if resource_id.startswith("audit_record_") or resource_id.startswith("security_"):
        return "security_service"
    if resource_id.startswith("data_flow_"):
        return "integration_service"

    prefix = resource_id.split("_")[0]
    mapping = {
        "account": "account_service",
        "analytics": "analytics_platform",
        "backup": "backup_service",
        "export": "export_service",
        "search": "search_service",
        "support": "support_platform",
        "tombstone": "identity_service",
    }
    return mapping.get(prefix, "unknown_system")


def get_finding_op_and_state(resource_id: str) -> Tuple[str, str]:
    """Returns the compliant (operation, state) pair for a resource in the FINDING phase."""
    if resource_id.startswith("data_flow_"):
        return ("REPORT_ACTIVE_DATA_FLOW", "ACTIVE")
    if resource_id.startswith("backup_"):
        return ("REPORT_RESTORE_RISK", "ACTIVE")
    return ("REPORT_REMAINING_RECORD", "PRESENT")


def load_evidence_manifest_mapping(data_dir: str) -> Tuple[Dict[str, str], Set[str]]:
    """
    Loads evidence_files.csv to map relative file_path -> file_id,
    and returns all known evidence IDs.
    """
    manifest_path = os.path.join(data_dir, "evidence_files.csv")
    path_to_file_id: Dict[str, str] = {}
    known_evidence_ids: Set[str] = set()

    if os.path.isfile(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                fid = r["file_id"]
                fpath = r["file_path"].replace("\\", "/")
                path_to_file_id[fpath] = fid
                known_evidence_ids.add(fid)

    return path_to_file_id, known_evidence_ids


def load_record_cooccurrences(
    record_cooccurrence_path: str,
) -> Dict[str, List[Dict[str, str]]]:
    """
    Loads the diagnostic record_cooccurrence.csv table mapping
    normalized identifier -> list of candidate dictionaries.
    """
    id_to_cands: Dict[str, List[Dict[str, str]]] = {}
    if os.path.isfile(record_cooccurrence_path):
        with open(record_cooccurrence_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("reason_code") == "RECORD_COOCCURRENCE":
                    val = row["identifier_value"]
                    id_to_cands.setdefault(val, []).append(row)
    return id_to_cands


def run_baseline_pipeline(
    data_dir: str = "./dataset",
    output_path: str = "./build/nulltrace_baseline.csv",
    record_cooccurrence_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes the conservative 518-case baseline pipeline:
    - Loads dataset without reading sample_output.csv or output.csv.
    - Classifies requests into NOT_APPLICABLE vs INCOMPLETE.
    - Emits FINDING steps only with valid evidence IDs.
    - Validates every generated row against ops.validate_steps.
    - Writes output to build/nulltrace_baseline.csv (preserving root output.csv template).
    """
    # Safety: ensure destination does not overwrite root output.csv or dataset/output.csv
    abs_out = os.path.abspath(output_path)
    root_output = os.path.abspath(os.path.join(_repo_root, "output.csv"))
    dataset_output = os.path.abspath(os.path.join(_repo_root, "dataset", "output.csv"))
    if abs_out in (root_output, dataset_output):
        raise ValueError(f"Refusing to overwrite evaluation template output.csv at: {abs_out}")

    dataset = load_dataset(data_dir=data_dir)
    clusters = resolve_all(dataset)
    act_index = ActivitySubjectIndex(dataset.system_activity)

    path_to_file_id, known_evidence_ids = load_evidence_manifest_mapping(data_dir)

    # Add activity IDs and audit IDs to known evidence IDs
    for act in dataset.system_activity:
        known_evidence_ids.add(act.activity_id)
    for aud in dataset.user_audit_log:
        known_evidence_ids.add(aud.audit_id)

    # Locate record_cooccurrence.csv
    if record_cooccurrence_path is None:
        default_cooc = os.path.join(_repo_root, "code", "evaluation", "record_cooccurrence.csv")
        record_cooccurrence_path = default_cooc if os.path.isfile(default_cooc) else ""

    id_to_record_cands = (
        load_record_cooccurrences(record_cooccurrence_path) if record_cooccurrence_path else {}
    )

    results: List[Dict[str, Any]] = []
    counts = {
        "total_requests": len(dataset.deletion_requests),
        "not_applicable": 0,
        "incomplete": 0,
        "incomplete_with_findings": 0,
        "incomplete_insufficient_evidence": 0,
        "complete": 0,
        "total_steps_emitted": 0,
        "validation_failures": 0,
    }

    # Sort requests strictly by case_id
    sorted_requests = sorted(dataset.deletion_requests, key=lambda r: r.case_id)

    for req in sorted_requests:
        cid = req.case_id

        # 1. Deterministic Non-Deletion Check
        if is_non_deletion_inquiry(req.request_text):
            status = "NOT_APPLICABLE"
            steps: List[Step] = []
            counts["not_applicable"] += 1
        else:
            status = "INCOMPLETE"
            counts["incomplete"] += 1

            cluster = clusters[cid]
            c_vals = {node.value_norm for node in cluster.nodes.values()}

            # Deduplicate findings by resource_id: mapping rid -> (system_id, evidence_id)
            res_to_finding: Dict[str, Tuple[str, str]] = {}

            # A. Activity Links (activity_id supplies evidence_id)
            act_links = link_cluster_resources(cluster, dataset, act_index)
            for act in act_links:
                rid = act.resource_id
                if rid not in res_to_finding:
                    sys_id = act.system_id or get_system_id_for_resource(rid)
                    res_to_finding[rid] = (sys_id, act.activity_id)

            # B. JSON Record Co-occurrences (manifest file_id supplies evidence_id)
            for val in c_vals:
                for jcand in id_to_record_cands.get(val, []):
                    rid = jcand["resource_id"]
                    if rid not in res_to_finding:
                        rel_path = jcand["source_file"].replace("\\", "/")
                        file_id = path_to_file_id.get(rel_path, "")
                        if file_id:
                            sys_id = get_system_id_for_resource(rid)
                            res_to_finding[rid] = (sys_id, file_id)

            raw_steps: List[Step] = []
            for rid, (sys_id, ev_id) in res_to_finding.items():
                op, state = get_finding_op_and_state(rid)
                raw_steps.append(
                    Step(
                        step_no=0,
                        phase="FINDING",
                        system_id=sys_id,
                        resource_id=rid,
                        operation=op,
                        state=state,
                        evidence_id=ev_id,
                    )
                )

            steps = sort_steps(raw_steps)
            counts["total_steps_emitted"] += len(steps)

            if steps:
                counts["incomplete_with_findings"] += 1
            else:
                counts["incomplete_insufficient_evidence"] += 1

        # Strict validation
        errs = validate_steps(steps, status, known_evidence_ids)
        if errs:
            counts["validation_failures"] += 1
            logger.error(f"Validation failure on {cid} ({status}): {errs}")
            raise ValueError(f"Step validation failed for {cid}: {errs}")

        steps_json = serialize_steps(steps)
        results.append(
            {
                "case_id": cid,
                "deletion_status": status,
                "steps_json": steps_json,
            }
        )

    # Output writing
    os.makedirs(os.path.dirname(abs_out), exist_ok=True)
    write_output_csv(results, abs_out)

    return {
        "output_path": abs_out,
        "counts": counts,
        "results": results,
    }


def run_integrated_pipeline(
    data_dir: str = "./dataset",
    output_path: str = "./build/nulltrace_integrated.csv",
    vision_cache_dir: Optional[str] = None,
    apple_vision_cache_dir: Optional[str] = None,
    requests: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """
    Executes the fully integrated NullTrace pipeline across all evaluation requests:
    1. Loads dataset and resolves identity clusters with historical tracking.
    2. Extracts and indexes multi-modality evidence across all 94 files (SQL, Logs, Records, Text, PDF, Screenshots).
    3. Reconstructs temporal resource states at each request's audit_at cutoff.
    4. Evaluates deletion_rules.csv across all relevant resources (retained records, tombstones, replicas).
    5. Detects resurrection risks (active sync flows, backup restore paths).
    6. Strictly validates completion; produces verification steps for COMPLETE,
       ordered remediation plan for INCOMPLETE, and empty steps for NOT_APPLICABLE.
    7. Validates all outputs against ops.validate_steps and writes to output_path.
    """
    # Safety: ensure destination does not overwrite root output.csv or dataset/output.csv
    abs_out = os.path.abspath(output_path)
    root_output = os.path.abspath(os.path.join(_repo_root, "output.csv"))
    dataset_output = os.path.abspath(os.path.join(_repo_root, "dataset", "output.csv"))
    if abs_out in (root_output, dataset_output):
        raise ValueError(f"Refusing to overwrite evaluation template output.csv at: {abs_out}")

    # 1. Dataset loading & Identity resolution
    dataset = load_dataset(data_dir=data_dir)
    target_requests = requests if requests is not None else dataset.deletion_requests
    clusters = resolve_all(dataset, requests=target_requests)
    act_index = ActivitySubjectIndex(dataset.system_activity)

    # 2. Evidence extraction across all modalities
    tracker = CorpusCoverageTracker(data_dir=data_dir)
    coverage_summary = tracker.extract_corpus()
    all_obs: List[ExtractedObservation] = list(coverage_summary.all_observations)

    # Load cached screenshot observations (strictly offline)
    v_cache = vision_cache_dir or os.path.join(_repo_root, "build", "cache", "vision")
    av_cache = apple_vision_cache_dir or os.path.join(_repo_root, "build", "cache", "apple_vision")

    # A. Gemini pilot cache (evidence_04)
    try:
        gemini_extractor = GeminiVisionExtractor(
            config=VisionConfig(enabled=False, cache_dir=v_cache)
        )
        obs_04 = gemini_extractor.extract_file("evidence_04")
        all_obs.extend(obs_04)
    except Exception as e:
        logger.warning(f"Could not load cached pilot evidence_04: {e}")

    # B. Apple Vision cache for remaining screenshots
    manifest_path = os.path.join(data_dir, "evidence_files.csv")
    manifest_pngs: Dict[str, Dict[str, str]] = {}
    if os.path.isfile(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["file_path"].endswith(".png"):
                    manifest_pngs[r["file_id"]] = r

    apple_extractor = AppleVisionExtractor(
        config=LocalVisionConfig(cache_dir=av_cache),
        repo_root=_repo_root,
    )
    for fid, r in sorted(manifest_pngs.items()):
        if fid != "evidence_04":
            try:
                obs_png = apple_extractor.extract_file(fid, r["file_path"], r["origin"], r.get("captured_at"))
                all_obs.extend(obs_png)
            except Exception as e:
                logger.warning(f"Could not load cached Apple Vision for {fid}: {e}")

    # 3. Index observations and system activity
    obs_by_res: Dict[str, List[ExtractedObservation]] = {}
    obs_by_ident: Dict[str, List[ExtractedObservation]] = {}
    resource_evidence_map: Dict[str, Set[str]] = {}

    for obs in all_obs:
        ev_id = obs.evidence_id or obs.file_id
        if obs.resource_id:
            obs_by_res.setdefault(obs.resource_id, []).append(obs)
            if ev_id:
                resource_evidence_map.setdefault(obs.resource_id, set()).add(ev_id)
        for _, val in obs.associated_identifiers.items():
            if val:
                obs_by_ident.setdefault(val, []).append(obs)
                if obs.resource_id and ev_id:
                    resource_evidence_map.setdefault(obs.resource_id, set()).add(ev_id)

    activity_by_res: Dict[str, List[Any]] = {}
    for act in dataset.system_activity:
        if act.resource_id:
            activity_by_res.setdefault(act.resource_id, []).append(act)
            resource_evidence_map.setdefault(act.resource_id, set()).add(act.activity_id)

    # Compile authoritative known evidence IDs
    path_to_file_id, known_evidence_ids = load_evidence_manifest_mapping(data_dir)
    for act in dataset.system_activity:
        known_evidence_ids.add(act.activity_id)
    for aud in dataset.user_audit_log:
        known_evidence_ids.add(aud.audit_id)

    # 4. Temporal flow graph construction
    flow_evidence_obs = [o.to_evidence_observation() for o in all_obs if o.to_evidence_observation()]
    flow_graph = build_temporal_flow_graph(dataset.system_activity, flow_evidence_obs)

    # 5. Case-by-case execution
    results: List[Dict[str, Any]] = []
    counts = {
        "total_requests": len(target_requests),
        "not_applicable": 0,
        "incomplete": 0,
        "complete": 0,
        "total_steps_emitted": 0,
        "validation_failures": 0,
    }

    sorted_requests = sorted(target_requests, key=lambda r: r.case_id)

    for req in sorted_requests:
        cid = req.case_id
        audit_dt = ensure_utc(req.audit_at)

        # A. Non-deletion check
        if is_non_deletion_inquiry(req.request_text):
            status = "NOT_APPLICABLE"
            steps: List[Step] = []
            counts["not_applicable"] += 1
        else:
            cluster = clusters[cid]
            c_vals = {node.value_norm for node in cluster.nodes.values()}

            # B. Candidate resource discovery
            candidate_rids: Set[str] = set()

            # (1) From system activity
            act_links = link_cluster_resources(cluster, dataset, act_index)
            for act in act_links:
                candidate_rids.add(act.resource_id)

            # (2) From extracted evidence observations matching any cluster identifier
            for val in c_vals:
                for obs in obs_by_ident.get(val, []):
                    if obs.resource_id:
                        candidate_rids.add(obs.resource_id)

            # C. Temporal state reconstruction for all candidate resources
            policy_assessments: Dict[str, Any] = {}
            for rid in sorted(candidate_rids):
                dir_obs = [o.to_evidence_observation() for o in obs_by_res.get(rid, []) if o.to_evidence_observation()]
                acts = activity_by_res.get(rid, [])
                recon = reconstruct_resource_state(
                    resource_id=rid,
                    audit_at=audit_dt,
                    direct_observations=dir_obs,
                    activity_events=acts,
                )
                coll = dir_obs[0].collection if dir_obs else None
                assess = assess_resource_policy(recon, dataset.deletion_rules, collection=coll)
                policy_assessments[rid] = assess

            # D. Resurrection risk detection
            flow_risks = detect_case_resurrection_risks(
                case_id=cid,
                audit_at=audit_dt,
                linked_resource_ids=set(candidate_rids),
                graph=flow_graph,
            )

            # E. Completion validation
            decision = validate_case_completion(
                case_id=cid,
                is_non_deletion=False,
                policy_assessments=policy_assessments,
                flow_risks=flow_risks,
                identity_cluster=cluster,
                known_evidence_ids=known_evidence_ids,
                resource_evidence_map=resource_evidence_map,
            )

            if decision.is_complete:
                status = "COMPLETE"
                steps = decision.steps
                counts["complete"] += 1
            else:
                status = "INCOMPLETE"
                counts["incomplete"] += 1
                plan = plan_case(
                    case_id=cid,
                    is_non_deletion=False,
                    policy_assessments=policy_assessments,
                    flow_risks=flow_risks,
                    known_evidence_ids=known_evidence_ids,
                )
                steps = plan.steps

        counts["total_steps_emitted"] += len(steps)

        # F. Strict step validation
        errs = validate_steps(steps, status, known_evidence_ids)
        if errs:
            counts["validation_failures"] += 1
            logger.error(f"Validation failure on {cid} ({status}): {errs}")
            raise ValueError(f"Step validation failed for {cid}: {errs}")

        steps_json = serialize_steps(steps)
        results.append(
            {
                "case_id": cid,
                "deletion_status": status,
                "steps_json": steps_json,
            }
        )

    # 6. Output writing
    os.makedirs(os.path.dirname(abs_out), exist_ok=True)
    write_output_csv(results, abs_out)

    return {
        "output_path": abs_out,
        "counts": counts,
        "results": results,
        "coverage_summary": coverage_summary,
        "total_observations": len(all_obs),
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NullTrace Pipeline")
    parser.add_argument("--data-dir", default="./dataset", help="Path to dataset directory")
    parser.add_argument(
        "--output",
        default="./build/nulltrace_integrated.csv",
        help="Path to write output CSV (default: ./build/nulltrace_integrated.csv)",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        default=False,
        help="Run conservative baseline pipeline instead of integrated pipeline",
    )
    args = parser.parse_args()

    if args.baseline:
        print(f"Running baseline pipeline on {args.data_dir} -> {args.output}...")
        res = run_baseline_pipeline(data_dir=args.data_dir, output_path=args.output)
    else:
        print(f"Running integrated pipeline on {args.data_dir} -> {args.output}...")
        res = run_integrated_pipeline(data_dir=args.data_dir, output_path=args.output)

    counts = res["counts"]
    print("Execution complete!")
    print(f"Total Requests: {counts['total_requests']}")
    print(f"NOT_APPLICABLE: {counts.get('not_applicable', 0)}")
    print(f"INCOMPLETE: {counts.get('incomplete', 0)}")
    print(f"COMPLETE: {counts.get('complete', 0)}")
    print(f"Total Steps Emitted: {counts['total_steps_emitted']}")
    print(f"Validation Failures: {counts['validation_failures']}")
    print(f"Output saved to: {res['output_path']}")


if __name__ == "__main__":
    main()
