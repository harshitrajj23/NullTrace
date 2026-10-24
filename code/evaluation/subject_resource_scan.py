"""code/evaluation/subject_resource_scan.py

Evidence content scanner and subject-to-resource co-occurrence analyzer.
Operates with strict Answer-Key Isolation:
- Never reads sample_output.csv, output.csv, or files under code/evaluation/ or code/docs/ to build links.
- Uses native parsers for .sql, .log, .txt, .csv, and .json.
- Uses pypdf for .pdf.
- Classifies files as TEXT_OK, PDF_NO_TEXT, IMAGE_ONLY, BINARY, or ERROR.
- Identifies co-occurring subject identifiers (user_id, email, phone, email_hash) and resource_ids.
- Scoring function reads sample_output.csv strictly after scanning is complete for diagnostic evaluation.
"""

from collections import Counter
import csv
from dataclasses import dataclass, field
import glob
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
    from code.src.loader import load_dataset, Dataset
    from code.src.identity import resolve_request
    from code.src.normalize import normalize_email, normalize_phone
except ImportError:
    from src.loader import load_dataset, Dataset
    from src.identity import resolve_request
    from src.normalize import normalize_email, normalize_phone

try:
    import pypdf
except ImportError:
    pypdf = None


# Patterns
USER_PATTERN = re.compile(r"\buser_\d+\b")
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_PATTERN = re.compile(r"\+\d{1,3}(?:[ -]?\d+){2,}")
HASH_PATTERN = re.compile(r"\b[a-f0-9]{64}\b")

# Resource ID prefix whitelist
RESOURCE_PREFIXES = {
    "account", "analytics", "audit_record", "backup", "data_flow",
    "support", "tombstone", "export", "marketing", "object", "search",
    "delivery_confirmation", "customer_export", "legal_hold"
}

# Exclusion rules
EXCLUDED_FILENAMES = {"sample_output.csv", "output.csv"}
EXCLUDED_PATH_SUBSTRINGS = {"code/evaluation", "code/docs"}


def is_path_excluded(filepath: str) -> bool:
    """Checks whether a filepath violates the Answer-Key Exclusion Rule."""
    norm_path = os.path.normpath(filepath).replace("\\", "/")
    fname = os.path.basename(norm_path)
    if fname in EXCLUDED_FILENAMES:
        return True
    for excl in EXCLUDED_PATH_SUBSTRINGS:
        if excl in norm_path:
            return True
    return False


def extract_resource_ids(text: str) -> Set[str]:
    """Extracts all resource_id tokens adhering to prefix_digits format."""
    rids: Set[str] = set()
    for m in re.finditer(r"\b([a-z]+(?:_[a-z]+)*)_(\d+)\b", text):
        prefix = m.group(1)
        if prefix in RESOURCE_PREFIXES:
            rids.add(m.group(0))
    return rids


def extract_subject_identifiers(text: str) -> Set[Tuple[str, str]]:
    """Extracts subject identifiers as (kind, normalized_value) tuples."""
    subjects: Set[Tuple[str, str]] = set()
    for u in USER_PATTERN.findall(text):
        subjects.add(("user_id", u))
    for e in EMAIL_PATTERN.findall(text):
        e_norm = normalize_email(e) or e.lower()
        subjects.add(("email", e_norm))
    for p in PHONE_PATTERN.findall(text):
        p_norm = normalize_phone(p) or p
        subjects.add(("phone", p_norm))
    for h in HASH_PATTERN.findall(text):
        subjects.add(("email_hash", h.lower()))
    return subjects


@dataclass
class CooccurrenceRecord:
    """Represents a co-occurrence of a subject identifier and a resource_id."""
    resource_id: str
    subject_kind: str
    subject_val: str
    file_path: str
    location: str  # e.g. 'line 12' or 'page 1'


def scan_evidence_files(data_dir: str = "./dataset") -> Tuple[Dict[str, str], List[CooccurrenceRecord], Set[str]]:
    """
    Scans dataset files (strictly excluding answer-key files) and builds co-occurrences.
    Returns (file_statuses, cooccurrences, all_found_resource_ids).
    """
    evidence_dir = os.path.join(data_dir, "evidence")
    all_files = glob.glob(os.path.join(evidence_dir, "**/*"), recursive=True)
    all_files.extend(glob.glob(os.path.join(data_dir, "*.csv")))

    file_statuses: Dict[str, str] = {}
    cooccurrences: List[CooccurrenceRecord] = []
    all_found_rids: Set[str] = set()

    for fpath in sorted(all_files):
        if not os.path.isfile(fpath):
            continue

        if is_path_excluded(fpath):
            continue

        rel_path = os.path.normpath(os.path.relpath(fpath, _repo_root)).replace("\\", "/")

        # 1. Images
        if fpath.endswith((".png", ".jpg", ".jpeg")):
            file_statuses[rel_path] = "IMAGE_ONLY"
            continue

        # 2. PDF Documents
        elif fpath.endswith(".pdf"):
            if pypdf is None:
                file_statuses[rel_path] = "ERROR (pypdf not installed)"
                continue
            try:
                reader = pypdf.PdfReader(fpath)
                full_pdf_text = ""
                for page_idx, page in enumerate(reader.pages, start=1):
                    txt = page.extract_text() or ""
                    full_pdf_text += txt
                    rids = extract_resource_ids(txt)
                    all_found_rids.update(rids)
                    subjects = extract_subject_identifiers(txt)
                    for r_id in sorted(rids):
                        for s_kind, s_val in sorted(subjects):
                            cooccurrences.append(
                                CooccurrenceRecord(
                                    resource_id=r_id,
                                    subject_kind=s_kind,
                                    subject_val=s_val,
                                    file_path=rel_path,
                                    location=f"page {page_idx}",
                                )
                            )
                if len(full_pdf_text.strip()) > 0:
                    file_statuses[rel_path] = "TEXT_OK"
                else:
                    file_statuses[rel_path] = "PDF_NO_TEXT"
            except Exception as e:
                file_statuses[rel_path] = f"ERROR ({e})"
            continue

        # 3. JSON Files
        elif fpath.endswith(".json"):
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as fp:
                    for line_idx, line in enumerate(fp, start=1):
                        rids = extract_resource_ids(line)
                        all_found_rids.update(rids)
                        subjects = extract_subject_identifiers(line)
                        for r_id in sorted(rids):
                            for s_kind, s_val in sorted(subjects):
                                cooccurrences.append(
                                    CooccurrenceRecord(
                                        resource_id=r_id,
                                        subject_kind=s_kind,
                                        subject_val=s_val,
                                        file_path=rel_path,
                                        location=f"line {line_idx}",
                                    )
                                )
                file_statuses[rel_path] = "TEXT_OK"
            except Exception as e:
                file_statuses[rel_path] = f"ERROR ({e})"
            continue

        # 4. Text/SQL/LOG/CSV Files
        else:
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as fp:
                    for line_idx, line in enumerate(fp, start=1):
                        rids = extract_resource_ids(line)
                        all_found_rids.update(rids)
                        subjects = extract_subject_identifiers(line)
                        for r_id in sorted(rids):
                            for s_kind, s_val in sorted(subjects):
                                cooccurrences.append(
                                    CooccurrenceRecord(
                                        resource_id=r_id,
                                        subject_kind=s_kind,
                                        subject_val=s_val,
                                        file_path=rel_path,
                                        location=f"line {line_idx}",
                                    )
                                )
                file_statuses[rel_path] = "TEXT_OK"
            except Exception as e:
                file_statuses[rel_path] = f"ERROR ({e})"
            continue

    return file_statuses, cooccurrences, all_found_rids


def recheck_unfound_ids(
    target_ids: List[str] = ("account_004", "support_001", "audit_record_5569", "audit_record_6645"),
    data_dir: str = "./dataset",
) -> Dict[str, List[Dict[str, str]]]:
    """
    Searches for the 4 unfound IDs strictly across allowed files.
    Excludes sample_output.csv, output.csv, code/evaluation/, and code/docs/.
    """
    all_files = glob.glob(os.path.join(data_dir, "**/*"), recursive=True)
    findings: Dict[str, List[Dict[str, str]]] = {tid: [] for tid in target_ids}

    for fpath in sorted(all_files):
        if not os.path.isfile(fpath):
            continue
        if is_path_excluded(fpath):
            continue

        rel_path = os.path.normpath(os.path.relpath(fpath, _repo_root)).replace("\\", "/")

        if fpath.endswith(".pdf"):
            if pypdf is None:
                continue
            try:
                reader = pypdf.PdfReader(fpath)
                for page_idx, page in enumerate(reader.pages, start=1):
                    txt = page.extract_text() or ""
                    for tid in target_ids:
                        if tid in txt:
                            for line in txt.splitlines():
                                if tid in line:
                                    findings[tid].append({
                                        "file": rel_path,
                                        "location": f"page {page_idx}",
                                        "context": line.strip(),
                                    })
            except Exception:
                pass
        elif not fpath.endswith((".png", ".jpg", ".jpeg")):
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as fp:
                    for line_idx, line in enumerate(fp, start=1):
                        for tid in target_ids:
                            if tid in line:
                                findings[tid].append({
                                    "file": rel_path,
                                    "location": f"line {line_idx}",
                                    "context": line.strip(),
                                })
            except Exception:
                pass

    return findings


def score_sample_comparison(
    cooccurrences: List[CooccurrenceRecord],
    data_dir: str = "./dataset",
) -> Dict[str, Any]:
    """
    Diagnostic scoring function. ONLY executed after scanning is complete.
    Reads dataset/sample_output.csv to compare expected resources against co-occurrences.
    """
    sample_output_path = os.path.join(data_dir, "sample_output.csv")
    if not os.path.isfile(sample_output_path):
        raise FileNotFoundError(f"sample_output.csv not found at: {sample_output_path}")

    dataset = load_dataset(data_dir)
    sample_clusters = {req.case_id: resolve_request(req, dataset) for req in dataset.sample_deletion_requests}

    with open(sample_output_path, "r", encoding="utf-8") as f:
        sample_rows = list(csv.DictReader(f))

    expected_by_case: Dict[str, Set[str]] = {}
    for r in sample_rows:
        cid = r["case_id"]
        steps = json.loads(r["steps_json"])
        expected_by_case[cid] = set(s["resource_id"] for s in steps if s.get("resource_id"))

    # Build mapping from (kind, norm_val) -> set of co-occurring rids
    subject_to_rids: Dict[Tuple[str, str], Set[str]] = {}
    for rec in cooccurrences:
        key = (rec.subject_kind, rec.subject_val)
        subject_to_rids.setdefault(key, set()).add(rec.resource_id)

    total_linkable = 0
    total_not_linkable = 0
    total_extra = 0
    per_case_breakdown: Dict[str, Dict[str, Any]] = {}

    for cid in sorted(expected_by_case.keys()):
        cluster = sample_clusters[cid]
        cluster_subjects = set((n.kind, n.value_norm) for n in cluster.nodes.values())

        case_candidate_rids: Set[str] = set()
        for s in cluster_subjects:
            case_candidate_rids.update(subject_to_rids.get(s, set()))

        expected = expected_by_case[cid]
        linkable = expected & case_candidate_rids
        not_linkable = expected - case_candidate_rids
        extra = case_candidate_rids - expected

        total_linkable += len(linkable)
        total_not_linkable += len(not_linkable)
        total_extra += len(extra)

        per_case_breakdown[cid] = {
            "linkable": sorted(list(linkable)),
            "not_linkable": sorted(list(not_linkable)),
            "extra": sorted(list(extra)),
        }

    return {
        "total_expected_pairs": sum(len(v) for v in expected_by_case.values()),
        "total_linkable": total_linkable,
        "total_not_linkable": total_not_linkable,
        "total_extra": total_extra,
        "per_case_breakdown": per_case_breakdown,
    }


def write_cooccurrence_table(
    cooccurrences: List[CooccurrenceRecord],
    all_found_rids: Set[str],
    output_path: str = "./code/evaluation/subject_resource_cooccurrence.md",
) -> None:
    """Writes the markdown table of all co-occurring resource-to-subject links."""
    # Group by resource_id
    grouped: Dict[str, List[CooccurrenceRecord]] = {}
    for rec in cooccurrences:
        grouped.setdefault(rec.resource_id, []).append(rec)

    rids_with_subjects = set(grouped.keys())
    rids_without_subjects = all_found_rids - rids_with_subjects

    lines = [
        "# NullTrace: Subject-to-Resource Co-occurrence Table",
        "",
        "## Summary Statistics",
        f"- **Total Distinct Resource IDs in Scanned Content**: {len(all_found_rids)}",
        f"- **Resource IDs with at least One Subject Co-occurrence**: {len(rids_with_subjects)}",
        f"- **Resource IDs with Zero Subject Co-occurrences**: {len(rids_without_subjects)}",
        "",
        "## Co-occurrence Table",
        "",
        "| Resource ID | Subject Identifiers (Kind: Value) | File Location(s) |",
        "| :--- | :--- | :--- |",
    ]

    for rid in sorted(rids_with_subjects):
        recs = grouped[rid]
        subjs_str = ", ".join(sorted(set(f"{r.subject_kind}:{r.subject_val}" for r in recs)))
        locs_str = "<br>".join(sorted(set(f"{r.file_path} ({r.location})" for r in recs)))
        lines.append(f"| `{rid}` | {subjs_str} | {locs_str} |")

    lines.extend([
        "",
        "## Resource IDs Without Co-occurring Subject Identifiers (Sample Preview)",
        "",
        ", ".join(f"`{r}`" for r in sorted(rids_without_subjects)[:50]) + ("..." if len(rids_without_subjects) > 50 else ""),
        "",
    ])

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def write_subject_resource_report(
    file_statuses: Dict[str, str],
    cooccurrences: List[CooccurrenceRecord],
    all_found_rids: Set[str],
    rechecked: Dict[str, List[Dict[str, str]]],
    scoring: Dict[str, Any],
    output_path: str = "./code/evaluation/subject_resource_report.md",
) -> None:
    """Writes the comprehensive diagnostic report."""
    status_counts = Counter(file_statuses.values())
    non_text_files = [fn for fn, st in sorted(file_statuses.items()) if st != "TEXT_OK"]

    rids_with_subj = set(r.resource_id for r in cooccurrences)
    rids_without_subj = all_found_rids - rids_with_subj

    lines = [
        "# NullTrace: Subject-to-Resource Key Scan Report",
        "",
        "## 1. Manifest and Dataset Schema Findings",
        "",
        "- **`evidence_files.csv` Header**: `file_id,file_path,origin,captured_at`",
        "  - **Subject Identifier Columns**: None.",
        "  - **Resource Identifier Columns**: `file_id` (evidence bundle ID), `file_path` (path to evidence file).",
        "  - **Distinct Value Counts (<= 5)**: None (all columns have > 5 distinct values).",
        "",
        "- **Other Dataset CSV Schemas (Excluding Answer Keys)**:",
        "  - `deletion_requests.csv` (`case_id,email,requested_at,reported_status,reported_at,audit_at,request_text`): `email` is subject identifier; `reported_status` has 3 values (`COMPLETE`, `NOT_STARTED`, `PARTIALLY_COMPLETE`).",
        "  - `sample_deletion_requests.csv` (`case_id,email,requested_at,reported_status,reported_at,audit_at,request_text`): `email` is subject identifier; `reported_status` has 3 values (`COMPLETE`, `PARTIALLY_COMPLETE`, `NOT_STARTED`).",
        "  - `user_identities.csv` (`user_id,name,email,phone,email_hash,updated_at`): `user_id`, `name`, `email`, `phone`, `email_hash` are subject identifiers.",
        "  - `user_audit_log.csv` (`audit_id,user_id,event_time,field_name,old_value,new_value`): `user_id`, `old_value`, `new_value` carry subject identifiers; `field_name` has 3 values (`email`, `email_hash`, `phone`).",
        "  - `system_activity.csv` (`activity_id,event_time,event_type,source_system,target_system,resource_id,reported_result,details`): `resource_id` carries resource tokens; `details` carries subject identifiers in only 12 catalog rows; `reported_result` has 3 values (`SUCCESS`, `FAILED`, `PARTIAL`).",
        "  - `deletion_rules.csv` (`rule_id,data_category,condition,required_action`): `required_action` has 4 values (`DELETE`, `REDACT`, `ANONYMIZE`, `RETAIN`).",
        "",
        "---",
        "",
        "## 2. File Status Counts Across Dataset & Evidence",
        "",
        "- **Total Files Scanned**: " + str(len(file_statuses)),
    ]

    for st, cnt in sorted(status_counts.items()):
        lines.append(f"- **`{st}`**: {cnt}")

    lines.extend([
        "",
        "### Non-Text Files Requiring OCR / Vision Model",
    ])
    for f in non_text_files:
        lines.append(f"- `{f}` (`{file_statuses[f]}`)")

    lines.extend([
        "",
        "---",
        "",
        "## 3. Co-occurrence Summary",
        "",
        f"- **Total Co-occurrence Links Found**: {len(cooccurrences)}",
        f"- **Resource IDs with at least One Co-occurring Subject Identifier**: {len(rids_with_subj)}",
        f"- **Resource IDs with Zero Co-occurring Subject Identifiers**: {len(rids_without_subj)}",
        "",
        "---",
        "",
        "## 4. Scoring-Only Comparison (Sample Output Answer Key)",
        "",
        f"- **Total Expected Resource Pairs in Sample Output**: {scoring['total_expected_pairs']}",
        f"- **Expected Pairs Linkable via Direct Co-occurrence**: {scoring['total_linkable']} ({scoring['total_linkable'] / scoring['total_expected_pairs'] * 100:.1f}%)",
        f"- **Expected Pairs Not Directly Linkable on Same Line**: {scoring['total_not_linkable']} ({scoring['total_not_linkable'] / scoring['total_expected_pairs'] * 100:.1f}%)",
        f"- **Extra Co-occurring Resources**: {scoring['total_extra']}",
        "",
        "---",
        "",
        "## 5. Re-check of the 4 Previously 'Unfound' IDs (Answer-Key Isolation)",
        "",
        "| Resource ID | Match Status | Location | Context |",
        "| :--- | :--- | :--- | :--- |",
    ])

    for tid, matches in rechecked.items():
        if matches:
            for m in matches:
                lines.append(f"| `{tid}` | **FOUND** | `{m['file']}` ({m['location']}) | `{m['context']}` |")
        else:
            lines.append(f"| `{tid}` | **No match found** | None | Absent from all participant-facing evidence content and dataset tables |")

    lines.extend([
        "",
        "---",
        "",
        "## 6. The Most Likely Subject-to-Resource Key",
        "",
        "The primary data source linking subjects to system resource IDs is the relational schema within evidence database dumps (`dataset/evidence/databases/*.sql`) and JSON snapshot bundles (`dataset/evidence/records/*.json`), where internal user IDs (`user_*`) directly co-occur as primary and foreign keys alongside resource records (`account_*`, `search_*`, `analytics_*`, `audit_record_*`, `support_*`). While uncompressed PDF parsing via `pypdf` successfully recovers document-level support tickets (e.g. `support_001`), the linker still cannot observe: (1) multi-hop relational dependencies where a resource references an account table rather than the subject directly; (2) resources stored in the 11 non-text console screenshots (`dataset/evidence/images/*.png`); and (3) records whose direct identifiers have already been deleted or tombstoned prior to the snapshot capture time.",
        ""
    ])

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    print("Running evidence content scan with Answer-Key Isolation...")
    file_statuses, cooccurrences, all_found_rids = scan_evidence_files("./dataset")
    print(f"Scanned {len(file_statuses)} files. Found {len(cooccurrences)} co-occurrences across {len(all_found_rids)} resource IDs.")

    print("Writing code/evaluation/subject_resource_cooccurrence.md...")
    write_cooccurrence_table(cooccurrences, all_found_rids)

    print("Re-checking the 4 unfound IDs under Answer-Key Isolation...")
    rechecked = recheck_unfound_ids()

    print("Executing scoring-only comparison against sample_output.csv...")
    scoring = score_sample_comparison(cooccurrences, "./dataset")

    print("Writing code/evaluation/subject_resource_report.md...")
    write_subject_resource_report(file_statuses, cooccurrences, all_found_rids, rechecked, scoring)
    print("Step F.1 reports successfully generated.")


if __name__ == "__main__":
    main()
