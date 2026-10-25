"""
Regression tests for Safe Log Recovery, Multi-format Parsing, Trace-ID Correlation,
and Completion Validation under Step R.
"""

import os
import tempfile
import pytest

from code.src.evidence_extraction import LogRecordExtractor, ExtractedObservation
from code.src.state_reconstruction import ResourceState


def test_log_extractor_bracketed_format():
    """Verify standard bracketed format parsing."""
    content = (
        "[2026-09-10T12:00:00Z] [INFO] [account_service] event=profile_lookup_completed "
        "user_id=usr_001 resource_id=account_101 rows=0 http_status=404\n"
    )
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".log") as f:
        f.write(content)
        f.flush()
        temp_path = f.name

    try:
        extractor = LogRecordExtractor()
        obs = extractor.extract(temp_path, "ev_001")
        assert len(obs) == 1
        assert obs[0].resource_id == "account_101"
        assert obs[0].observed_state == ResourceState.ABSENT
        assert obs[0].associated_identifiers.get("user_id") == "usr_001"
        assert obs[0].evidence_id == "ev_001"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_log_extractor_pipe_and_unbracketed_format():
    """Verify pipe-delimited and unbracketed format parsing."""
    content = (
        "2026-09-11T08:30:00Z | INFO | audit_logger | event=audit_record_read_completed "
        "user_id=usr_002 resource_id=audit_record_202 rows=1\n"
        "2026-09-11T09:00:00Z INFO connector_mgr event=connector_config_read_completed "
        "resource_id=data_flow_303 enabled=false\n"
    )
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".log") as f:
        f.write(content)
        f.flush()
        temp_path = f.name

    try:
        extractor = LogRecordExtractor()
        obs = extractor.extract(temp_path, "ev_002")
        assert len(obs) == 2
        assert obs[0].resource_id == "audit_record_202"
        assert obs[0].observed_state == ResourceState.PRESENT
        assert obs[1].resource_id == "data_flow_303"
        assert obs[1].observed_state == ResourceState.DISABLED
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_log_extractor_trace_id_correlation():
    """
    Verify two-pass trace-id correlation links identifiers across multi-line events
    (e.g., as in Case 15 where start event has email and completion has resource_id).
    """
    content = (
        "2026-09-12T10:00:00Z INFO worker event=data_flow_scan_started subject_key=lucia@example.com trace_id=tr-9999\n"
        "2026-09-12T10:00:05Z INFO worker event=connector_heartbeat resource_id=data_flow_9846 enabled=true trace_id=tr-9999\n"
    )
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".log") as f:
        f.write(content)
        f.flush()
        temp_path = f.name

    try:
        extractor = LogRecordExtractor()
        obs = extractor.extract(temp_path, "ev_003")
        # Line 1 is a scan_started claim, Line 2 is connector_heartbeat
        assert len(obs) == 2
        # The second observation (connector_heartbeat) should inherit the email from trace_id
        heartbeat_obs = next(o for o in obs if o.resource_id == "data_flow_9846")
        assert heartbeat_obs.observed_state == ResourceState.ACTIVE
        assert heartbeat_obs.associated_identifiers.get("email") == "lucia@example.com"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_log_extractor_hex_email_hash_recognition():
    """
    Verify 64-char hex strings in correlation_key/lookup_key are recognized as email_hash
    (e.g., as in Case 12 where historical email hash links analytics_9914).
    """
    hex_hash = "44a65154bfd8c6b7538bdf5baecde9b0091391d1469e5d773418c39757fef486"
    content = (
        f"2026-09-13T14:00:00Z INFO analytics event=analytics_profile_read_completed "
        f"resource_id=analytics_9914 correlation_key={hex_hash} email_hash={hex_hash} rows=1\n"
    )
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".log") as f:
        f.write(content)
        f.flush()
        temp_path = f.name

    try:
        extractor = LogRecordExtractor()
        obs = extractor.extract(temp_path, "ev_004")
        assert len(obs) == 1
        assert obs[0].resource_id == "analytics_9914"
        assert obs[0].observed_state == ResourceState.PRESENT
        assert obs[0].associated_identifiers.get("email_hash") == hex_hash
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_plain_text_extractor_extended_states():
    """Verify PlainTextExtractor recognizes REDACTED, ANONYMIZED, DISABLED, BLOCKED states."""
    from code.src.evidence_extraction import PlainTextExtractor

    content = (
        "- 2026-09-10T12:00:00Z | support_platform | support_101 | SUPPORT_TICKET | REDACTED | user_001\n"
        "- 2026-09-10T12:00:00Z | analytics_platform | analytics_202 | ANALYTICS_PROFILE | ANONYMIZED | user_001\n"
        "- 2026-09-10T12:00:00Z | integration_service | data_flow_303 | DATA_FLOW | DISABLED | user_001\n"
        "- 2026-09-10T12:00:00Z | backup_service | backup_404 | BACKUP_ARCHIVE | BLOCKED | user_001\n"
    )
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt") as f:
        f.write(content)
        f.flush()
        temp_path = f.name

    try:
        extractor = PlainTextExtractor()
        obs = extractor.extract(temp_path, "ev_005")
        states = {o.resource_id: o.observed_state for o in obs}
        assert states.get("support_101") == ResourceState.REDACTED
        assert states.get("analytics_202") == ResourceState.ANONYMIZED
        assert states.get("data_flow_303") == ResourceState.DISABLED
        assert states.get("backup_404") == ResourceState.BLOCKED
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
