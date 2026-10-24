
import logging
import os
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.repositories.resource_repository import resource_repository

logger = logging.getLogger(__name__)


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


def reconcile_stale_requested_resources(
    now: datetime | None = None,
    grace_minutes: int = 15,
) -> int:
    """Mark expired requests without an EC2 ID as FAILED."""
    if grace_minutes < 0:
        raise ValueError("grace_minutes must be non-negative")

    if now is None:
        now = datetime.now(timezone.utc)

    cutoff = now - timedelta(minutes=grace_minutes)
    failed_count = 0

    for resource in resource_repository.list_all():
        if (
            resource.status == "REQUESTED"
            and resource.aws_resource_id is None
            and resource.expires_at <= cutoff
        ):
            failed_resource = resource.model_copy(
                update={"status": "FAILED"}
            )
            resource_repository.update(failed_resource)

            failed_count += 1
            logger.warning(
                "Marked stale request %s as FAILED; "
                "no EC2 instance ID was recorded",
                resource.resource_id,
            )

    return failed_count


def cleanup_expired_resources():
    """Safely process expired CloudExpire EC2 resources."""
    expired_resources = find_expired_resources()

    result = {
        "eligible": len(expired_resources),
        "terminated": 0,
        "reconciled": 0,
        "already_terminating": 0,
        "skipped_missing": 0,
        "skipped_unowned": 0,
        "skipped_state": 0,
        "stale_requests_failed": 0,
        "errors": 0,
        "skipped": False,
    }

    # Read-only mode: never contact EC2 or terminate instances.
    if os.getenv(
        "CLOUDEXPIRE_ALLOW_EC2_TERMINATION", "false"
    ).lower() != "true":
        result["skipped"] = True
        logger.warning(
            "Cleanup is in read-only mode; eligible=%s",
            result["eligible"],
        )
        return result

    result["stale_requests_failed"] = (
        reconcile_stale_requested_resources()
    )

    region = os.getenv("AWS_REGION", "ap-south-1")
    ec2 = boto3.client("ec2", region_name=region)

    for resource in expired_resources:
        resource_id = resource.resource_id
        instance_id = resource.aws_resource_id

        try:
            response = ec2.describe_instances(
                InstanceIds=[instance_id]
            )
        except (ClientError, BotoCoreError):
            result["errors"] += 1
            logger.exception(
                "Failed to describe EC2 instance %s for resource %s",
                instance_id,
                resource_id,
            )
            continue

        instances = [
            instance
            for reservation in response.get("Reservations", [])
            for instance in reservation.get("Instances", [])
        ]

        if not instances:
            result["skipped_missing"] += 1
            logger.warning(
                "No EC2 instance returned for resource %s, instance %s",
                resource_id,
                instance_id,
            )
            continue

        instance = instances[0]
        tags = {
            tag["Key"]: tag["Value"]
            for tag in instance.get("Tags", [])
        }

        # Never terminate an instance unless all ownership tags match.
        if (
            tags.get("Project") != "CloudExpire"
            or tags.get("ManagedBy") != "CloudExpire"
            or tags.get("ResourceId") != resource_id
        ):
            result["skipped_unowned"] += 1
            logger.warning(
                "Ownership check failed; refusing to terminate instance %s",
                instance_id,
            )
            continue

        state = instance.get("State", {}).get("Name", "unknown")

        if state == "terminated":
            resource_repository.update(
                resource.model_copy(update={"status": "CLEANED"})
            )
            result["reconciled"] += 1
            logger.info(
                "Reconciled resource %s: instance %s is already terminated",
                resource_id,
                instance_id,
            )
            continue

        if state in ("shutting-down", "stopping"):
            if resource.status != "CLEANUP_PENDING":
                resource_repository.update(
                    resource.model_copy(
                        update={"status": "CLEANUP_PENDING"}
                    )
                )
            result["already_terminating"] += 1
            logger.info(
                "Resource %s is awaiting cleanup; EC2 state=%s",
                resource_id,
                state,
            )
            continue

        if state not in ("pending", "running", "stopped"):
            result["skipped_state"] += 1
            logger.warning(
                "Skipping resource %s: unsupported EC2 state=%s",
                resource_id,
                state,
            )
            continue

        try:
            ec2.terminate_instances(InstanceIds=[instance_id])
        except (ClientError, BotoCoreError):
            result["errors"] += 1
            logger.exception(
                "Failed to terminate EC2 instance %s for resource %s",
                instance_id,
                resource_id,
            )
            continue

        resource_repository.update(
            resource.model_copy(update={"status": "CLEANUP_PENDING"})
        )
        result["terminated"] += 1
        logger.info(
            "Termination requested for resource %s, instance %s",
            resource_id,
            instance_id,
        )

    logger.info("Cleanup summary: %s", result)
    return result
