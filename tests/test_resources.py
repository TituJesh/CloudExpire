
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.resource_repository import resource_repository

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_resources():
    resource_repository.clear()
    yield
    resource_repository.clear()


def test_create_resource_record():
    response = client.post(
        "/resources",
        json={
            "name": "test-server",
            "resource_type": "ec2",
            "ttl_hours": 6,
            "instance_type": "t3.micro",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "test-server"
    assert data["status"] == "REQUESTED"
    assert data["aws_resource_id"] is None
    assert data["resource_id"].startswith("ce-")
    assert data["expires_at"]


def test_list_and_get_resources():
    create_response = client.post(
        "/resources",
        json={
            "name": "test-server",
            "resource_type": "ec2",
            "ttl_hours": 6,
            "instance_type": "t3.micro",
        },
    )

    resource_id = create_response.json()["resource_id"]

    list_response = client.get("/resources")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = client.get(f"/resources/{resource_id}")
    assert get_response.status_code == 200
    assert get_response.json()["resource_id"] == resource_id


def test_get_missing_resource():
    response = client.get("/resources/does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"] == "Resource not found"


def test_invalid_ttl_is_rejected():
    response = client.post(
        "/resources",
        json={
            "name": "test-server",
            "resource_type": "ec2",
            "ttl_hours": 25,
            "instance_type": "t3.micro",
        },
    )

    assert response.status_code == 422
