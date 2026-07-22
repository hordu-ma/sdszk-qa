"""WP2.5 试点组织管理 Schema（平台 admin 专用）。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    code: str = Field(min_length=2, max_length=50, pattern=r"^[a-z0-9][a-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=200)
    note: str | None = Field(default=None, max_length=500)


class OrganizationStatusUpdate(BaseModel):
    status: Literal["pilot_active", "suspended"]


class OrganizationAssignRequest(BaseModel):
    user_id: int
    organization_id: int | None = None


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    status: str
    note: str | None
    created_at: datetime
