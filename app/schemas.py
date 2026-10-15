
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
