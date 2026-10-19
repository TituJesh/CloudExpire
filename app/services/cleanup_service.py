
import os
from datetime import datetime, timezone

import boto3

from app.repositories.resource_repository import resource_repository


def find_expired_resources():
    """Return active resources whose expiry time has passed."""
    now = datetime.now(timezone.utc)

    return [
        resource
        for resource in resource_repository.list_all()
        if resource.status == "ACTIVE"
        and resource.expires_at <= now
        and resource.aws_resource_id is not None
    ]


def cleanup_expired_resources():
    """Terminate expired CloudExpire instances only when explicitly enabled."""
    if os.getenv("CLOUDEXPIRE_ALLOW_EC2_TERMINATION", "false").lower() != "true":
        return {"terminated": 0, "skipped": True}

    region = os.getenv("AWS_REGION", "ap-south-1")
    ec2 = boto3.client("ec2", region_name=region)

    terminated = 0

    for resource in find_expired_resources():
        response = ec2.describe_instances(
            InstanceIds=[resource.aws_resource_id]
        )

        instances = [
            instance
            for reservation in response.get("Reservations", [])
            for instance in reservation.get("Instances", [])
        ]

        if not instances:
            continue

        instance = instances[0]
        tags = {
            tag["Key"]: tag["Value"]
            for tag in instance.get("Tags", [])
        }

        # Never terminate an instance unless its ownership matches the record.
        if (
            tags.get("Project") != "CloudExpire"
            or tags.get("ManagedBy") != "CloudExpire"
            or tags.get("ResourceId") != resource.resource_id
        ):
            continue

        ec2.terminate_instances(
            InstanceIds=[resource.aws_resource_id]
        )

        updated_resource = resource.model_copy(
            update={"status": "CLEANUP_PENDING"}
        )
        resource_repository.update(updated_resource)
        terminated += 1

    return {"terminated": terminated, "skipped": False}
