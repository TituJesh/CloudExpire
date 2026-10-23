
import pytest

from app.services.ec2_service import launch_ec2_instance


def test_ec2_launch_disabled_by_default(monkeypatch):
    monkeypatch.delenv("CLOUDEXPIRE_ALLOW_EC2_LAUNCH", raising=False)

    with pytest.raises(RuntimeError, match="EC2 launch is disabled"):
        launch_ec2_instance(
            instance_type="t3.micro",
            resource_id="ce-test-123",
            expires_at="2026-10-20T12:00:00+00:00",
        )



def test_ec2_launch_uses_resource_id_as_client_token(monkeypatch):
    from app.services import ec2_service

    monkeypatch.setenv("CLOUDEXPIRE_ALLOW_EC2_LAUNCH", "true")
    monkeypatch.setenv("CLOUDEXPIRE_AMI_ID", "ami-test123")
    monkeypatch.setenv("CLOUDEXPIRE_SUBNET_ID", "subnet-test123")
    monkeypatch.setenv("CLOUDEXPIRE_SECURITY_GROUP_ID", "sg-test123")
    monkeypatch.setenv("AWS_REGION", "ap-south-1")

    captured = {}

    class FakeEC2:
        def run_instances(self, **kwargs):
            captured.update(kwargs)
            return {"Instances": [{"InstanceId": "i-0123456789abcdef0"}]}

    monkeypatch.setattr(
        ec2_service.boto3,
        "client",
        lambda *args, **kwargs: FakeEC2(),
    )

    result = ec2_service.launch_ec2_instance(
        instance_type="t3.micro",
        resource_id="ce-test-123",
        expires_at="2026-10-24T12:00:00+00:00",
    )

    assert result == "i-0123456789abcdef0"
    assert captured["ClientToken"] == "ce-test-123"
    assert captured["MinCount"] == 1
    assert captured["MaxCount"] == 1
