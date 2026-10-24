"""code/src/evidence_extraction.py

Multi-Modality Evidence Extraction Adapters for HackerRank Orchestrate: Ghost Data Still Exists.

Extracts structured, provenance-backed factual observations across all evidence modalities:
- JSON evidence records (dataset/evidence/records/*.json)
- Relational SQL snapshots (dataset/evidence/databases/*.sql)
- Structured application & runtime logs (dataset/evidence/logs/*.log)
- Plain-text handover & audit records (dataset/evidence/records/*.txt)
- PDF compliance & history documents (dataset/evidence/documents/*.pdf)

Preserves exact source file, table/line/page location, timestamps, subject identifiers,
resource identifiers, observed operational states, extraction method, and confidence flags.
Does not invent evidence or fabricate relationships without source corroboration.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import logging
import os
import re
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Standard library module 'code' conflict resolution
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if "code" in sys.modules and not hasattr(sys.modules["code"], "src"):
    del sys.modules["code"]

try:
    from code.src.models import EvidenceFile
    from code.src.normalize import normalize_email, normalize_phone, normalize_timestamp
    from code.src.state_reconstruction import (
        EvidenceObservation,
        ResourceState,
        ensure_utc,
        parse_timestamp_to_utc,
    )
except ImportError:
    from src.models import EvidenceFile
    from src.normalize import normalize_email, normalize_phone, normalize_timestamp
    from src.state_reconstruction import (
        EvidenceObservation,
        ResourceState,
        ensure_utc,
        parse_timestamp_to_utc,
    )

logger = logging.getLogger("nulltrace.evidence_extraction")


class ObservationConfidence(str, Enum):
    """Confidence level of an extracted observation."""
    HIGH = "HIGH"                              # Direct factual observation
    MEDIUM = "MEDIUM"                          # Corroborated cross-field observation
    UNVERIFIED_CLAIM = "UNVERIFIED_CLAIM"      # Logged intent, start event, or unproven claim
    AMBIGUOUS = "AMBIGUOUS"                    # Multiple possible interpretations or conflicting signals


@dataclass
class ExtractedObservation:
    """Standardized factual observation extracted from an evidence file."""
    source_file: str                                       # Relative path (e.g. evidence/databases/...)
    file_id: str                                           # Evidence manifest ID (e.g. evidence_05)
    evidence_id: str                                       # file_id or specific entry reference
    source_location: str                                   # Table:row, line_no, or page_no
    observation_type: str                                  # RECORD_SNAPSHOT, LOOKUP_RESULT, LOG_CLAIM, DOCUMENT_TEXT, etc.
    extraction_method: str                                 # JSON_PARSER, SQL_PARSER, LOG_PARSER, PDF_PARSER, TEXT_PARSER
    confidence: ObservationConfidence
    timestamp: Optional[datetime] = None                   # UTC timestamp of observation
    resource_id: Optional[str] = None                      # Grounded resource identifier
    system_id: Optional[str] = None                        # Originating system identifier
    associated_identifiers: Dict[str, str] = field(default_factory=dict) # kind -> normalized value
    observed_state: Optional[ResourceState] = None         # Determinable resource state
    raw_payload: Dict[str, Any] = field(default_factory=dict)
    ambiguity_flags: List[str] = field(default_factory=list)

    def to_evidence_observation(self) -> Optional[EvidenceObservation]:
        """Converts to state_reconstruction.EvidenceObservation if resource_id and state are present."""
        if not self.resource_id or self.observed_state is None:
            return None
        return EvidenceObservation(
            resource_id=self.resource_id,
            observed_state=self.observed_state,
            timestamp=self.timestamp,
            evidence_id=self.evidence_id,
            source_path=self.source_file,
            is_direct=(self.confidence == ObservationConfidence.HIGH),
            details=self.raw_payload,
            collection=self.raw_payload.get("collection") or self.raw_payload.get("table"),
            system_id=self.system_id,
        )


class JsonRecordExtractor:
    """Extractor for structured JSON snapshot bundles in evidence/records/*.json."""

    @staticmethod
    def extract(file_path: str, file_id: str, file_cap_time: Optional[datetime] = None) -> List[ExtractedObservation]:
        observations: List[ExtractedObservation] = []
        if not os.path.isfile(file_path):
            return observations

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        snapshots = data.get("snapshots", [])
        for snap_idx, snap in enumerate(snapshots):
            snap_time = parse_timestamp_to_utc(snap.get("captured_at")) or file_cap_time
            store = snap.get("data_store")
            coll = snap.get("collection")
            records = snap.get("records", [])

            for rec_idx, rec in enumerate(records):
                rid = rec.get("resource_id")
                loc = f"snap_{snap_idx}:{coll or 'records'}:{rec_idx}"

                # Extract associated identifiers
                idents: Dict[str, str] = {}
                for k in ("email", "user_email", "customer_email"):
                    if rec.get(k):
                        norm_e = normalize_email(str(rec[k]))
                        if norm_e:
                            idents["email"] = norm_e
                for k in ("phone", "user_phone", "mobile"):
                    if rec.get(k):
                        norm_p = normalize_phone(str(rec[k]))
                        if norm_p:
                            idents["phone"] = norm_p
                for k in ("user_id", "subject_reference", "subject_id", "account_id"):
                    if rec.get(k) and str(rec[k]).startswith("user_"):
                        idents["user_id"] = str(rec[k]).strip()
                if rec.get("email_hash"):
                    idents["email_hash"] = str(rec["email_hash"]).strip().lower()

                # Determine state and observation type
                state = ResourceState.UNKNOWN
                rec_time = parse_timestamp_to_utc(rec.get("recorded_at") or rec.get("updated_at")) or snap_time

                if "operational_record_history" in str(coll):
                    res = str(rec.get("result", "")).upper()
                    mapping = {
                        "FOUND": ResourceState.PRESENT,
                        "NOT_FOUND": ResourceState.ABSENT,
                        "ANONYMIZED": ResourceState.ANONYMIZED,
                        "IDENTIFIABLE": ResourceState.PRESENT,
                        "REDACTED": ResourceState.REDACTED,
                        "ACTIVE": ResourceState.ACTIVE,
                        "DISABLED": ResourceState.DISABLED,
                        "BLOCKED": ResourceState.BLOCKED,
                    }
                    state = mapping.get(res, ResourceState.UNKNOWN)
                    obs_type = "OPERATIONAL_HISTORY"
                elif coll == "connector_configurations":
                    state = ResourceState.ACTIVE if rec.get("enabled", True) else ResourceState.DISABLED
                    obs_type = "CONNECTOR_CONFIG"
                elif coll == "backup_catalog":
                    state = ResourceState.ACTIVE if rec.get("restore_allowed", True) else ResourceState.BLOCKED
                    obs_type = "BACKUP_CATALOG"
                elif coll == "deleted_customer_references":
                    has_direct_pii = any(bool(rec.get(k)) for k in ("name", "email", "phone", "email_hash"))
                    state = ResourceState.PRESENT if has_direct_pii else ResourceState.REDACTED
                    obs_type = "TOMBSTONE_RECORD"
                else:
                    state = ResourceState.PRESENT
                    obs_type = "DATA_RECORD"

                observations.append(
                    ExtractedObservation(
                        source_file=file_path,
                        file_id=file_id,
                        evidence_id=file_id,
                        source_location=loc,
                        observation_type=obs_type,
                        extraction_method="JSON_PARSER",
                        confidence=ObservationConfidence.HIGH,
                        timestamp=rec_time,
                        resource_id=rid,
                        system_id=store,
                        associated_identifiers=idents,
                        observed_state=state,
                        raw_payload=rec,
                    )
                )

        return observations


class SqlSnapshotExtractor:
    """Extractor for relational SQL point-in-time database snapshots in evidence/databases/*.sql."""

    @staticmethod
    def extract(file_path: str, file_id: str, file_cap_time: Optional[datetime] = None) -> List[ExtractedObservation]:
        observations: List[ExtractedObservation] = []
        if not os.path.isfile(file_path):
            return observations

        with open(file_path, "r", encoding="utf-8") as f:
            sql_script = f.read()

        # Parse captured_at comment if available
        cap_match = re.search(r"--\s*Captured at:\s*(\S+)", sql_script)
        snap_time = file_cap_time
        if cap_match:
            parsed = parse_timestamp_to_utc(cap_match.group(1))
            if parsed:
                snap_time = parsed

        # Execute safely in an in-memory SQLite database
        conn = sqlite3.connect(":memory:")
        try:
            # Custom function for json_valid compatibility
            conn.create_function("json_valid", 1, lambda val: 1)
            conn.executescript(sql_script)

            # Discover all user tables
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = [row[0] for row in cursor.fetchall()]

            for tbl in tables:
                # Inspect columns
                cursor.execute(f"PRAGMA table_info('{tbl}');")
                col_info = cursor.fetchall()
                col_names = [c[1] for c in col_info]

                # Inspect foreign keys
                cursor.execute(f"PRAGMA foreign_key_list('{tbl}');")
                fk_info = cursor.fetchall()
                has_declared_fk = len(fk_info) > 0

                # Read all rows
                cursor.execute(f"SELECT * FROM '{tbl}';")
                rows = cursor.fetchall()

                for row_idx, row_vals in enumerate(rows):
                    row_dict = dict(zip(col_names, row_vals))
                    rid = row_dict.get("resource_id")
                    loc = f"{tbl}:{row_idx}"
                    idents: Dict[str, str] = {}
                    ambiguity: List[str] = []
                    if not has_declared_fk:
                        ambiguity.append("NO_DECLARED_FOREIGN_KEY")

                    # Check for direct columns
                    if row_dict.get("email"):
                        norm_e = normalize_email(str(row_dict["email"]))
                        if norm_e:
                            idents["email"] = norm_e
                    if row_dict.get("phone"):
                        norm_p = normalize_phone(str(row_dict["phone"]))
                        if norm_p:
                            idents["phone"] = norm_p
                    if row_dict.get("user_id"):
                        idents["user_id"] = str(row_dict["user_id"]).strip()

                    row_ts = parse_timestamp_to_utc(row_dict.get("updated_at") or row_dict.get("created_at")) or snap_time
                    sys_id = row_dict.get("origin_system")

                    # Check for nested JSON column (e.g. record_json)
                    if "record_json" in row_dict:
                        try:
                            nested = json.loads(str(row_dict["record_json"]))
                            if not rid and nested.get("resource_id"):
                                rid = nested.get("resource_id")
                            if nested.get("subject_reference"):
                                idents["user_id"] = str(nested["subject_reference"]).strip()
                            if nested.get("email"):
                                norm_e = normalize_email(str(nested["email"]))
                                if norm_e:
                                    idents["email"] = norm_e
                            if nested.get("phone"):
                                norm_p = normalize_phone(str(nested["phone"]))
                                if norm_p:
                                    idents["phone"] = norm_p
                            if nested.get("email_hash"):
                                idents["email_hash"] = str(nested["email_hash"]).strip().lower()

                            # State inference for nested JSON
                            coll_name = str(row_dict.get("collection_name", ""))
                            if "tombstone" in str(rid) or "deleted_customer" in coll_name:
                                has_pii = any(bool(nested.get(k)) for k in ("name", "email", "phone", "email_hash"))
                                st = ResourceState.PRESENT if has_pii else ResourceState.REDACTED
                                obs_type = "SQL_TOMBSTONE_RECORD"
                            else:
                                st = ResourceState.PRESENT
                                obs_type = "SQL_JSON_RECORD"

                            row_dict["_parsed_json"] = nested
                        except Exception:
                            st = ResourceState.PRESENT
                            obs_type = "SQL_RECORD"
                    else:
                        st = ResourceState.PRESENT
                        obs_type = "SQL_TABLE_ROW"

                    observations.append(
                        ExtractedObservation(
                            source_file=file_path,
                            file_id=file_id,
                            evidence_id=file_id,
                            source_location=loc,
                            observation_type=obs_type,
                            extraction_method="SQL_PARSER",
                            confidence=ObservationConfidence.HIGH,
                            timestamp=row_ts,
                            resource_id=str(rid) if rid else None,
                            system_id=str(sys_id) if sys_id else None,
                            associated_identifiers=idents,
                            observed_state=st,
                            raw_payload=row_dict,
                            ambiguity_flags=ambiguity,
                        )
                    )
        except Exception as e:
            logger.error(f"SQL execution error on {file_path}: {e}")
            raise
        finally:
            conn.close()

        return observations


class LogRecordExtractor:
    """Extractor for structured application and platform event logs in evidence/logs/*.log."""

    # Regex for standard bracketed log format
    _RE_BRACKET = re.compile(
        r"^(\S+)\s+\[(\w+)\]\s+\[([\w\-]+)\]\s+\[([\w\-]+)\]\s+([\w\-]+):\s*(.*)$"
    )
    # Regex for key-value runtime export format
    _RE_KV = re.compile(
        r"^(\S+)\s+requestId=([\w\-]+)\s+level=(\w+)\s+function=([\w\-]+)\s+message=\"(.*)\"$"
    )
    # Key-value pair extractor inside message strings
    _RE_FIELDS = re.compile(r'(\w+)="([^"]*)"')

    @staticmethod
    def extract(file_path: str, file_id: str, file_cap_time: Optional[datetime] = None) -> List[ExtractedObservation]:
        observations: List[ExtractedObservation] = []
        if not os.path.isfile(file_path):
            return observations

        with open(file_path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, start=1):
                clean_line = line.strip()
                if not clean_line:
                    continue

                ts: Optional[datetime] = None
                sys_id: Optional[str] = None
                event_name: str = ""
                fields: Dict[str, str] = {}
                raw_payload: Dict[str, Any] = {"line": clean_line}

                # Try bracket format
                m_b = LogRecordExtractor._RE_BRACKET.match(clean_line)
                if m_b:
                    ts = parse_timestamp_to_utc(m_b.group(1)) or file_cap_time
                    sys_id = m_b.group(3)
                    event_name = m_b.group(5)
                    raw_payload["level"] = m_b.group(2)
                    raw_payload["trace_id"] = m_b.group(4)
                    raw_payload["event_name"] = event_name
                    rest = m_b.group(6)
                    for k, v in LogRecordExtractor._RE_FIELDS.findall(rest):
                        fields[k] = v
                else:
                    # Try KV format
                    m_kv = LogRecordExtractor._RE_KV.match(clean_line)
                    if m_kv:
                        ts = parse_timestamp_to_utc(m_kv.group(1)) or file_cap_time
                        sys_id = m_kv.group(4)
                        raw_payload["requestId"] = m_kv.group(2)
                        raw_payload["level"] = m_kv.group(3)
                        msg = m_kv.group(5).replace('\\"', '"')
                        for k, v in LogRecordExtractor._RE_FIELDS.findall(msg):
                            fields[k] = v
                        event_name = fields.get("event", "log_event")
                    else:
                        continue

                raw_payload.update(fields)
                rid = fields.get("resource_id")
                loc = f"line_{line_idx}"

                # Extract associated subject identifiers
                idents: Dict[str, str] = {}
                for key_name in ("lookup_key", "subject_key", "correlation_key", "email", "user_email"):
                    if key_name in fields:
                        val = fields[key_name]
                        if "@" in val:
                            norm_e = normalize_email(val)
                            if norm_e:
                                idents["email"] = norm_e
                        elif val.startswith("user_"):
                            idents["user_id"] = val
                        elif re.search(r"\d{7,}", val):
                            norm_p = normalize_phone(val)
                            if norm_p:
                                idents["phone"] = norm_p

                # Distinguish observed outcomes from logged claims
                obs_state: Optional[ResourceState] = None
                conf = ObservationConfidence.HIGH
                ambiguity: List[str] = []

                if "profile_lookup_completed" in event_name or fields.get("event") == "profile_lookup_completed":
                    rows = fields.get("rows")
                    status = fields.get("http_status")
                    if rows == "0" or status == "404":
                        obs_state = ResourceState.ABSENT
                        obs_type = "LOOKUP_RESULT_ABSENT"
                    elif rows == "1" or status == "200":
                        obs_state = ResourceState.PRESENT
                        obs_type = "LOOKUP_RESULT_PRESENT"
                    else:
                        obs_state = ResourceState.UNKNOWN
                        obs_type = "LOOKUP_RESULT_UNKNOWN"
                elif "export_started" in event_name or "lookup_started" in event_name or "scan_started" in event_name:
                    obs_type = "LOG_CLAIM"
                    conf = ObservationConfidence.UNVERIFIED_CLAIM
                    obs_state = None
                    ambiguity.append("UNCORROBORATED_START_CLAIM")
                elif "delivery_abandoned" in event_name:
                    obs_type = "LOG_FAILURE"
                    conf = ObservationConfidence.HIGH
                    obs_state = None
                else:
                    obs_type = "SYSTEM_LOG_EVENT"
                    conf = ObservationConfidence.MEDIUM

                observations.append(
                    ExtractedObservation(
                        source_file=file_path,
                        file_id=file_id,
                        evidence_id=file_id,
                        source_location=loc,
                        observation_type=obs_type,
                        extraction_method="LOG_PARSER",
                        confidence=conf,
                        timestamp=ts,
                        resource_id=rid,
                        system_id=sys_id,
                        associated_identifiers=idents,
                        observed_state=obs_state,
                        raw_payload=raw_payload,
                        ambiguity_flags=ambiguity,
                    )
                )

        return observations


class PlainTextExtractor:
    """Extractor for structured plain-text handover reports and lists (e.g. *.txt)."""

    @staticmethod
    def extract(file_path: str, file_id: str, file_cap_time: Optional[datetime] = None) -> List[ExtractedObservation]:
        observations: List[ExtractedObservation] = []
        if not os.path.isfile(file_path):
            return observations

        with open(file_path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, start=1):
                clean = line.strip()
                if not clean.startswith("- "):
                    continue

                parts = [p.strip() for p in clean[2:].split("|")]
                if len(parts) >= 5:
                    ts_str, sys_id, rid, cat, outcome = parts[:5]
                    ts = parse_timestamp_to_utc(ts_str) or file_cap_time
                    idents: Dict[str, str] = {}
                    if len(parts) >= 6:
                        raw_id = parts[5]
                        if "@" in raw_id:
                            ne = normalize_email(raw_id)
                            if ne:
                                idents["email"] = ne
                        elif raw_id.startswith("user_"):
                            idents["user_id"] = raw_id

                    st = ResourceState.UNKNOWN
                    if outcome.upper() == "NOT_FOUND":
                        st = ResourceState.ABSENT
                    elif outcome.upper() in ("FOUND", "ACTIVE", "PRESENT"):
                        st = ResourceState.PRESENT

                    observations.append(
                        ExtractedObservation(
                            source_file=file_path,
                            file_id=file_id,
                            evidence_id=file_id,
                            source_location=f"line_{line_idx}",
                            observation_type="HANDOVER_CHECK",
                            extraction_method="TEXT_PARSER",
                            confidence=ObservationConfidence.HIGH,
                            timestamp=ts,
                            resource_id=rid,
                            system_id=sys_id,
                            associated_identifiers=idents,
                            observed_state=st,
                            raw_payload={"line": clean, "category": cat, "outcome": outcome},
                        )
                    )

        return observations


class PdfDocumentExtractor:
    """Extractor for PDF documents using pypdf."""

    @staticmethod
    def extract(file_path: str, file_id: str, file_cap_time: Optional[datetime] = None) -> Tuple[List[ExtractedObservation], bool]:
        """
        Returns (observations, requires_ocr).
        Extracts usable text locally, records page numbers, and flags scanned/empty pages.
        """
        observations: List[ExtractedObservation] = []
        requires_ocr = False
        if not os.path.isfile(file_path):
            return observations, requires_ocr

        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            for page_idx, page in enumerate(reader.pages, start=1):
                text = (page.extract_text() or "").strip()
                if not text or len(text) < 20:
                    requires_ocr = True
                    continue

                # Scan for identifiers in page text
                idents: Dict[str, str] = {}
                emails = re.findall(r"[\w\.\+\-]+@[\w\.\-]+\.[a-zA-Z]{2,}", text)
                for e in emails:
                    norm_e = normalize_email(e)
                    if norm_e:
                        idents["email"] = norm_e

                phones = re.findall(r"\+?\d[\d\s\-]{8,}\d", text)
                for p in phones:
                    norm_p = normalize_phone(p)
                    if norm_p:
                        idents["phone"] = norm_p

                users = re.findall(r"\buser_\d+\b", text)
                for u in users:
                    idents["user_id"] = u

                resources = re.findall(r"\b(?:account|support|audit_record|backup|search|export|tombstone)_\d+\b", text)
                primary_rid = resources[0] if resources else None

                observations.append(
                    ExtractedObservation(
                        source_file=file_path,
                        file_id=file_id,
                        evidence_id=file_id,
                        source_location=f"page_{page_idx}",
                        observation_type="DOCUMENT_PAGE_TEXT",
                        extraction_method="PDF_PARSER",
                        confidence=ObservationConfidence.MEDIUM,
                        timestamp=file_cap_time,
                        resource_id=primary_rid,
                        system_id="document_repository",
                        associated_identifiers=idents,
                        observed_state=ResourceState.PRESENT if (idents or primary_rid) else None,
                        raw_payload={"page_num": page_idx, "snippet": text[:300]},
                    )
                )
        except Exception as exc:
            logger.warning(f"PDF extraction error on {file_path}: {exc}")
            requires_ocr = True

        return observations, requires_ocr
