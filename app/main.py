
import hmac
import os

import boto3
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.repositories.resource_repository import resource_repository
from app.schemas import ResourceCreate, ResourceRecord
from app.services.resource_service import create_resource_record

app = FastAPI(
    title="CloudExpire",
    description="Automated temporary AWS resource lifecycle manager",
    version="0.5.0",
)

bearer_scheme = HTTPBearer(auto_error=False)
_cached_api_token: str | None = None


def get_expected_api_token() -> str | None:
    """Use a local environment token or retrieve the AWS SSM SecureString."""
    global _cached_api_token

    # Preserve local development and existing authentication tests.
    environment_token = os.getenv("CLOUDEXPIRE_API_TOKEN")
    if environment_token:
        return environment_token

    parameter_name = os.getenv("CLOUDEXPIRE_API_TOKEN_PARAMETER")
    if not parameter_name:
        return None

    if _cached_api_token is None:
        try:
            ssm = boto3.client(
                "ssm",
                region_name=os.getenv("AWS_REGION", "ap-south-1"),
            )
            response = ssm.get_parameter(
                Name=parameter_name,
                WithDecryption=True,
            )
            _cached_api_token = response["Parameter"]["Value"]
        except Exception as exc:
            # Never log the token or the returned parameter value.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="API authentication could not be loaded",
            ) from exc

    return _cached_api_token


def require_api_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    expected_token = get_expected_api_token()

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
