"""code/src/normalize.py

Normalizers for email, phone, and timestamp fields.
Preserves raw values and explicitly flags missing timezones.
"""

from datetime import datetime, timezone
import re
from typing import Optional, Tuple


class TimestampFormatError(ValueError):
    """Raised when an unparseable or unrecognized timestamp format is encountered."""
    def __init__(self, raw: str, file: str = "", line: int = 0):
        self.raw = raw
        self.file = file
        self.line = line
        loc = f" at {file}:{line}" if file or line else ""
        super().__init__(f"Unknown or invalid timestamp format '{raw}'{loc}")


def normalize_email(raw: Optional[str]) -> Optional[str]:
    """
    Normalizes an email address: trims whitespace and lowercases.
    Returns None if input is empty or None.
    NOTE: Does NOT strip plus-addressing.
    """
    if raw is None:
        return None
    trimmed = raw.strip()
    if not trimmed:
        return None
    return trimmed.lower()


def normalize_phone(raw: Optional[str]) -> Optional[str]:
    """
    Normalizes a phone number: extracts only decimal digits.
    Returns None if input is empty or contains no digits.
    """
    if raw is None:
        return None
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    return digits


def normalize_timestamp(
    raw: Optional[str],
    file: str = "",
    line: int = 0,
) -> Tuple[Optional[datetime], bool]:
    """
    Parses a timestamp string.
    Returns a tuple: (parsed_datetime, tz_missing).
    
    If the timestamp has a timezone (e.g. UTC 'Z' or offset), converts/normalizes
    to timezone-aware UTC datetime with tz_missing=False.
    If the timestamp has NO timezone, parses into a naive datetime (tzinfo=None)
    with tz_missing=True. Never silently assumes a timezone.
    
    Raises TimestampFormatError if the string does not match known formats.
    """
    if raw is None:
        return (None, False)
    val = raw.strip()
    if not val:
        return (None, False)

    # 1. ISO-8601 with Z (e.g., 2026-08-18T09:14:00Z)
    if val.endswith("Z") or val.endswith("z"):
        try:
            # Replace Z with +00:00 for robust iso parsing across python versions
            iso_str = val[:-1] + "+00:00"
            dt = datetime.fromisoformat(iso_str)
            dt_utc = dt.astimezone(timezone.utc)
            return (dt_utc, False)
        except ValueError as exc:
            raise TimestampFormatError(raw, file, line) from exc

    # 2. ISO-8601 with numeric offset (e.g., 2026-08-18T09:14:00+00:00 or -05:00)
    if re.search(r"[+-]\d{2}:?\d{2}$", val):
        try:
            dt = datetime.fromisoformat(val)
            dt_utc = dt.astimezone(timezone.utc)
            return (dt_utc, False)
        except ValueError as exc:
            raise TimestampFormatError(raw, file, line) from exc

    # 3. Naive ISO timestamp (no timezone: e.g. 2026-08-18T09:14:00 or 2026-08-18 09:14:00)
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            return (dt, True)
        else:
            return (dt.astimezone(timezone.utc), False)
    except ValueError:
        pass

    # Unrecognized format
    raise TimestampFormatError(raw, file, line)
