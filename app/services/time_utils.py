from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

APP_TIMEZONE = ZoneInfo("Europe/Rome")
RECEIPT_DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"


def parse_db_datetime(value: str | None) -> datetime | None:
    """Parse SQLite datetime strings and treat naive values as UTC.

    SQLite datetime('now') stores UTC without timezone information.
    """
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def to_rome(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    parsed = parse_db_datetime(value) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(APP_TIMEZONE)


def format_rome_datetime(value: str | datetime | None) -> str:
    local_dt = to_rome(value)
    if local_dt is None:
        return ""
    return local_dt.strftime(RECEIPT_DATETIME_FORMAT)
