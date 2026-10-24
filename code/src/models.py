"""code/src/models.py

Typed dataclasses representing entities loaded from dataset CSV files.
Preserves raw values alongside normalized fields and attaches 1-based SourceRefs.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class SourceRef:
    """Represents the provenance of a loaded record."""
    file: str
    row_number: int  # 1-based line number in file (line 1 is header, line 2 is first data row)


@dataclass
class Identity:
    """Represents a row from user_identities.csv."""
    user_id: str
    name: str
    email_raw: str
    email_norm: Optional[str]
    phone_raw: str
    phone_norm: Optional[str]
    email_hash: str
    updated_at_raw: str
    updated_at: Optional[datetime]
    source: SourceRef


@dataclass
class AuditEvent:
    """Represents a row from user_audit_log.csv."""
    audit_id: str
    user_id: str
    field_name: str
    old_value_raw: str
    new_value_raw: str
    changed_at_raw: str  # maps to CSV column 'event_time'
    changed_at: Optional[datetime]  # parsed UTC datetime
    source: SourceRef

    @property
    def event_time_raw(self) -> str:
        return self.changed_at_raw

    @property
    def event_time(self) -> Optional[datetime]:
        return self.changed_at


@dataclass
class SystemActivity:
    """Represents a row from system_activity.csv."""
    activity_id: str
    event_time_raw: str
    event_time: Optional[datetime]
    event_type: str
    source_system: str
    target_system: str
    resource_id: str
    reported_result: str
    details: str
    source: SourceRef


@dataclass
class DeletionRule:
    """Represents a row from deletion_rules.csv."""
    rule_id: str
    data_category: str
    condition: str
    required_action: str
    source: SourceRef


@dataclass
class DeletionRequest:
    """Represents a row from deletion_requests.csv or sample_deletion_requests.csv."""
    case_id: str
    email_raw: str
    email_norm: Optional[str]
    requested_at_raw: str
    requested_at: Optional[datetime]
    reported_status: str
    reported_at_raw: str
    reported_at: Optional[datetime]
    audit_at_raw: str
    audit_at: Optional[datetime]
    request_text: str
    source: SourceRef


@dataclass
class EvidenceFile:
    """Represents a row from evidence_files.csv."""
    file_id: str
    file_path: str
    origin: str
    captured_at_raw: str
    captured_at: Optional[datetime]
    source: SourceRef
