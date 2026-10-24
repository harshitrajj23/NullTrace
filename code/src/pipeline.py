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
except ImportError:
    from src.loader import Dataset, load_dataset
    from src.identity import Cluster, resolve_all
    from src.resource_link import ActivitySubjectIndex, link_cluster_resources
    from src.ops import Step, sort_steps, validate_steps
    from src.grader_io import serialize_steps, write_output_csv

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


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NullTrace Baseline Pipeline")
    parser.add_argument("--data-dir", default="./dataset", help="Path to dataset directory")
    parser.add_argument(
        "--output",
        default="./build/nulltrace_baseline.csv",
        help="Path to write baseline output CSV (default: ./build/nulltrace_baseline.csv)",
    )
    args = parser.parse_args()

    print(f"Running baseline pipeline on {args.data_dir} -> {args.output}...")
    res = run_baseline_pipeline(data_dir=args.data_dir, output_path=args.output)
    counts = res["counts"]
    print("Baseline execution complete!")
    print(f"Total Requests: {counts['total_requests']}")
    print(f"NOT_APPLICABLE: {counts['not_applicable']}")
    print(f"INCOMPLETE: {counts['incomplete']}")
    print(f"  - with confidently linked findings: {counts['incomplete_with_findings']}")
    print(f"  - with insufficient evidence (empty findings): {counts['incomplete_insufficient_evidence']}")
    print(f"COMPLETE: {counts['complete']}")
    print(f"Total Steps Emitted: {counts['total_steps_emitted']}")
    print(f"Validation Failures: {counts['validation_failures']}")
    print(f"Output saved to: {res['output_path']}")


if __name__ == "__main__":
    main()
