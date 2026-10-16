
from datetime import datetime, timezone
from uuid import uuid4

from app.repositories.resource_repository import resource_repository
from app.schemas import ResourceCreate, ResourceRecord
from app.services.expiry import calculate_expiry


def create_resource_record(request: ResourceCreate) -> ResourceRecord:
    created_at = datetime.now(timezone.utc)
    expires_at = calculate_expiry(request.ttl_hours)

    resource = ResourceRecord(
        resource_id=f"ce-{uuid4()}",
        name=request.name,
        resource_type=request.resource_type,
        ttl_hours=request.ttl_hours,
        instance_type=request.instance_type,
        created_at=created_at,
        expires_at=expires_at,
        status="REQUESTED",
        aws_resource_id=None,
    )

    return resource_repository.create(resource)
