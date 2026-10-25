"""code/src/loader.py

Typed loader for dataset CSV files with source tracing, malformed row detection,
duplicate primary key checking, and normalization reporting.
"""

from collections import Counter
import csv
from dataclasses import dataclass, field
from datetime import datetime
import os
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import (
    SourceRef,
    Identity,
    AuditEvent,
    SystemActivity,
    DeletionRule,
    DeletionRequest,
    EvidenceFile,
)
from .normalize import (
    normalize_email,
    normalize_phone,
    normalize_timestamp,
    TimestampFormatError,
)


class LoaderError(Exception):
    """Base exception for loader errors."""
    pass


class EmptyRowError(LoaderError):
    """Raised when an empty data line is found in a CSV."""
    def __init__(self, file: str, line: int):
        self.file = file
        self.line = line
        super().__init__(f"Empty data row encountered at {file}:{line}")


class MalformedRowError(LoaderError):
    """Raised when a CSV row does not match the expected column count."""
    def __init__(self, file: str, line: int, expected: int, actual: int):
        self.file = file
        self.line = line
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Malformed row at {file}:{line}: expected {expected} columns, found {actual}"
        )


@dataclass
class LoaderReport:
    """Detailed summary of the dataset loading process."""
    row_counts: Dict[str, int] = field(default_factory=dict)
    normalization_issues: Dict[str, int] = field(default_factory=lambda: Counter())
    timestamps_without_timezone: int = 0
    duplicate_pk_errors: List[str] = field(default_factory=list)

    def summary_text(self) -> str:
        lines = [
            "=== DATASET LOADER REPORT ===",
            "Per-file Row Counts:",
        ]
        for fn, cnt in sorted(self.row_counts.items()):
            lines.append(f"  - {fn}: {cnt}")
        lines.append(f"Timestamps without timezone: {self.timestamps_without_timezone}")
        lines.append("Normalization Issues:")
        if self.normalization_issues:
            for issue, cnt in sorted(self.normalization_issues.items()):
                lines.append(f"  - {issue}: {cnt}")
        else:
            lines.append("  - None")
        lines.append("Duplicate Primary Key Errors:")
        if self.duplicate_pk_errors:
            for err in self.duplicate_pk_errors:
                lines.append(f"  - {err}")
        else:
            lines.append("  - None (all primary keys unique)")
        return "\n".join(lines)


@dataclass
class Dataset:
    """In-memory typed container for all loaded dataset entities."""
    data_dir: str
    deletion_requests: List[DeletionRequest]
    sample_deletion_requests: List[DeletionRequest]
    sample_output: List[Dict[str, Any]]
    user_identities: List[Identity]
    user_audit_log: List[AuditEvent]
    system_activity: List[SystemActivity]
    deletion_rules: List[DeletionRule]
    evidence_files: List[EvidenceFile]
    report: LoaderReport


def _read_csv_rows(filepath: str) -> Tuple[List[str], List[Tuple[int, List[str]]]]:
    """
    Reads a CSV file verifying no empty lines or malformed rows.
    Returns (header, list_of_(line_number, row_columns)).
    Line numbers are 1-based (header is line 1).
    """
    filename = os.path.basename(filepath)
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Dataset file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            raise LoaderError(f"File {filename} is completely empty")

        rows: List[Tuple[int, List[str]]] = []
        expected_len = len(header)

        for line_no, r in enumerate(reader, start=2):
            if not r or (len(r) == 1 and not r[0].strip()):
                raise EmptyRowError(filename, line_no)
            if len(r) != expected_len:
                raise MalformedRowError(filename, line_no, expected_len, len(r))
            rows.append((line_no, r))

    return header, rows


def load_dataset(data_dir: str = "./dataset") -> Dataset:
    """
    Loads all participant-facing CSV files from data_dir into typed dataclasses.
    Attaches SourceRef to every row and gathers a comprehensive LoaderReport.
    """
    report = LoaderReport()

    def process_timestamp(val: str, fn: str, line_no: int) -> Optional[datetime]:
        dt, tz_missing = normalize_timestamp(val, fn, line_no)
        if tz_missing:
            report.timestamps_without_timezone += 1
            report.normalization_issues["timestamp_missing_timezone"] += 1
        return dt

    # 1. user_identities.csv
    identities_path = os.path.join(data_dir, "user_identities.csv")
    _, rows = _read_csv_rows(identities_path)
    fn = "user_identities.csv"
    report.row_counts[fn] = len(rows)
    identities: List[Identity] = []
    seen_user_ids: Set[str] = set()

    for line_no, r in rows:
        user_id, name, email_raw, phone_raw, email_hash, updated_at_raw = r
        if user_id in seen_user_ids:
            report.duplicate_pk_errors.append(f"Duplicate user_id '{user_id}' at {fn}:{line_no}")
        seen_user_ids.add(user_id)

        email_norm = normalize_email(email_raw)
        if email_norm is None:
            report.normalization_issues["identity_empty_email"] += 1

        phone_norm = normalize_phone(phone_raw)
        if phone_norm is None:
            report.normalization_issues["identity_empty_phone"] += 1

        updated_at = process_timestamp(updated_at_raw, fn, line_no)

        identities.append(
            Identity(
                user_id=user_id,
                name=name,
                email_raw=email_raw,
                email_norm=email_norm,
                phone_raw=phone_raw,
                phone_norm=phone_norm,
                email_hash=email_hash,
                updated_at_raw=updated_at_raw,
                updated_at=updated_at,
                source=SourceRef(file=fn, row_number=line_no),
            )
        )

    # 2. user_audit_log.csv
    audit_path = os.path.join(data_dir, "user_audit_log.csv")
    _, rows = _read_csv_rows(audit_path)
    fn = "user_audit_log.csv"
    report.row_counts[fn] = len(rows)
    audit_events: List[AuditEvent] = []
    seen_audit_ids: Set[str] = set()

    for line_no, r in rows:
        audit_id, user_id, event_time_raw, field_name, old_val_raw, new_val_raw = r
        if audit_id in seen_audit_ids:
            report.duplicate_pk_errors.append(f"Duplicate audit_id '{audit_id}' at {fn}:{line_no}")
        seen_audit_ids.add(audit_id)

        event_time = process_timestamp(event_time_raw, fn, line_no)

        audit_events.append(
            AuditEvent(
                audit_id=audit_id,
                user_id=user_id,
                field_name=field_name,
                old_value_raw=old_val_raw,
                new_value_raw=new_val_raw,
                changed_at_raw=event_time_raw,
                changed_at=event_time,
                source=SourceRef(file=fn, row_number=line_no),
            )
        )

    # 3. system_activity.csv
    sys_path = os.path.join(data_dir, "system_activity.csv")
    _, rows = _read_csv_rows(sys_path)
    fn = "system_activity.csv"
    report.row_counts[fn] = len(rows)
    system_activities: List[SystemActivity] = []
    seen_act_ids: Set[str] = set()

    for line_no, r in rows:
        act_id, ev_time_raw, ev_type, src_sys, tgt_sys, res_id, rep_res, details = r
        if act_id in seen_act_ids:
            report.duplicate_pk_errors.append(f"Duplicate activity_id '{act_id}' at {fn}:{line_no}")
        seen_act_ids.add(act_id)

        ev_time = process_timestamp(ev_time_raw, fn, line_no)

        system_activities.append(
            SystemActivity(
                activity_id=act_id,
                event_time_raw=ev_time_raw,
                event_time=ev_time,
                event_type=ev_type,
                source_system=src_sys,
                target_system=tgt_sys,
                resource_id=res_id,
                reported_result=rep_res,
                details=details,
                source=SourceRef(file=fn, row_number=line_no),
            )
        )

    # 4. deletion_rules.csv
    rules_path = os.path.join(data_dir, "deletion_rules.csv")
    _, rows = _read_csv_rows(rules_path)
    fn = "deletion_rules.csv"
    report.row_counts[fn] = len(rows)
    deletion_rules: List[DeletionRule] = []
    seen_rule_ids: Set[str] = set()

    for line_no, r in rows:
        rule_id, category, condition, action = r
        if rule_id in seen_rule_ids:
            report.duplicate_pk_errors.append(f"Duplicate rule_id '{rule_id}' at {fn}:{line_no}")
        seen_rule_ids.add(rule_id)

        deletion_rules.append(
            DeletionRule(
                rule_id=rule_id,
                data_category=category,
                condition=condition,
                required_action=action,
                source=SourceRef(file=fn, row_number=line_no),
            )
        )

    # 5. evidence_files.csv
    ev_files_path = os.path.join(data_dir, "evidence_files.csv")
    _, rows = _read_csv_rows(ev_files_path)
    fn = "evidence_files.csv"
    report.row_counts[fn] = len(rows)
    evidence_files: List[EvidenceFile] = []
    seen_file_ids: Set[str] = set()

    for line_no, r in rows:
        file_id, file_path, origin, cap_time_raw = r
        if file_id in seen_file_ids:
            report.duplicate_pk_errors.append(f"Duplicate file_id '{file_id}' at {fn}:{line_no}")
        seen_file_ids.add(file_id)

        cap_time = process_timestamp(cap_time_raw, fn, line_no)

        evidence_files.append(
            EvidenceFile(
                file_id=file_id,
                file_path=file_path,
                origin=origin,
                captured_at_raw=cap_time_raw,
                captured_at=cap_time,
                source=SourceRef(file=fn, row_number=line_no),
            )
        )

    # 6. deletion_requests.csv
    del_path = os.path.join(data_dir, "deletion_requests.csv")
    _, rows = _read_csv_rows(del_path)
    fn = "deletion_requests.csv"
    report.row_counts[fn] = len(rows)
    deletion_requests: List[DeletionRequest] = []
    seen_case_ids: Set[str] = set()

    for line_no, r in rows:
        cid, email_raw, req_at_raw, rep_stat, rep_at_raw, audit_at_raw, req_text = r
        if cid in seen_case_ids:
            report.duplicate_pk_errors.append(f"Duplicate case_id '{cid}' at {fn}:{line_no}")
        seen_case_ids.add(cid)

        email_norm = normalize_email(email_raw)
        if email_norm is None:
            report.normalization_issues["request_empty_email"] += 1

        req_at = process_timestamp(req_at_raw, fn, line_no)
        rep_at = process_timestamp(rep_at_raw, fn, line_no)
        audit_at = process_timestamp(audit_at_raw, fn, line_no)

        deletion_requests.append(
            DeletionRequest(
                case_id=cid,
                email_raw=email_raw,
                email_norm=email_norm,
                requested_at_raw=req_at_raw,
                requested_at=req_at,
                reported_status=rep_stat,
                reported_at_raw=rep_at_raw,
                reported_at=rep_at,
                audit_at_raw=audit_at_raw,
                audit_at=audit_at,
                request_text=req_text,
                source=SourceRef(file=fn, row_number=line_no),
            )
        )

    # 7. sample_deletion_requests.csv
    sample_del_path = os.path.join(data_dir, "sample_deletion_requests.csv")
    sample_deletion_requests: List[DeletionRequest] = []
    if os.path.isfile(sample_del_path):
        _, rows = _read_csv_rows(sample_del_path)
        fn = "sample_deletion_requests.csv"
        report.row_counts[fn] = len(rows)
        seen_sample_cids: Set[str] = set()

        for line_no, r in rows:
            cid, email_raw, req_at_raw, rep_stat, rep_at_raw, audit_at_raw, req_text = r
            if cid in seen_sample_cids:
                report.duplicate_pk_errors.append(f"Duplicate case_id '{cid}' at {fn}:{line_no}")
            seen_sample_cids.add(cid)

            email_norm = normalize_email(email_raw)
            req_at = process_timestamp(req_at_raw, fn, line_no)
            rep_at = process_timestamp(rep_at_raw, fn, line_no)
            audit_at = process_timestamp(audit_at_raw, fn, line_no)

            sample_deletion_requests.append(
                DeletionRequest(
                    case_id=cid,
                    email_raw=email_raw,
                    email_norm=email_norm,
                    requested_at_raw=req_at_raw,
                    requested_at=req_at,
                    reported_status=rep_stat,
                    reported_at_raw=rep_at_raw,
                    reported_at=rep_at,
                    audit_at_raw=audit_at_raw,
                    audit_at=audit_at,
                    request_text=req_text,
                    source=SourceRef(file=fn, row_number=line_no),
                )
            )

    # Record row counts for any remaining dataset files without reading sample output in production
    for fname in sorted(os.listdir(data_dir)):
        if fname.endswith(".csv") and fname not in report.row_counts:
            fpath = os.path.join(data_dir, fname)
            if os.path.isfile(fpath):
                with open(fpath, "r", encoding="utf-8") as f:
                    cnt = sum(1 for line in f if line.strip()) - 1
                    report.row_counts[fname] = max(0, cnt)

    sample_output: List[Dict[str, Any]] = []

    return Dataset(
        data_dir=data_dir,
        deletion_requests=deletion_requests,
        sample_deletion_requests=sample_deletion_requests,
        sample_output=sample_output,
        user_identities=identities,
        user_audit_log=audit_events,
        system_activity=system_activities,
        deletion_rules=deletion_rules,
        evidence_files=evidence_files,
        report=report,
    )
