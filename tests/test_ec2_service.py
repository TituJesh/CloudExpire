
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
