
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories import resource_repository as repository_module
from app.repositories.resource_repository import InMemoryResourceRepository


@pytest.fixture()
def client(monkeypatch):
    test_repository = InMemoryResourceRepository()

    monkeypatch.setattr(
        repository_module,
        "resource_repository",
        test_repository,
    )
    monkeypatch.setattr(
        "app.services.resource_service.resource_repository",
        test_repository,
    )
    monkeypatch.setattr(
        "app.main.resource_repository",
        test_repository,
    )

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_create_resource_record(client):
    response = client.post(
        "/resources",
        json={
            "name": "test-instance",
            "resource_type": "ec2",
            "ttl_hours": 2,
            "instance_type": "t3.micro",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test-instance"
    assert data["status"] == "REQUESTED"
    assert data["aws_resource_id"] is None


def test_list_and_get_resources(client):
    created = client.post(
        "/resources",
        json={
            "name": "test-instance",
            "resource_type": "ec2",
            "ttl_hours": 2,
            "instance_type": "t3.micro",
        },
    )
    resource_id = created.json()["resource_id"]

    listed = client.get("/resources")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = client.get(f"/resources/{resource_id}")
    assert fetched.status_code == 200
    assert fetched.json()["resource_id"] == resource_id


def test_get_missing_resource(client):
    response = client.get("/resources/nonexistent")
    assert response.status_code == 404


def test_invalid_ttl_is_rejected(client):
    response = client.post(
        "/resources",
        json={
            "name": "test-instance",
            "resource_type": "ec2",
            "ttl_hours": 25,
            "instance_type": "t3.micro",
        },
    )

    assert response.status_code == 422


def test_provisioning_disabled_keeps_resource_requested(client, monkeypatch):
    monkeypatch.setenv("CLOUDEXPIRE_PROVISION_EC2", "false")
    monkeypatch.setenv("CLOUDEXPIRE_STORAGE", "memory")

    response = client.post(
        "/resources",
        json={
            "name": "safe-test",
            "resource_type": "ec2",
            "ttl_hours": 1,
            "instance_type": "t3.micro",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "REQUESTED"
    assert data["aws_resource_id"] is None


def test_mocked_ec2_provisioning_activates_resource(client, monkeypatch):
    monkeypatch.setenv("CLOUDEXPIRE_PROVISION_EC2", "true")

    def fake_launch_ec2_instance(instance_type, resource_id, expires_at):
        assert instance_type == "t3.micro"
        assert resource_id.startswith("ce-")
        assert expires_at
        return "i-0123456789abcdef0"

    monkeypatch.setattr(
        "app.services.resource_service.launch_ec2_instance",
        fake_launch_ec2_instance,
    )

    response = client.post(
        "/resources",
        json={
            "name": "mock-ec2-test",
            "resource_type": "ec2",
            "ttl_hours": 1,
            "instance_type": "t3.micro",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "ACTIVE"
    assert data["aws_resource_id"] == "i-0123456789abcdef0"


def test_failed_ec2_provisioning_marks_resource_failed(client, monkeypatch):
    monkeypatch.setenv("CLOUDEXPIRE_PROVISION_EC2", "true")

    def fake_launch_ec2_instance(instance_type, resource_id, expires_at):
        raise RuntimeError("Simulated EC2 launch failure")

    monkeypatch.setattr(
        "app.services.resource_service.launch_ec2_instance",
        fake_launch_ec2_instance,
    )

    response = client.post(
        "/resources",
        json={
            "name": "failed-launch-test",
            "resource_type": "ec2",
            "ttl_hours": 1,
            "instance_type": "t3.micro",
        },
    )

    assert response.status_code == 500
    resources_response = client.get("/resources")
    assert resources_response.status_code == 200

    failed_records = [
        resource
        for resource in resources_response.json()
        if resource["name"] == "failed-launch-test"
    ]
    assert len(failed_records) == 1
    assert failed_records[0]["status"] == "FAILED"



def test_resource_persistence_retries_after_initial_update_failure(
    client, monkeypatch
):
    monkeypatch.setenv("CLOUDEXPIRE_PROVISION_EC2", "true")

    def fake_launch_ec2_instance(instance_type, resource_id, expires_at):
        return "i-0123456789abcdef0"

    monkeypatch.setattr(
        "app.services.resource_service.launch_ec2_instance",
        fake_launch_ec2_instance,
    )

    original_update = repository_module.resource_repository.update
    calls = {"count": 0}

    def fail_once_then_update(resource):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("Simulated transient persistence failure")
        return original_update(resource)

    monkeypatch.setattr(
        "app.services.resource_service.resource_repository.update",
        fail_once_then_update,
    )

    response = client.post(
        "/resources",
        json={
            "name": "persistence-retry-test",
            "resource_type": "ec2",
            "ttl_hours": 1,
            "instance_type": "t3.micro",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "ACTIVE"
    assert data["aws_resource_id"] == "i-0123456789abcdef0"
    assert calls["count"] == 2

