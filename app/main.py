
from datetime import datetime, timezone

from fastapi import FastAPI

from app.schemas import ResourceCreate
from app.services.expiry import calculate_expiry

app = FastAPI(
    title="CloudExpire",
    description="Automated temporary AWS resource lifecycle manager",
    version="0.2.0",
)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "CloudExpire",
    }


@app.post("/resources/preview")
def preview_resource(request: ResourceCreate):
    expires_at = calculate_expiry(request.ttl_hours)

    return {
        "name": request.name,
        "resource_type": request.resource_type,
        "instance_type": request.instance_type,
        "ttl_hours": request.ttl_hours,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat(),
        "status": "PREVIEW",
        "message": "Preview only. No AWS resource was created.",
    }
