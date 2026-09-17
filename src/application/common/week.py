from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


def week_bounds(value: datetime, timezone: ZoneInfo) -> tuple[datetime, datetime]:
    """Return the half-open UTC interval for the local Monday-based week."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    local = value.astimezone(timezone)
    start_local = (local - timedelta(days=local.weekday())).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    return start_local.astimezone(UTC), (start_local + timedelta(days=7)).astimezone(UTC)
