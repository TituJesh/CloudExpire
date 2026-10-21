
import os
from datetime import datetime, timezone

import boto3

from app.repositories.resource_repository import resource_repository


def find_expired_resources():
    """Find expired resources awaiting termination or cleanup confirmation."""
    now = datetime.now(timezone.utc)

    return [
        resource
        for resource in resource_repository.list_all()
        if resource.status in ("ACTIVE", "CLEANUP_PENDING")
        and resource.expires_at <= now
        and resource.aws_resource_id is not None
    ]


def cleanup_expired_resources():
    """Safely process expired CloudExpire EC2 resources."""
    # Read DynamoDB even when termination is disabled.
    expired_resources = find_expired_resources()

    # Safe dry-run mode: inspect records, but never contact EC2
    # or terminate instances.
    if os.getenv(
        "CLOUDEXPIRE_ALLOW_EC2_TERMINATION", "false"
    ).lower() != "true":
        return {"terminated": 0, "skipped": True}

    region = os.getenv("AWS_REGION", "ap-south-1")
    ec2 = boto3.client("ec2", region_name=region)

    terminated = 0

    for resource in expired_resources:
        response = ec2.describe_instances(
            InstanceIds=[resource.aws_resource_id]
        )

        instances = [
            instance
            for reservation in response.get("Reservations", [])
            for instance in reservation.get("Instances", [])
        ]

        # Do not assume a missing response proves cleanup succeeded.
        if not instances:
            continue

        instance = instances[0]
        tags = {
            tag["Key"]: tag["Value"]
            for tag in instance.get("Tags", [])
        }

        # Require all three ownership tags before changing or terminating
        # an AWS resource.
        if (
            tags.get("Project") != "CloudExpire"
            or tags.get("ManagedBy") != "CloudExpire"
            or tags.get("ResourceId") != resource.resource_id
        ):
            continue

        state = instance.get("State", {}).get("Name", "unknown")

        if state not in (
            "pending",
            "running",
            "stopping",
            "stopped",
            "shutting-down",
            "terminated",
        ):
            continue

        if state == "terminated":
            updated_resource = resource.model_copy(
                update={"status": "CLEANED"}
            )
            resource_repository.update(updated_resource)
            continue

        if state in ("shutting-down", "stopping"):
            if resource.status != "CLEANUP_PENDING":
                updated_resource = resource.model_copy(
                    update={"status": "CLEANUP_PENDING"}
                )
                resource_repository.update(updated_resource)
            continue

        # Request termination for eligible instances. If AWS raises an
        # error, let it surface rather than marking cleanup as successful.
        ec2.terminate_instances(
            InstanceIds=[resource.aws_resource_id]
        )

        updated_resource = resource.model_copy(
            update={"status": "CLEANUP_PENDING"}
        )
        resource_repository.update(updated_resource)
        terminated += 1

    return {"terminated": terminated, "skipped": False}
