
from datetime import datetime, timedelta, timezone

from app.repositories.resource_repository import InMemoryResourceRepository
from app.schemas import ResourceRecord
from app.services import cleanup_service


def test_finds_expired_active_resources(monkeypatch):
    repository = InMemoryResourceRepository()
    monkeypatch.setattr(
        cleanup_service,
        "resource_repository",
        repository,
    )

    now = datetime.now(timezone.utc)

    expired = ResourceRecord(
        resource_id="ce-expired",
        name="expired-test",
        resource_type="ec2",
        ttl_hours=1,
        instance_type="t3.micro",
        created_at=now - timedelta(hours=2),
        expires_at=now - timedelta(hours=1),
        status="ACTIVE",
        aws_resource_id="i-0123456789abcdef0",
    )

    not_expired = expired.model_copy(
        update={
            "resource_id": "ce-not-expired",
            "name": "not-expired-test",
            "expires_at": now + timedelta(hours=1),
            "aws_resource_id": "i-0123456789abcdef1",
        }
    )

    repository.create(expired)
    repository.create(not_expired)

    result = cleanup_service.find_expired_resources()

    assert len(result) == 1
    assert result[0].resource_id == "ce-expired"

def test_reconciles_stale_requested_resources(monkeypatch):
    repository = InMemoryResourceRepository()
    monkeypatch.setattr(
        cleanup_service,
        "resource_repository",
        repository,
    )

    now = datetime.now(timezone.utc)

    stale = ResourceRecord(
        resource_id="ce-stale",
        name="stale-test",
        resource_type="ec2",
        ttl_hours=1,
        instance_type="t3.micro",
        created_at=now - timedelta(hours=3),
        expires_at=now - timedelta(hours=2),
        status="REQUESTED",
        aws_resource_id=None,
    )

    fresh = stale.model_copy(
        update={
            "resource_id": "ce-fresh",
            "name": "fresh-test",
            "created_at": now - timedelta(minutes=5),
            "expires_at": now + timedelta(hours=1),
        }
    )

    repository.create(stale)
    repository.create(fresh)

    count = cleanup_service.reconcile_stale_requested_resources(
        now=now,
        grace_minutes=15,
    )

    assert count == 1
    assert repository.get("ce-stale").status == "FAILED"
    assert repository.get("ce-stale").aws_resource_id is None
    assert repository.get("ce-fresh").status == "REQUESTED"
