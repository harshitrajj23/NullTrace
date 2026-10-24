"""
NullTrace: JSON Record-Level & Activity-to-Record Bridge Diagnostic Linker.

Implements Step I diagnostic:
- Answer-Key Isolation: Candidate links are built strictly from participant-facing
  evidence files without reading sample_output.csv.
- Re-evaluates JSON evidence by grouping tokens by logical JSON object/record
  rather than single-line text regex.
- Tests Activity-to-Record bridge links.
- Evaluates the 73 unlinked sample expected pairs after candidate generation.
"""

import csv
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

import sys

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

# Universal shapes
USER_ID_PATTERN = re.compile(r"^user_\d+$")
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_PATTERN = re.compile(r"^\+?[0-9\s-]{7,20}$")
HASH_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
RESOURCE_PATTERN = re.compile(r"^[a-z_]+_\d+$")

EXCLUDED_FILES = {"sample_output.csv", "output.csv"}
EXCLUDED_PATHS = ["code/evaluation", "code/docs"]


def is_path_excluded(fpath: str) -> bool:
    norm = os.path.normpath(fpath).replace("\\", "/")
    fname = os.path.basename(norm)
    if fname in EXCLUDED_FILES:
        return True
    for excl in EXCLUDED_PATHS:
        if excl in norm:
            return True
    return False


def normalize_email(val: str) -> str:
    val = val.strip().lower()
    if "@" in val:
        local, domain = val.split("@", 1)
        if "+" in local:
            local = local.split("+", 1)[0]
        return f"{local}@{domain}"
    return val


def normalize_phone(val: str) -> str:
    return re.sub(r"[^\d]", "", val)


@dataclass
class JsonRecord:
    file_name: str
    record_index: int
    record_type: str
    json_path: str
    data: Dict[str, Any]


def walk_key_paths_and_types(data: Any, prefix: str = "") -> List[Tuple[str, str]]:
    """Lists all key paths and primitive value types inside a JSON object."""
    results = []
    if isinstance(data, dict):
        for k, v in data.items():
            curr = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                results.extend(walk_key_paths_and_types(v, curr))
            else:
                results.append((curr, type(v).__name__))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            curr = f"{prefix}[{i}]"
            if isinstance(item, (dict, list)):
                results.extend(walk_key_paths_and_types(item, curr))
            else:
                results.append((curr, type(item).__name__))
    else:
        results.append((prefix or "$", type(data).__name__))
    return results


def extract_all_json_records(data: Any, file_name: str) -> List[JsonRecord]:
    """Recursively extracts all logical records from JSON data."""
    records: List[JsonRecord] = []
    rec_counter = 0

    def traverse(obj: Any, path: str, current_type: str):
        nonlocal rec_counter
        if isinstance(obj, dict):
            # If the dict contains a resource_id or data record indicators, treat as record
            is_record = "resource_id" in obj or "customer_reference" in obj or "subject_reference" in obj
            rtype = obj.get("record_type") or obj.get("collection") or obj.get("system") or current_type

            if is_record:
                rec_counter += 1
                records.append(
                    JsonRecord(
                        file_name=file_name,
                        record_index=rec_counter,
                        record_type=rtype,
                        json_path=path,
                        data=obj,
                    )
                )

            # Recurse into nested structures
            for k, v in obj.items():
                child_path = f"{path}.{k}" if path else k
                traverse(v, child_path, k if isinstance(v, (dict, list)) else rtype)

        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                child_path = f"{path}[{i}]"
                traverse(item, child_path, current_type)

    traverse(data, "$", "root")
    return records


def find_record_cooccurrences(
    records: List[JsonRecord],
) -> List[Dict[str, Any]]:
    """
    Extracts all (identifier, resource_id) co-occurrences within each JSON record.
    """
    candidates: List[Dict[str, Any]] = []

    for rec in records:
        rids: List[Tuple[str, str]] = []
        ids: List[Tuple[str, str, str]] = []

        def walk_vals(obj: Any, path: str):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    walk_vals(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    walk_vals(v, f"{path}[{i}]")
            elif isinstance(obj, str):
                val = obj.strip()
                # Check resource_id pattern
                if RESOURCE_PATTERN.match(val) and not val.startswith("user_"):
                    rids.append((path, val))
                elif USER_ID_PATTERN.match(val):
                    ids.append((path, val, "user_id"))
                elif EMAIL_PATTERN.match(val):
                    ids.append((path, normalize_email(val), "email"))
                elif HASH_PATTERN.match(val):
                    ids.append((path, val.lower(), "email_hash"))
                elif PHONE_PATTERN.match(val) and any(c.isdigit() for c in val) and sum(c.isdigit() for c in val) >= 7:
                    ids.append((path, normalize_phone(val), "phone"))

        walk_vals(rec.data, rec.json_path)

        for path_id, val_id, kind_id in ids:
            for path_res, val_res in rids:
                candidates.append(
                    {
                        "source_file": rec.file_name,
                        "record_index": rec.record_index,
                        "record_type": rec.record_type,
                        "json_path_id": path_id,
                        "identifier_value": val_id,
                        "identifier_type": kind_id,
                        "resource_id": val_res,
                        "json_path_resource": path_res,
                        "reason_code": "RECORD_COOCCURRENCE",
                        "bridge_resource_id": "",
                        "activity_id": "",
                    }
                )

    return candidates


def find_activity_bridge_candidates(
    record_candidates: List[Dict[str, Any]],
    data_dir: str = "./dataset",
) -> List[Dict[str, Any]]:
    """
    Step 4: For each resource_id in system_activity.csv that also appears in a JSON record,
    checks if that record carries an identifier.
    Connects subject to bridged resource if the activity row relates two resource IDs.
    Does not chain more than one bridge hop.
    """
    activity_path = os.path.join(data_dir, "system_activity.csv")
    if not os.path.isfile(activity_path):
        return []

    res_word_pattern = re.compile(r"\b([a-z_]+_\d+)\b")
    activity_edges = []

    with open(activity_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            main_r = r["resource_id"]
            matches = set(res_word_pattern.findall(r["details"])) - {main_r}
            for m in matches:
                activity_edges.append((main_r, m, r["activity_id"]))

    bridge_candidates: List[Dict[str, Any]] = []
    seen = set()

    for cand in record_candidates:
        r_json = cand["resource_id"]
        for m1, m2, act_id in activity_edges:
            target_res = None
            if r_json == m1:
                target_res = m2
            elif r_json == m2:
                target_res = m1

            if target_res:
                key = (cand["identifier_value"], target_res, r_json, act_id)
                if key not in seen:
                    seen.add(key)
                    bridge_candidates.append(
                        {
                            "source_file": cand["source_file"],
                            "record_index": cand["record_index"],
                            "record_type": cand["record_type"],
                            "json_path_id": cand["json_path_id"],
                            "identifier_value": cand["identifier_value"],
                            "identifier_type": cand["identifier_type"],
                            "resource_id": target_res,
                            "json_path_resource": cand["json_path_resource"],
                            "reason_code": "BRIDGE_VIA_RESOURCE",
                            "bridge_resource_id": r_json,
                            "activity_id": act_id,
                        }
                    )

    return bridge_candidates


def run_json_record_inventory(
    data_dir: str = "./dataset",
) -> Tuple[Dict[str, Any], List[JsonRecord]]:
    """Runs Step 2 JSON Record Inventory across dataset/evidence/."""
    inventory_summary: Dict[str, Any] = {
        "files_scanned": 0,
        "parse_failures": [],
        "file_details": {},
        "total_records": 0,
    }

    all_records: List[JsonRecord] = []
    evidence_dir = os.path.join(data_dir, "evidence")

    for root, dirs, files in os.walk(evidence_dir):
        for f in sorted(files):
            if not f.endswith(".json"):
                continue
            fpath = os.path.join(root, f)
            if is_path_excluded(fpath):
                continue

            rel_name = os.path.relpath(fpath, data_dir).replace("\\", "/")
            inventory_summary["files_scanned"] += 1

            try:
                with open(fpath, "r", encoding="utf-8") as fp:
                    content = fp.read().strip()
                # Check top-level structure
                if content.startswith("["):
                    struct_type = "array"
                elif content.startswith("{"):
                    struct_type = "object"
                else:
                    struct_type = "lines of objects"

                data = json.loads(content)
                records = extract_all_json_records(data, rel_name)
                all_records.extend(records)

                # Key paths sample from first record if any
                key_paths = walk_key_paths_and_types(data) if records else []

                inventory_summary["file_details"][rel_name] = {
                    "structure_type": struct_type,
                    "record_count": len(records),
                    "sample_key_paths_count": len(key_paths),
                }
                inventory_summary["total_records"] += len(records)
            except Exception as e:
                inventory_summary["parse_failures"].append({"file": rel_name, "error": str(e)})

    return inventory_summary, all_records


def write_candidate_table(
    candidates: List[Dict[str, Any]],
    output_path: str = "./code/evaluation/record_cooccurrence.csv",
) -> None:
    """Writes record_cooccurrence.csv to disk BEFORE answer-key comparison."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fields = [
        "source_file",
        "record_index",
        "record_type",
        "json_path_id",
        "identifier_value",
        "identifier_type",
        "resource_id",
        "json_path_resource",
        "reason_code",
        "bridge_resource_id",
        "activity_id",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for cand in candidates:
            writer.writerow(cand)


def evaluate_73_misses(
    all_candidates: List[Dict[str, Any]],
    data_dir: str = "./dataset",
) -> Dict[str, Any]:
    """
    Step 5: Strictly executed AFTER candidate table is written to disk.
    Reads sample_output.csv to test the 73 unlinked expected pairs.
    """
    from code.evaluation.subject_resource_scan import scan_evidence_files, score_sample_comparison
    from code.src.identity import resolve_request
    from code.src.loader import load_dataset

    # 1. Get baseline line-level results to isolate the 73 misses
    file_statuses, cooccurrences, all_found_rids = scan_evidence_files(data_dir)
    line_scoring = score_sample_comparison(cooccurrences, data_dir)

    missed_line_pairs: List[Tuple[str, str]] = []
    for cid, data in line_scoring["per_case_breakdown"].items():
        for rid in data["not_linkable"]:
            missed_line_pairs.append((cid, rid))

    dataset = load_dataset(data_dir)
    sample_clusters = {req.case_id: resolve_request(req, dataset) for req in dataset.sample_deletion_requests}
    cluster_ids = {
        req.case_id: {n.value_norm for n in cluster.nodes.values()}
        for req, cluster in zip(dataset.sample_deletion_requests, sample_clusters.values())
    }

    # Read all expected pairs
    sample_output_path = os.path.join(data_dir, "sample_output.csv")
    expected_by_case: Dict[str, Set[str]] = {}
    with open(sample_output_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = row["case_id"]
            steps = json.loads(row["steps_json"])
            expected_by_case[cid] = set(s["resource_id"] for s in steps if s.get("resource_id"))

    # Separate candidates by reason code
    record_cooc_by_id: Dict[str, Set[str]] = {}
    bridge_by_id: Dict[str, Set[str]] = {}
    record_cand_pairs: Set[Tuple[str, str]] = set()

    for cand in all_candidates:
        val = cand["identifier_value"]
        rid = cand["resource_id"]
        rcode = cand["reason_code"]
        if rcode == "RECORD_COOCCURRENCE":
            record_cooc_by_id.setdefault(val, set()).add(rid)
        elif rcode == "BRIDGE_VIA_RESOURCE":
            bridge_by_id.setdefault(val, set()).add(rid)

    # Calculate extra candidates for sample cases
    for cid, c_ids in cluster_ids.items():
        for c_val in c_ids:
            for rid in record_cooc_by_id.get(c_val, set()):
                record_cand_pairs.add((cid, rid))

    extra_sample_pairs = [p for p in record_cand_pairs if p[1] not in expected_by_case.get(p[0], set())]

    # Evaluate each of the 73 missed pairs
    recovered_record: List[Tuple[str, str]] = []
    recovered_bridge: List[Tuple[str, str]] = []
    still_unlinked: List[Tuple[str, str]] = []

    for cid, rid in missed_line_pairs:
        c_ids = cluster_ids.get(cid, set())
        has_rec = any(rid in record_cooc_by_id.get(c_val, set()) for c_val in c_ids)
        has_bridge = any(rid in bridge_by_id.get(c_val, set()) for c_val in c_ids)

        if has_rec:
            recovered_record.append((cid, rid))
        elif has_bridge:
            recovered_bridge.append((cid, rid))
        else:
            still_unlinked.append((cid, rid))

    # Halves split
    sorted_cases = sorted(list(expected_by_case.keys()))
    odd_cases = [c for i, c in enumerate(sorted_cases) if i % 2 == 0]
    even_cases = [c for i, c in enumerate(sorted_cases) if i % 2 == 1]

    odd_misses = [p for p in missed_line_pairs if p[0] in odd_cases]
    even_misses = [p for p in missed_line_pairs if p[0] in even_cases]

    odd_rec = [p for p in recovered_record if p[0] in odd_cases]
    even_rec = [p for p in recovered_record if p[0] in even_cases]

    odd_bridge = [p for p in recovered_bridge if p[0] in odd_cases]
    even_bridge = [p for p in recovered_bridge if p[0] in even_cases]

    odd_unlinked = [p for p in still_unlinked if p[0] in odd_cases]
    even_unlinked = [p for p in still_unlinked if p[0] in even_cases]

    return {
        "total_misses": len(missed_line_pairs),
        "recovered_by_record": recovered_record,
        "recovered_by_bridge": recovered_bridge,
        "still_unlinked": still_unlinked,
        "odd_half": {
            "total_misses": len(odd_misses),
            "recovered_record": len(odd_rec),
            "recovered_bridge": len(odd_bridge),
            "still_unlinked": len(odd_unlinked),
        },
        "even_half": {
            "total_misses": len(even_misses),
            "recovered_record": len(even_rec),
            "recovered_bridge": len(even_bridge),
            "still_unlinked": len(even_unlinked),
        },
        "extra_candidates": extra_sample_pairs,
    }


def main():
    data_dir = "./dataset"
    print("Step 2: JSON Record Inventory...")
    inv_summary, all_records = run_json_record_inventory(data_dir)
    print(f"Files scanned: {inv_summary['files_scanned']}, Total records: {inv_summary['total_records']}, Failures: {len(inv_summary['parse_failures'])}")

    print("Step 3: Extracting Record-Level Co-occurrences...")
    record_cands = find_record_cooccurrences(all_records)
    print(f"RECORD_COOCCURRENCE candidates: {len(record_cands)}")

    print("Step 4: Extracting Activity-to-Record Bridge Candidates...")
    bridge_cands = find_activity_bridge_candidates(record_cands, data_dir)
    print(f"BRIDGE_VIA_RESOURCE candidates: {len(bridge_cands)}")

    all_candidates = record_cands + bridge_cands
    csv_path = "./code/evaluation/record_cooccurrence.csv"
    print(f"Writing {csv_path}...")
    write_candidate_table(all_candidates, csv_path)

    print("Step 5: Evaluating against 73 Misses in sample_output.csv (Answer Key Isolation)...")
    eval_res = evaluate_73_misses(all_candidates, data_dir)
    print(f"Overall (73 total): Recovered by Record={len(eval_res['recovered_by_record'])}, Bridge={len(eval_res['recovered_by_bridge'])}, Unlinked={len(eval_res['still_unlinked'])}")
    print(f"Odd Half: {eval_res['odd_half']}")
    print(f"Even Half: {eval_res['even_half']}")
    print(f"Extra candidates on sample: {len(eval_res['extra_candidates'])}")


if __name__ == "__main__":
    main()
