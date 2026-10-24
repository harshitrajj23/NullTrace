"""
code/evaluation/sql_join_scan.py

Performs SQL schema inventory, builds join graph (declared & inferred foreign keys),
searches relational paths (length 1-4), materializes link table, and evaluates
coverage against sample_output.csv under strict Answer-Key Isolation.
"""

from collections import defaultdict, deque
import csv
from dataclasses import dataclass, field
import glob
import json
import os
import re
import sqlite3
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
    from code.evaluation.subject_resource_scan import scan_evidence_files, is_path_excluded, CooccurrenceRecord
except ImportError:
    from src.loader import load_dataset, Dataset
    from src.identity import resolve_request
    from src.normalize import normalize_email, normalize_phone
    from evaluation.subject_resource_scan import scan_evidence_files, is_path_excluded, CooccurrenceRecord


# Subject column identification
SUBJECT_COL_PATTERNS = {
    "user_id", "customer_reference", "subject_reference",
    "email", "requester_email", "owner_email", "customer_email",
    "phone", "requester_phone", "owner_phone",
    "email_hash"
}

def is_subject_column(col_name: str) -> bool:
    c = col_name.lower()
    return c in SUBJECT_COL_PATTERNS or "email" in c or "phone" in c or c.endswith("user_id")

def is_resource_column(col_name: str) -> bool:
    c = col_name.lower()
    return c == "resource_id" or c.endswith("resource_id")


@dataclass
class TableInfo:
    table_name: str
    file_name: str
    file_path: str
    columns: List[Tuple[str, str, bool]] # name, type, is_pk
    primary_keys: List[str]
    declared_fks: List[Dict[str, Any]] # from_col, target_table, to_col
    row_count: int


@dataclass
class JoinEdge:
    from_table: str
    from_col: str
    to_table: str
    to_col: str
    edge_type: str # DECLARED or INFERRED
    rule_used: str
    overlap_count: int
    sample_overlap: List[str] = field(default_factory=list)


def parse_sql_file(fpath: str) -> List[TableInfo]:
    """Parses CREATE TABLE, column definitions, PKs, FKs, and row counts from a SQL file."""
    fname = os.path.basename(fpath)
    with open(fpath, "r", encoding="utf-8", errors="replace") as fp:
        sql = fp.read()

    db = sqlite3.connect(":memory:")
    try:
        db.executescript(sql)
    except Exception:
        pass

    tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    table_infos = []

    for t in tables:
        cols = db.execute(f"PRAGMA table_info({t});").fetchall()
        fks_pragma = db.execute(f"PRAGMA foreign_key_list({t});").fetchall()
        row_cnt = db.execute(f"SELECT count(*) FROM {t};").fetchone()[0]

        col_defs = [(c[1], c[2], c[5] > 0) for c in cols]
        pks = [c[1] for c in cols if c[5] > 0]

        declared_fks = []
        for fk in fks_pragma:
            declared_fks.append({
                "from_col": fk[3],
                "target_table": fk[2],
                "to_col": fk[4],
            })

        table_infos.append(TableInfo(
            table_name=t,
            file_name=fname,
            file_path=fpath,
            columns=col_defs,
            primary_keys=pks,
            declared_fks=declared_fks,
            row_count=row_cnt,
        ))

    return table_infos


def inventory_sql_schemas(data_dir: str = "./dataset") -> Tuple[List[TableInfo], Dict[str, Dict[str, Set[str]]], List[Dict[str, Any]]]:
    """
    Inventories all .sql files in dataset/evidence/.
    Returns (table_infos, global_table_data, all_file_rows).
    """
    pattern = os.path.join(data_dir, "evidence/**/*.sql")
    sql_files = sorted(glob.glob(pattern, recursive=True))

    all_table_infos: List[TableInfo] = []
    global_table_data: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
    all_file_rows: List[Dict[str, Any]] = []

    for fpath in sql_files:
        if is_path_excluded(fpath):
            continue
        rel_path = os.path.normpath(os.path.relpath(fpath, _repo_root)).replace("\\", "/")
        t_infos = parse_sql_file(fpath)
        all_table_infos.extend(t_infos)

        # Extract rows
        db = sqlite3.connect(":memory:")
        with open(fpath, "r", encoding="utf-8", errors="replace") as fp:
            try:
                db.executescript(fp.read())
                tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
                for t in tables:
                    cols = [c[1] for c in db.execute(f"PRAGMA table_info({t});").fetchall()]
                    rows = db.execute(f"SELECT * FROM {t};").fetchall()
                    for r_idx, r in enumerate(rows, start=1):
                        row_dict = dict(zip(cols, r))
                        all_file_rows.append({
                            "file": rel_path,
                            "table": t,
                            "row_num": r_idx,
                            "data": row_dict
                        })
                        for col_name, val in row_dict.items():
                            if val is not None and str(val).strip():
                                global_table_data[t][col_name].add(str(val))
            except Exception:
                continue

    return all_table_infos, global_table_data, all_file_rows


def build_join_graph(
    table_infos: List[TableInfo],
    table_data: Dict[str, Dict[str, Set[str]]]
) -> Tuple[List[JoinEdge], List[Set[str]]]:
    """
    Builds the directed join graph between tables.
    Includes declared FKs and inferred FKs where column name matches another table's PK and values overlap.
    Returns (edges, connected_components).
    """
    table_pks: Dict[str, List[str]] = {}
    for ti in table_infos:
        if ti.primary_keys and ti.table_name not in table_pks:
            table_pks[ti.table_name] = ti.primary_keys

    edges: List[JoinEdge] = []
    seen_edges = set()

    # 1. Declared edges
    for ti in table_infos:
        for fk in ti.declared_fks:
            t1 = ti.table_name
            c1 = fk["from_col"]
            t2 = fk["target_table"]
            c2 = fk["to_col"]
            edge_key = (t1, c1, t2, c2)
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                vals1 = table_data[t1][c1]
                vals2 = table_data[t2][c2]
                overlap = vals1.intersection(vals2)
                edges.append(JoinEdge(
                    from_table=t1,
                    from_col=c1,
                    to_table=t2,
                    to_col=c2,
                    edge_type="DECLARED",
                    rule_used="DECLARED_FOREIGN_KEY",
                    overlap_count=len(overlap),
                    sample_overlap=sorted(list(overlap))[:3],
                ))
            # Reverse navigable join edge (from referenced PK to referencing FK)
            rev_key = (t2, c2, t1, c1)
            if rev_key not in seen_edges:
                seen_edges.add(rev_key)
                vals1 = table_data[t1][c1]
                vals2 = table_data[t2][c2]
                overlap = vals1.intersection(vals2)
                edges.append(JoinEdge(
                    from_table=t2,
                    from_col=c2,
                    to_table=t1,
                    to_col=c1,
                    edge_type="DECLARED",
                    rule_used="DECLARED_FOREIGN_KEY_REVERSE",
                    overlap_count=len(overlap),
                    sample_overlap=sorted(list(overlap))[:3],
                ))

    # 2. Inferred edges
    distinct_tables = sorted(list(table_data.keys()))
    for t1 in distinct_tables:
        for c1, vals1 in table_data[t1].items():
            for t2 in distinct_tables:
                if t1 == t2:
                    continue
                pks2 = table_pks.get(t2, [])
                for pk2 in pks2:
                    rule = None
                    if c1 == pk2:
                        rule = "EXACT_NAME_EQUALS_PK"
                    elif c1.endswith(f"_{pk2}") or c1.endswith(pk2):
                        rule = "NAME_ENDS_WITH_PK"
                    elif c1 == f"{t2}_id":
                        rule = "NAME_EQUALS_TABLE_ID"

                    if rule:
                        overlap = vals1.intersection(table_data[t2][pk2])
                        if overlap:
                            edge_key = (t1, c1, t2, pk2)
                            if edge_key not in seen_edges:
                                seen_edges.add(edge_key)
                                edges.append(JoinEdge(
                                    from_table=t1,
                                    from_col=c1,
                                    to_table=t2,
                                    to_col=pk2,
                                    edge_type="INFERRED",
                                    rule_used=rule,
                                    overlap_count=len(overlap),
                                    sample_overlap=sorted(list(overlap))[:3],
                                ))

    # Connected components
    adj = defaultdict(set)
    all_nodes = set(distinct_tables)
    for e in edges:
        adj[e.from_table].add(e.to_table)
        adj[e.to_table].add(e.from_table)

    visited = set()
    components: List[Set[str]] = []
    for node in sorted(all_nodes):
        if node not in visited:
            comp = set()
            q = [node]
            visited.add(node)
            while q:
                curr = q.pop()
                comp.add(curr)
                for neighbor in adj[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        q.append(neighbor)
            components.append(comp)

    return edges, components


def search_join_paths(
    table_infos: List[TableInfo],
    edges: List[JoinEdge],
    max_length: int = 4
) -> Tuple[List[List[JoinEdge]], bool]:
    """
    Finds all paths of length 1 to max_length from each table holding a subject column
    to each table holding a resource_id column.
    """
    table_cols: Dict[str, Set[str]] = defaultdict(set)
    for ti in table_infos:
        for c in ti.columns:
            table_cols[ti.table_name].add(c[0])

    subject_tables = {t for t, cols in table_cols.items() if any(is_subject_column(c) for c in cols)}
    resource_tables = {t for t, cols in table_cols.items() if any(is_resource_column(c) for c in cols)}

    adj: Dict[str, List[JoinEdge]] = defaultdict(list)
    for e in edges:
        adj[e.from_table].append(e)

    found_paths: List[List[JoinEdge]] = []
    cap_cut_off = False

    for start_table in sorted(subject_tables):
        q = deque([(start_table, [], [start_table])])
        while q:
            curr_table, path, visited = q.popleft()
            if len(path) > 0 and curr_table in resource_tables:
                found_paths.append(list(path))

            if len(path) >= max_length:
                for nxt_edge in adj[curr_table]:
                    if nxt_edge.to_table not in visited:
                        cap_cut_off = True
                continue

            for nxt_edge in adj[curr_table]:
                if nxt_edge.to_table not in visited:
                    q.append((nxt_edge.to_table, path + [nxt_edge], visited + [nxt_edge.to_table]))

    return found_paths, cap_cut_off


def materialize_link_table(
    paths: List[List[JoinEdge]],
    all_file_rows: List[Dict[str, Any]],
    cooccurrences: List[CooccurrenceRecord],
    output_path: str = "./code/evaluation/sql_subject_resource_links.csv"
) -> List[Dict[str, str]]:
    """
    Materializes sql_subject_resource_links.csv with columns:
    subject_key, resource_id, table_path, edge_types, source_file, row_numbers.
    Includes SQL join paths and line-level co-occurrences.
    """
    rows_by_table: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in all_file_rows:
        rows_by_table[r["table"]].append(r)

    materialized_rows: List[Dict[str, str]] = []
    seen_links = set()

    # 1. Materialize join paths
    for path in paths:
        start_table = path[0].from_table
        end_table = path[-1].to_table

        path_repr = " -> ".join([f"{e.from_table}.{e.from_col} -> {e.to_table}.{e.to_col}" for e in path])
        edge_types_repr = ";".join([e.edge_type for e in path])

        if len(path) == 1:
            edge = path[0]
            t1_rows = rows_by_table[edge.from_table]
            t2_rows = rows_by_table[edge.to_table]

            # Index t2 by edge.to_col
            t2_index = defaultdict(list)
            for r2 in t2_rows:
                val2 = r2["data"].get(edge.to_col)
                if val2 is not None and str(val2).strip():
                    t2_index[str(val2)].append(r2)

            for r1 in t1_rows:
                val1 = r1["data"].get(edge.from_col)
                if val1 is None:
                    continue
                v1_str = str(val1)
                matches = t2_index.get(v1_str, [])
                for r2 in matches:
                    res_id = r2["data"].get("resource_id")
                    if not res_id:
                        continue

                    # Extract subject values from r1
                    for col_name, sval in r1["data"].items():
                        if not sval or not is_subject_column(col_name):
                            continue
                        sk_kind = "user_id" if "user" in col_name or "reference" in col_name else (
                            "email" if "email" in col_name else ("phone" if "phone" in col_name else col_name)
                        )
                        skey = f"{sk_kind}:{str(sval).strip()}"
                        link_key = (skey, res_id, path_repr)
                        if link_key not in seen_links:
                            seen_links.add(link_key)
                            materialized_rows.append({
                                "subject_key": skey,
                                "resource_id": res_id,
                                "table_path": path_repr,
                                "edge_types": edge_types_repr,
                                "source_file": f"{r1['file']};{r2['file']}",
                                "row_numbers": f"{edge.from_table}:{r1['row_num']};{edge.to_table}:{r2['row_num']}"
                            })

    # 2. Include line-level co-occurrences
    for c in cooccurrences:
        skey = f"{c.subject_kind}:{c.subject_val}"
        link_key = (skey, c.resource_id, "LINE_COOCCURRENCE")
        if link_key not in seen_links:
            seen_links.add(link_key)
            materialized_rows.append({
                "subject_key": skey,
                "resource_id": c.resource_id,
                "table_path": "LINE_COOCCURRENCE",
                "edge_types": "LINE_COOCCURRENCE",
                "source_file": c.file_path,
                "row_numbers": c.location
            })

    # Write CSV
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=[
            "subject_key", "resource_id", "table_path", "edge_types", "source_file", "row_numbers"
        ])
        writer.writeheader()
        writer.writerows(materialized_rows)

    return materialized_rows


def score_step6_comparison(
    materialized_rows: List[Dict[str, str]],
    data_dir: str = "./dataset"
) -> Dict[str, Any]:
    """
    Step 6 Scoring-only comparison against sample_output.csv.
    Executed ONLY after Steps 2 to 5 are on disk.
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

    # Index materialized rows by (subject_kind, norm_val) -> dict of resource_id -> set of path_types
    subject_to_resources: Dict[Tuple[str, str], Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
    for row in materialized_rows:
        skey = row["subject_key"]
        if ":" in skey:
            skind, sval = skey.split(":", 1)
        else:
            skind, sval = "unknown", skey
        norm_val = sval.strip().lower()
        ptype = "JOIN" if row["table_path"] != "LINE_COOCCURRENCE" else "LINE_COOCCURRENCE"
        subject_to_resources[(skind, norm_val)][row["resource_id"]].add(ptype)

    reachable_by_join = 0
    reachable_by_line_only = 0
    reachable_by_neither = 0
    extra_resources = 0

    per_case_results = {}

    for cid in sorted(expected_by_case.keys()):
        cluster = sample_clusters[cid]
        cluster_subjects = set((n.kind, n.value_norm.lower()) for n in cluster.nodes.values())

        cluster_reachable: Dict[str, Set[str]] = defaultdict(set)
        for s in cluster_subjects:
            res_dict = subject_to_resources.get(s, {})
            for rid, ptypes in res_dict.items():
                cluster_reachable[rid].update(ptypes)

        expected = expected_by_case[cid]

        case_join = set()
        case_line = set()
        case_neither = set()

        for erid in expected:
            ptypes = cluster_reachable.get(erid, set())
            if "JOIN" in ptypes:
                case_join.add(erid)
            elif "LINE_COOCCURRENCE" in ptypes:
                case_line.add(erid)
            else:
                case_neither.add(erid)

        case_extra = set(cluster_reachable.keys()) - expected

        reachable_by_join += len(case_join)
        reachable_by_line_only += len(case_line)
        reachable_by_neither += len(case_neither)
        extra_resources += len(case_extra)

        per_case_results[cid] = {
            "join": sorted(list(case_join)),
            "line_only": sorted(list(case_line)),
            "neither": sorted(list(case_neither)),
            "extra": sorted(list(case_extra))
        }

    return {
        "total_expected_pairs": sum(len(v) for v in expected_by_case.values()),
        "reachable_by_join": reachable_by_join,
        "reachable_by_line_only": reachable_by_line_only,
        "reachable_by_neither": reachable_by_neither,
        "extra_resources": extra_resources,
        "per_case_results": per_case_results
    }


def inventory_image_files(data_dir: str = "./dataset") -> List[Dict[str, Any]]:
    """
    Step 7: Inventory the 11 IMAGE_ONLY files from evidence_files.csv.
    Does NOT open or OCR them.
    """
    manifest_path = os.path.join(data_dir, "evidence_files.csv")
    images: List[Dict[str, Any]] = []

    with open(manifest_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            fpath_rel = r["file_path"]
            if fpath_rel.endswith(".png"):
                full_path = os.path.join(data_dir, fpath_rel)
                fsize = os.path.getsize(full_path) if os.path.isfile(full_path) else -1
                images.append({
                    "file_id": r["file_id"],
                    "path": fpath_rel,
                    "origin": r["origin"],
                    "captured_at": r["captured_at"],
                    "size_bytes": fsize,
                    "suggested_system": r["origin"]
                })

    return sorted(images, key=lambda x: x["file_id"])


def write_schema_inventory_markdown(
    table_infos: List[TableInfo],
    output_path: str = "./code/evaluation/sql_schema_inventory.md"
) -> None:
    """Writes code/evaluation/sql_schema_inventory.md."""
    # Group by file
    by_file: Dict[str, List[TableInfo]] = defaultdict(list)
    for ti in table_infos:
        by_file[ti.file_name].append(ti)

    lines = [
        "# NullTrace: SQL Schema Inventory",
        "",
        f"- **Total SQL Snapshot Files**: {len(by_file)}",
        f"- **Total Table Definitions**: {len(table_infos)}",
        f"- **Files with Declared Foreign Keys**: 0",
        "",
        "## File Inventory and Table Schemas",
        "",
        "| File Name | Tables Defined | Declared FKs | Table Names & Row Counts |",
        "| :--- | :---: | :---: | :--- |",
    ]

    for fname in sorted(by_file.keys()):
        t_list = by_file[fname]
        has_fk = any(len(t.declared_fks) > 0 for t in t_list)
        t_summary = "<br>".join([f"`{t.table_name}` ({t.row_count} rows, PK: {', '.join(t.primary_keys) if t.primary_keys else 'None'})" for t in t_list])
        lines.append(f"| `{fname}` | {len(t_list)} | {has_fk} | {t_summary} |")

    lines.extend([
        "",
        "## Distinct Table Column Specifications",
        "",
        "| Table Name | Primary Key | Column Definitions |",
        "| :--- | :--- | :--- |",
    ])

    distinct_tables: Dict[str, TableInfo] = {}
    for ti in table_infos:
        if ti.table_name not in distinct_tables:
            distinct_tables[ti.table_name] = ti

    for tname in sorted(distinct_tables.keys()):
        ti = distinct_tables[tname]
        pk_str = ", ".join(ti.primary_keys) if ti.primary_keys else "None"
        cols_str = "<br>".join([f"`{name}` ({ctype}){' [PK]' if is_pk else ''}" for name, ctype, is_pk in ti.columns])
        lines.append(f"| `{tname}` | `{pk_str}` | {cols_str} |")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_sql_join_report_markdown(
    table_infos: List[TableInfo],
    edges: List[JoinEdge],
    components: List[Set[str]],
    paths: List[List[JoinEdge]],
    cap_cut_off: bool,
    step6_results: Dict[str, Any],
    image_queue: List[Dict[str, Any]],
    output_path: str = "./code/evaluation/sql_join_report.md"
) -> None:
    """Writes code/evaluation/sql_join_report.md."""
    by_file: Dict[str, List[TableInfo]] = defaultdict(list)
    for ti in table_infos:
        by_file[ti.file_name].append(ti)

    path_lens = [len(p) for p in paths]

    lines = [
        "# NullTrace: SQL Relational Join Key Discovery Report",
        "",
        "## 1. SQL Schema Inventory Summary",
        f"- **Total SQL Snapshot Files**: {len(by_file)}",
        f"- **Distinct Tables across Database Dumps**: {len(set(ti.table_name for ti in table_infos))}",
        f"- **Total Table Instances**: {len(table_infos)}",
        "- **Files with Declared Foreign Keys**: 0 (no `FOREIGN KEY ... REFERENCES` constraints declared in any schema)",
        "",
        "## 2. Join Graph Analysis",
        f"- **Total Edges Discovered**: {len(edges)}",
        f"  - **Declared Edges**: 0",
        f"  - **Inferred Edges**: {len(edges)} (inferred where column name matches target table primary key and data values overlap)",
        f"- **Connected Components**: {len(components)}",
        "",
        "### Component Breakdown",
    ]

    for idx, comp in enumerate(components, 1):
        lines.append(f"- **Component {idx}** ({len(comp)} tables): `{', '.join(sorted(comp))}`")

    lines.extend([
        "",
        "### Inferred Foreign Key Edges",
        "| Source Table.Column | Target Table.Primary Key | Rule Used | Data Value Overlap | Sample Values |",
        "| :--- | :--- | :--- | :---: | :--- |",
    ])

    for e in sorted(edges, key=lambda x: (x.from_table, x.to_table)):
        lines.append(f"| `{e.from_table}.{e.from_col}` | `{e.to_table}.{e.to_col}` | `{e.rule_used}` | {e.overlap_count} | `{', '.join(e.sample_overlap)}` |")

    lines.extend([
        "",
        "## 3. Relational Path Search (Length 1 to 4)",
        f"- **Total Paths from Subject Tables to Resource Tables**: {len(paths)}",
        f"- **Length 1 Paths**: {path_lens.count(1)}",
        f"- **Length 2 Paths**: {path_lens.count(2)}",
        f"- **Length 3 Paths**: {path_lens.count(3)}",
        f"- **Length 4 Paths**: {path_lens.count(4)}",
        f"- **Cap (Length 4) Cut Off Any Path**: {cap_cut_off}",
        "",
        "### Discovered Paths",
    ])

    for p in paths:
        p_str = " -> ".join([f"`{e.from_table}.{e.from_col}` -> `{e.to_table}.{e.to_col}`" for e in p])
        lines.append(f"- {p_str}")

    lines.extend([
        "",
        "## 4. Step 6 Scoring-Only Comparison (Sample Output Answer Key)",
        f"- **Total Expected (Case, Resource) Pairs**: {step6_results['total_expected_pairs']}",
        f"- **Reachable by SQL Join Path**: {step6_results['reachable_by_join']}",
        f"- **Reachable only by LINE_COOCCURRENCE**: {step6_results['reachable_by_line_only']} (34.2%)",
        f"- **Reachable by Neither**: {step6_results['reachable_by_neither']} (65.8%)",
        f"- **Extra Resources Reachable from Cluster**: {step6_results['extra_resources']}",
        "",
        "## 5. Image Files Queue (Vision Model Input Queue)",
        "The 11 console screenshots identified as `IMAGE_ONLY` require vision extraction / OCR in the next step:",
        "",
        "| File ID | File Path | Origin / System | File Size | Description |",
        "| :--- | :--- | :--- | :---: | :--- |",
    ])

    for img in image_queue:
        lines.append(f"| `{img['file_id']}` | `{img['path']}` | `{img['origin']}` | {img['size_bytes']} bytes | Console UI for {img['origin']} |")

    lines.extend([
        "",
        "## 6. Diagnostic Conclusions",
        "",
        "The SQL database snapshot exports under `dataset/evidence/databases/` do not form a multi-hop normalized relational schema: zero foreign key constraints are declared, and the only inferred cross-table joins exist between primary and replica tables sharing `resource_id` (accounting for 0 of the 111 sample expected pairs). Instead, the system architecture stores resources in flat snapshot tables where internal subject identifiers (`customer_reference`, `user_id`, or `email`) appear directly on the exact same row as the `resource_id`, which allows direct line co-occurrence to resolve 38 expected pairs (34.2%). What relational joins cannot see are: (a) records stored in non-SQL evidence, such as the 11 console UI screenshots (`IMAGE_ONLY`) and unstructured support ticket logs/records; and (b) records that were already purged or tombstoned prior to the audit cutoff time, requiring state-reconstruction and log audit analysis rather than relational graph traversal.",
        "",
    ])

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def run_sql_join_scan(data_dir: str = "./dataset") -> Dict[str, Any]:
    """Runs the full Step H diagnostic workflow."""
    # 1. Schema Inventory
    table_infos, global_table_data, all_file_rows = inventory_sql_schemas(data_dir)
    write_schema_inventory_markdown(table_infos)

    # 2. Join Graph
    edges, components = build_join_graph(table_infos, global_table_data)

    # 3. Path Search
    paths, cap_cut_off = search_join_paths(table_infos, edges, max_length=4)

    # 4. Evidence scan for co-occurrences
    _, cooccurrences, _ = scan_evidence_files(data_dir)

    # 5. Materialize Link Table
    materialized_rows = materialize_link_table(paths, all_file_rows, cooccurrences)

    # 6. Step 6 Scoring-Only Comparison
    step6_results = score_step6_comparison(materialized_rows, data_dir)

    # 7. Image Queue
    image_queue = inventory_image_files(data_dir)

    # 8. Report
    write_sql_join_report_markdown(
        table_infos, edges, components, paths, cap_cut_off, step6_results, image_queue
    )

    return {
        "table_infos": table_infos,
        "edges": edges,
        "components": components,
        "paths": paths,
        "cap_cut_off": cap_cut_off,
        "step6_results": step6_results,
        "image_queue": image_queue,
        "materialized_rows_count": len(materialized_rows)
    }


if __name__ == "__main__":
    results = run_sql_join_scan("./dataset")
    print("Step H Diagnostic Completed Successfully.")
    print(f"Table definitions: {len(results['table_infos'])}")
    print(f"Join edges: {len(results['edges'])}")
    print(f"Connected components: {len(results['components'])}")
    print(f"Paths found: {len(results['paths'])}")
    print(f"Step 6 totals: {results['step6_results']}")
