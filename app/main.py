
import hmac
import os

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.repositories.resource_repository import resource_repository
from app.schemas import ResourceCreate, ResourceRecord
from app.services.resource_service import create_resource_record

app = FastAPI(
    title="CloudExpire",
    description="Automated temporary AWS resource lifecycle manager",
    version="0.4.0",
)

bearer_scheme = HTTPBearer(auto_error=False)


def require_api_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    expected_token = os.getenv("CLOUDEXPIRE_API_TOKEN")

    # Fail closed if authentication has not been configured.
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured",
        )

    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not hmac.compare_digest(credentials.credentials, expected_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "CloudExpire"}


@app.post(
    "/resources",
    response_model=ResourceRecord,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_token)],
)
def create_resource(request: ResourceCreate):
    return create_resource_record(request)


@app.get(
    "/resources",
    response_model=list[ResourceRecord],
    dependencies=[Depends(require_api_token)],
)
def list_resources():
    return resource_repository.list_all()


@app.get(
    "/resources/{resource_id}",
    response_model=ResourceRecord,
    dependencies=[Depends(require_api_token)],
)
def get_resource(resource_id: str):
    resource = resource_repository.get(resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return resource
