
from datetime import datetime, timedelta, timezone

import pytest

from app.services.expiry import calculate_expiry


def test_expiry_is_six_hours_in_future():
    before = datetime.now(timezone.utc)

    expiry = calculate_expiry(6)

    after = datetime.now(timezone.utc)

    assert before + timedelta(hours=6) <= expiry
    assert expiry <= after + timedelta(hours=6)


def test_expiry_uses_utc():
    expiry = calculate_expiry(1)

    assert expiry.tzinfo is not None
    assert expiry.utcoffset() == timedelta(0)


@pytest.mark.parametrize("ttl", [0, -1, 25, 100])
def test_invalid_ttl_is_rejected(ttl):
    with pytest.raises(ValueError):
        calculate_expiry(ttl)


def test_non_integer_ttl_is_rejected():
    with pytest.raises(ValueError):
        calculate_expiry(1.5)
