"""code/tests/test_loader.py

Tests for dataset loading, normalization, row counts, round-trip fidelity,
source tracing, and error detection.
"""

from datetime import datetime, timezone
import os
import sys
import tempfile
import pytest

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if "code" in sys.modules and not hasattr(sys.modules["code"], "src"):
    del sys.modules["code"]

try:
    from code.src.normalize import (
        normalize_email,
        normalize_phone,
        normalize_timestamp,
        TimestampFormatError,
    )
    from code.src.loader import (
        load_dataset,
        EmptyRowError,
        MalformedRowError,
        LoaderError,
    )
except ImportError:
    from src.normalize import (
        normalize_email,
        normalize_phone,
        normalize_timestamp,
        TimestampFormatError,
    )
    from src.loader import (
        load_dataset,
        EmptyRowError,
        MalformedRowError,
        LoaderError,
    )


# Exact expected row counts recorded in SPEC_EXTRACTED.md
SPEC_ROW_COUNTS = {
    "deletion_requests.csv": 518,
    "sample_deletion_requests.csv": 32,
    "sample_output.csv": 32,
    "user_identities.csv": 850,
    "user_audit_log.csv": 306,
    "system_activity.csv": 4011,
    "deletion_rules.csv": 15,
    "evidence_files.csv": 94,
}


def test_row_counts_against_spec():
    """Verify that row counts read from the dataset match the spec document."""
    spec_path = os.path.join(_repo_root, "code", "docs", "SPEC_EXTRACTED.md")
    assert os.path.isfile(spec_path), "SPEC_EXTRACTED.md must exist"

    with open(spec_path, "r", encoding="utf-8") as f:
        spec_text = f.read()

    # Confirm that SPEC_EXTRACTED.md contains the exact numbers
    for filename, count in SPEC_ROW_COUNTS.items():
        assert f"`{filename}`" in spec_text or filename in spec_text
        assert str(count) in spec_text

    dataset = load_dataset(os.path.join(_repo_root, "dataset"))
    for filename, expected_count in SPEC_ROW_COUNTS.items():
        actual_count = dataset.report.row_counts.get(filename)
        assert actual_count == expected_count, (
            f"Row count mismatch for {filename}: expected {expected_count}, got {actual_count}"
        )


def test_normalize_email():
    """Test email normalization preserving plus-addressing, trimming, and lowercasing."""
    assert normalize_email("  User.Name@Example.COM  ") == "user.name@example.com"
    # Plus-addressing must NOT be stripped
    assert normalize_email("Alice+newsletter@test.org") == "alice+newsletter@test.org"
    assert normalize_email("  BOB+tag1+tag2@DOMAIN.CO.UK  ") == "bob+tag1+tag2@domain.co.uk"
    # Empty and None values
    assert normalize_email("") is None
    assert normalize_email("   ") is None
    assert normalize_email(None) is None


def test_normalize_phone():
    """Test phone normalization extracting digits only and preserving raw string."""
    assert normalize_phone("+1 (202) 555-0103") == "12025550103"
    assert normalize_phone("+34 612 847 593") == "34612847593"
    assert normalize_phone("+81 90-6278-6936") == "819062786936"
    assert normalize_phone("+46 70 144 08 06") == "46701440806"
    # Empty / no-digit values
    assert normalize_phone("") is None
    assert normalize_phone("   ") is None
    assert normalize_phone("+ - ()") is None
    assert normalize_phone(None) is None


def test_normalize_timestamp():
    """Test timestamp normalization with and without timezone."""
    # UTC with Z
    dt, tz_missing = normalize_timestamp("2026-08-18T09:14:00Z")
    assert not tz_missing
    assert dt == datetime(2026, 8, 18, 9, 14, 0, tzinfo=timezone.utc)

    # Offset timestamp
    dt, tz_missing = normalize_timestamp("2026-08-18T14:44:00+05:30")
    assert not tz_missing
    assert dt.astimezone(timezone.utc) == datetime(2026, 8, 18, 9, 14, 0, tzinfo=timezone.utc)

    # Timestamp without timezone
    dt_naive, tz_missing = normalize_timestamp("2026-08-18T09:14:00")
    assert tz_missing
    assert dt_naive.tzinfo is None
    assert dt_naive == datetime(2026, 8, 18, 9, 14, 0)

    # Invalid timestamp format raises TimestampFormatError
    with pytest.raises(TimestampFormatError):
        normalize_timestamp("18-08-2026 09:14")


def test_round_trip_raw_values():
    """Test that for 20 sample rows across datasets, raw values in model equal CSV values byte-for-byte."""
    import csv

    dataset = load_dataset(os.path.join(_repo_root, "dataset"))

    # Check 5 rows from deletion_requests.csv
    with open(os.path.join(_repo_root, "dataset", "deletion_requests.csv"), "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        raw_rows = [next(reader) for _ in range(5)]
    for i in range(5):
        m = dataset.deletion_requests[i]
        r = raw_rows[i]
        assert m.case_id == r[0]
        assert m.email_raw == r[1]
        assert m.requested_at_raw == r[2]
        assert m.reported_status == r[3]
        assert m.reported_at_raw == r[4]
        assert m.audit_at_raw == r[5]
        assert m.request_text == r[6]

    # Check 5 rows from user_identities.csv
    with open(os.path.join(_repo_root, "dataset", "user_identities.csv"), "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        raw_rows = [next(reader) for _ in range(5)]
    for i in range(5):
        m = dataset.user_identities[i]
        r = raw_rows[i]
        assert m.user_id == r[0]
        assert m.name == r[1]
        assert m.email_raw == r[2]
        assert m.phone_raw == r[3]
        assert m.email_hash == r[4]
        assert m.updated_at_raw == r[5]

    # Check 5 rows from user_audit_log.csv
    with open(os.path.join(_repo_root, "dataset", "user_audit_log.csv"), "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        raw_rows = [next(reader) for _ in range(5)]
    for i in range(5):
        m = dataset.user_audit_log[i]
        r = raw_rows[i]
        assert m.audit_id == r[0]
        assert m.user_id == r[1]
        assert m.changed_at_raw == r[2]
        assert m.field_name == r[3]
        assert m.old_value_raw == r[4]
        assert m.new_value_raw == r[5]

    # Check 5 rows from system_activity.csv
    with open(os.path.join(_repo_root, "dataset", "system_activity.csv"), "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        raw_rows = [next(reader) for _ in range(5)]
    for i in range(5):
        m = dataset.system_activity[i]
        r = raw_rows[i]
        assert m.activity_id == r[0]
        assert m.event_time_raw == r[1]
        assert m.event_type == r[2]
        assert m.source_system == r[3]
        assert m.target_system == r[4]
        assert m.resource_id == r[5]
        assert m.reported_result == r[6]
        assert m.details == r[7]


def test_source_tracing():
    """Verify that SourceRef points to the exact file line containing that row's primary key."""
    dataset = load_dataset(os.path.join(_repo_root, "dataset"))

    # Test user_identities.csv
    with open(os.path.join(_repo_root, "dataset", "user_identities.csv"), "r", encoding="utf-8") as f:
        lines = f.readlines()
    for item in dataset.user_identities[:20]:
        line_content = lines[item.source.row_number - 1]
        assert item.user_id in line_content

    # Test deletion_requests.csv
    with open(os.path.join(_repo_root, "dataset", "deletion_requests.csv"), "r", encoding="utf-8") as f:
        lines = f.readlines()
    for item in dataset.deletion_requests[:20]:
        line_content = lines[item.source.row_number - 1]
        assert item.case_id in line_content


def test_malformed_and_empty_rows():
    """Verify that temporary CSVs with malformed or empty rows raise typed errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create minimal required CSVs with one bad row in deletion_requests.csv
        for name in [
            "user_identities.csv",
            "user_audit_log.csv",
            "system_activity.csv",
            "deletion_rules.csv",
            "evidence_files.csv",
            "sample_deletion_requests.csv",
            "sample_output.csv",
        ]:
            src = os.path.join(_repo_root, "dataset", name)
            with open(src, "r") as sf, open(os.path.join(tmpdir, name), "w") as df:
                # copy header and 1 row
                df.write(sf.readline())
                df.write(sf.readline())

        # Test malformed row (too few columns)
        bad_csv = os.path.join(tmpdir, "deletion_requests.csv")
        with open(bad_csv, "w") as f:
            f.write("case_id,email,requested_at,reported_status,reported_at,audit_at,request_text\n")
            f.write("case_1,user@test.com\n")  # Only 2 columns instead of 7

        with pytest.raises(MalformedRowError) as exc_info:
            load_dataset(tmpdir)
        assert exc_info.value.line == 2
        assert "deletion_requests.csv" in exc_info.value.file

        # Test empty row
        with open(bad_csv, "w") as f:
            f.write("case_id,email,requested_at,reported_status,reported_at,audit_at,request_text\n")
            f.write("\n")

        with pytest.raises(EmptyRowError) as exc_info:
            load_dataset(tmpdir)
        assert exc_info.value.line == 2
