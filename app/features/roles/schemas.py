import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    codename: str
    name: str
    description: Optional[str]
    category: str


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    color: str = Field(default="#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")
    permission_ids: list[uuid.UUID] = []


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    permission_ids: Optional[list[uuid.UUID]] = None


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: Optional[str]
    color: str
    is_system: bool
    created_at: datetime
    permissions: list[PermissionResponse]


class RoleListResponse(BaseModel):
    items: list[RoleResponse]
    total: int
