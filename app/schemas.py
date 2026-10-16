from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, StringConstraints
from typing import Annotated


ResourceName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=50,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9-]*$",
    ),
]


class ResourceCreate(BaseModel):
    name: ResourceName
    resource_type: Literal["ec2"]
    ttl_hours: int = Field(ge=1, le=24)
    instance_type: Literal["t3.micro", "t3.small"] = "t3.micro"

class ResourceRecord(BaseModel):
    resource_id: str
    name: str
    resource_type: Literal["ec2"]
    ttl_hours: int
    instance_type: Literal["t3.micro", "t3.small"]
    created_at: datetime
    expires_at: datetime
    status: Literal[
        "REQUESTED",
        "ACTIVE",
        "CLEANUP_PENDING",
        "CLEANED",
        "FAILED",
    ]
    aws_resource_id: str | None = None