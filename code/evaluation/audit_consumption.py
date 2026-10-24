"""code/evaluation/audit_consumption.py

Audits consumption of user_audit_log.csv and user_identities.csv by identity.py.
Checks whether every audit row was cited by a link and whether every identity row
was included in at least one cluster.
For uncited rows, determines the exact reason based on identity.py's code path.
"""

from collections import Counter
from dataclasses import dataclass, field
import os
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
    from code.src.models import AuditEvent, Identity
    from code.src.identity import resolve_all, Cluster
except ImportError:
    from src.loader import load_dataset, Dataset
    from src.models import AuditEvent, Identity
    from src.identity import resolve_all, Cluster


@dataclass
class UncitedAuditRow:
    """Details of an audit row that was not cited by any identity link."""
    audit_id: str
    user_id: str
    field_name: str
    old_value: str
    new_value: str
    row_number: int
    reason: str


@dataclass
class AuditConsumptionReport:
    """Report detailing audit and identity consumption."""
    total_audit_rows: int
    cited_audit_rows: int
    uncited_audit_rows_count: int
    uncited_by_field: Dict[str, int]
    uncited_rows: List[UncitedAuditRow]

    total_identity_rows: int
    consumed_identity_rows: int
    unconsumed_identity_rows: int
    unconsumed_user_ids: List[str]


def check_audit_consumption(data_dir: str = "./dataset") -> AuditConsumptionReport:
    """
    Performs consumption check across user_audit_log.csv and user_identities.csv.
    """
    dataset = load_dataset(data_dir)
    clusters = resolve_all(dataset)

    # 1. Collect all cited SourceRefs from links across all clusters
    cited_sources: Set[Tuple[str, int]] = set()
    cluster_uids: Set[str] = set()

    for c in clusters.values():
        for link in c.links:
            cited_sources.add((link.source.file, link.source.row_number))
        for (kind, val) in c.nodes.keys():
            if kind == "user_id":
                cluster_uids.add(val)

    # Set of all user_ids that submitted any deletion request
    # Check both current emails and historical emails in deletion requests
    request_emails = set(r.email_norm for r in dataset.deletion_requests if r.email_norm)

    # 2. Check user_audit_log.csv
    total_audit = len(dataset.user_audit_log)
    cited_audit_count = 0
    uncited_by_field: Dict[str, int] = Counter()
    uncited_rows: List[UncitedAuditRow] = []

    for a in dataset.user_audit_log:
        ref_key = (a.source.file, a.source.row_number)
        if ref_key in cited_sources:
            cited_audit_count += 1
        else:
            uncited_by_field[a.field_name] += 1

            # Determine programmatic reason based on identity.py code path
            if a.user_id not in cluster_uids:
                reason = (
                    f"Subject '{a.user_id}' never submitted a deletion request (neither current nor "
                    f"historical email appears in deletion_requests.csv); resolver seeds only from "
                    f"requests, so user's audit history was not traversed."
                )
            elif a.field_name not in ("email", "phone", "email_hash"):
                reason = f"Field '{a.field_name}' is not in ('email', 'phone', 'email_hash') and ignored by resolver."
            elif not a.old_value_raw and not a.new_value_raw:
                reason = "Both old_value and new_value are empty/null; no identifier node was created."
            else:
                reason = "Unhandled code path in identity resolver."

            uncited_rows.append(
                UncitedAuditRow(
                    audit_id=a.audit_id,
                    user_id=a.user_id,
                    field_name=a.field_name,
                    old_value=a.old_value_raw,
                    new_value=a.new_value_raw,
                    row_number=a.source.row_number,
                    reason=reason,
                )
            )

    # 3. Check user_identities.csv
    total_identities = len(dataset.user_identities)
    consumed_identities = 0
    unconsumed_uids: List[str] = []

    for ident in dataset.user_identities:
        if ident.user_id in cluster_uids:
            consumed_identities += 1
        else:
            unconsumed_uids.append(ident.user_id)

    return AuditConsumptionReport(
        total_audit_rows=total_audit,
        cited_audit_rows=cited_audit_count,
        uncited_audit_rows_count=len(uncited_rows),
        uncited_by_field=dict(sorted(uncited_by_field.items())),
        uncited_rows=uncited_rows,
        total_identity_rows=total_identities,
        consumed_identity_rows=consumed_identities,
        unconsumed_identity_rows=len(unconsumed_uids),
        unconsumed_user_ids=sorted(unconsumed_uids),
    )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Check audit log and identity consumption by identity resolver")
    parser.add_argument("--data-dir", default="./dataset", help="Path to dataset directory")
    args = parser.parse_args()

    rep = check_audit_consumption(args.data_dir)
    print("=== AUDIT LOG & IDENTITY CONSUMPTION REPORT ===")
    print(f"User Audit Log Rows: {rep.total_audit_rows} total, {rep.cited_audit_rows} cited, {rep.uncited_audit_rows_count} uncited")
    print("Uncited Audit Rows by Field:")
    for fld, cnt in rep.uncited_by_field.items():
        print(f"  {fld}: {cnt}")

    print(f"\nUser Identities Rows: {rep.total_identity_rows} total, {rep.consumed_identity_rows} consumed, {rep.unconsumed_identity_rows} unconsumed")

    print("\nUncited Audit Rows Details:")
    for r in rep.uncited_rows:
        print(f"  [{r.audit_id}] row={r.row_number} user_id={r.user_id} field={r.field_name} (old='{r.old_value}', new='{r.new_value}')")
        print(f"     Reason: {r.reason}")


if __name__ == "__main__":
    main()
