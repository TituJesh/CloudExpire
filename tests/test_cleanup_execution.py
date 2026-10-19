
from datetime import datetime, timedelta, timezone

from app.repositories.resource_repository import InMemoryResourceRepository
from app.schemas import ResourceRecord
from app.services import cleanup_service


def make_expired_resource():
    now = datetime.now(timezone.utc)

    return ResourceRecord(
        resource_id="ce-cleanup-test",
        name="cleanup-test",
        resource_type="ec2",
        ttl_hours=1,
        instance_type="t3.micro",
        created_at=now - timedelta(hours=2),
        expires_at=now - timedelta(hours=1),
        status="ACTIVE",
        aws_resource_id="i-0123456789abcdef0",
    )


def test_cleanup_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("CLOUDEXPIRE_ALLOW_EC2_TERMINATION", raising=False)

    result = cleanup_service.cleanup_expired_resources()

    assert result == {"terminated": 0, "skipped": True}


def test_cleanup_terminates_matching_expired_instance(monkeypatch):
    repository = InMemoryResourceRepository()
    monkeypatch.setattr(cleanup_service, "resource_repository", repository)
    monkeypatch.setenv("CLOUDEXPIRE_ALLOW_EC2_TERMINATION", "true")

    resource = make_expired_resource()
    repository.create(resource)

    class FakeEC2:
        def __init__(self):
            self.terminated_ids = []

        def describe_instances(self, InstanceIds):
            return {
                "Reservations": [{
                    "Instances": [{
                        "InstanceId": resource.aws_resource_id,
                        "Tags": [
                            {"Key": "Project", "Value": "CloudExpire"},
                            {"Key": "ManagedBy", "Value": "CloudExpire"},
                            {"Key": "ResourceId", "Value": resource.resource_id},
                        ],
                    }]
                }]
            }

        def terminate_instances(self, InstanceIds):
            self.terminated_ids.extend(InstanceIds)
            return {"TerminatingInstances": []}

    fake_ec2 = FakeEC2()
    monkeypatch.setattr(
        cleanup_service.boto3,
        "client",
        lambda *args, **kwargs: fake_ec2,
    )

    result = cleanup_service.cleanup_expired_resources()

    assert result == {"terminated": 1, "skipped": False}
    assert fake_ec2.terminated_ids == [resource.aws_resource_id]
    assert repository.get(resource.resource_id).status == "CLEANUP_PENDING"


def test_cleanup_skips_instance_with_mismatched_ownership_tags(monkeypatch):
    repository = InMemoryResourceRepository()
    monkeypatch.setattr(cleanup_service, "resource_repository", repository)
    monkeypatch.setenv("CLOUDEXPIRE_ALLOW_EC2_TERMINATION", "true")

    resource = make_expired_resource()
    repository.create(resource)

    class FakeEC2:
        def describe_instances(self, InstanceIds):
            return {
                "Reservations": [{
                    "Instances": [{
                        "InstanceId": resource.aws_resource_id,
                        "Tags": [
                            {"Key": "Project", "Value": "CloudExpire"},
                            {"Key": "ManagedBy", "Value": "CloudExpire"},
                            {"Key": "ResourceId", "Value": "some-other-resource"},
                        ],
                    }]
                }]
            }

        def terminate_instances(self, InstanceIds):
            raise AssertionError("Mismatched instance must not be terminated")

    fake_ec2 = FakeEC2()
    monkeypatch.setattr(
        cleanup_service.boto3,
        "client",
        lambda *args, **kwargs: fake_ec2,
    )

    result = cleanup_service.cleanup_expired_resources()

    assert result == {"terminated": 0, "skipped": False}
    assert repository.get(resource.resource_id).status == "ACTIVE"
