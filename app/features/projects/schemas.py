import uuid
from datetime import datetime
from pydantic import BaseModel


class ColumnResponse(BaseModel):
    id: uuid.UUID
    name: str
    color: str
    position: int
    is_done_column: bool

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    key: str
    color: str = "#4f46e5"


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None


class UserBasic(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    full_name: str
    avatar_path: str | None = None

    model_config = {"from_attributes": True}


class ProjectMemberResponse(BaseModel):
    id: uuid.UUID
    user: UserBasic
    role: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    key: str
    color: str
    owner_id: uuid.UUID
    member_count: int
    created_at: datetime
    columns: list[ColumnResponse]

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int


class AddMemberRequest(BaseModel):
    user_id: uuid.UUID
    role: str = "member"
