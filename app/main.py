
from fastapi import FastAPI, HTTPException, status

from app.repositories.resource_repository import resource_repository
from app.schemas import ResourceCreate, ResourceRecord
from app.services.resource_service import create_resource_record

app = FastAPI(
    title="CloudExpire",
    description="Automated temporary AWS resource lifecycle manager",
    version="0.3.0",
)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "CloudExpire",
    }


@app.post(
    "/resources",
    response_model=ResourceRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_resource(request: ResourceCreate):
    return create_resource_record(request)


@app.get("/resources", response_model=list[ResourceRecord])
def list_resources():
    return resource_repository.list_all()


@app.get("/resources/{resource_id}", response_model=ResourceRecord)
def get_resource(resource_id: str):
    resource = resource_repository.get(resource_id)

    if resource is None:
        raise HTTPException(
            status_code=404,
            detail="Resource not found",
        )

    return resource
