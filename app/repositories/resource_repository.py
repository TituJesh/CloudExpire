
import os

import boto3

from app.schemas import ResourceRecord


class InMemoryResourceRepository:
    """Temporary storage for local development and tests."""

    def __init__(self):
        self._resources: dict[str, ResourceRecord] = {}

    def create(self, resource: ResourceRecord) -> ResourceRecord:
        if resource.resource_id in self._resources:
            raise ValueError("Resource ID already exists.")

        self._resources[resource.resource_id] = resource
        return resource

    def get(self, resource_id: str) -> ResourceRecord | None:
        return self._resources.get(resource_id)

    def list_all(self) -> list[ResourceRecord]:
        return list(self._resources.values())

    def clear(self) -> None:
        self._resources.clear()


class DynamoDBResourceRepository:
    """Persistent resource storage backed by Amazon DynamoDB."""

    def __init__(self, table_name: str, region: str):
        dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table = dynamodb.Table(table_name)

    def create(self, resource: ResourceRecord) -> ResourceRecord:
        item = resource.model_dump(mode="json")

        self.table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(resource_id)",
        )

        return resource

    def get(self, resource_id: str) -> ResourceRecord | None:
        response = self.table.get_item(
            Key={"resource_id": resource_id},
            ConsistentRead=True,
        )

        item = response.get("Item")
        if item is None:
            return None

        return ResourceRecord.model_validate(item)

    def list_all(self) -> list[ResourceRecord]:
        resources = []
        scan_kwargs = {}

        while True:
            response = self.table.scan(**scan_kwargs)

            resources.extend(
                ResourceRecord.model_validate(item)
                for item in response.get("Items", [])
            )

            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break

            scan_kwargs["ExclusiveStartKey"] = last_key

        return resources


def get_repository():
    storage = os.getenv("CLOUDEXPIRE_STORAGE", "memory").lower()

    if storage == "memory":
        return InMemoryResourceRepository()

    if storage == "dynamodb":
        table_name = os.getenv(
            "DYNAMODB_TABLE_NAME",
            "cloudexpire-resources",
        )
        region = os.getenv("AWS_REGION", "ap-south-1")

        return DynamoDBResourceRepository(table_name, region)

    raise ValueError(f"Unsupported storage backend: {storage}")


resource_repository = get_repository()
