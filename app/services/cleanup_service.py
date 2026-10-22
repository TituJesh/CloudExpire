
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError

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
    expired_resources = find_expired_resources()

    # Read-only mode: never contact EC2 or terminate instances.
    if os.getenv(
        "CLOUDEXPIRE_ALLOW_EC2_TERMINATION", "false"
    ).lower() != "true":
        return {
            "terminated": 0,
            "skipped": True,
            "eligible": len(expired_resources),
            "errors": 0,
        }

    region = os.getenv("AWS_REGION", "ap-south-1")
    ec2 = boto3.client("ec2", region_name=region)

    terminated = 0
    errors = 0

    for resource in expired_resources:
        try:
            response = ec2.describe_instances(
                InstanceIds=[resource.aws_resource_id]
            )
        except (ClientError, BotoCoreError):
            errors += 1
            continue

        instances = [
            instance
            for reservation in response.get("Reservations", [])
            for instance in reservation.get("Instances", [])
        ]

        # A missing response is not proof that cleanup succeeded.
        if not instances:
            continue

        instance = instances[0]
        tags = {
            tag["Key"]: tag["Value"]
            for tag in instance.get("Tags", [])
        }

        if (
            tags.get("Project") != "CloudExpire"
            or tags.get("ManagedBy") != "CloudExpire"
            or tags.get("ResourceId") != resource.resource_id
        ):
            continue

        state = instance.get("State", {}).get("Name", "unknown")

        if state == "terminated":
            resource_repository.update(
                resource.model_copy(update={"status": "CLEANED"})
            )
            continue

        if state in ("shutting-down", "stopping"):
            if resource.status != "CLEANUP_PENDING":
                resource_repository.update(
                    resource.model_copy(
                        update={"status": "CLEANUP_PENDING"}
                    )
                )
            continue

        if state not in ("pending", "running", "stopped"):
            continue

        try:
            ec2.terminate_instances(
                InstanceIds=[resource.aws_resource_id]
            )
        except (ClientError, BotoCoreError):
            errors += 1
            continue

        resource_repository.update(
            resource.model_copy(update={"status": "CLEANUP_PENDING"})
        )
        terminated += 1

    return {
        "terminated": terminated,
        "skipped": False,
        "errors": errors,
    }
