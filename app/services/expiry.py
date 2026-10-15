
from datetime import datetime, timedelta, timezone


def calculate_expiry(ttl_hours: int) -> datetime:
    """Return the UTC expiry time for a resource."""

    if isinstance(ttl_hours, bool) or not isinstance(ttl_hours, int):
        raise ValueError("TTL must be an integer.")

    if not 1 <= ttl_hours <= 24:
        raise ValueError("TTL must be between 1 and 24 hours.")

    return datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
