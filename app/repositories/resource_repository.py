
from app.schemas import ResourceRecord


class InMemoryResourceRepository:
    """Temporary development storage; data is lost on restart."""

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
        """Reset development storage for tests."""
        self._resources.clear()


resource_repository = InMemoryResourceRepository()
