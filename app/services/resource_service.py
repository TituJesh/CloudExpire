
import os
from datetime import datetime, timezone
from uuid import uuid4

from app.repositories.resource_repository import resource_repository
from app.schemas import ResourceCreate, ResourceRecord
from app.services.expiry import calculate_expiry
from app.services.ec2_service import launch_ec2_instance


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

    # Save the record before attempting any AWS provisioning.
    resource_repository.create(resource)

    provisioning_enabled = (
        os.getenv("CLOUDEXPIRE_PROVISION_EC2", "false").lower() == "true"
    )

    if not provisioning_enabled:
        return resource

    try:
        instance_id = launch_ec2_instance(
            instance_type=resource.instance_type,
            resource_id=resource.resource_id,
            expires_at=resource.expires_at.isoformat(),
        )

        updated_resource = resource.model_copy(
            update={
                "aws_resource_id": instance_id,
                "status": "ACTIVE",
            }
        )
        return resource_repository.update(updated_resource)

    except Exception:
        failed_resource = resource.model_copy(update={"status": "FAILED"})
        resource_repository.update(failed_resource)
        raise
