import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict, model_validator


class UserCreate(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role_ids: list[uuid.UUID] = []


class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    role_ids: Optional[list[uuid.UUID]] = None


class RoleBasic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    color: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    full_name: str
    avatar_path: Optional[str]
    is_active: bool
    is_superadmin: bool
    must_change_password: bool
    last_login: Optional[datetime]
    created_at: datetime
    roles: list[RoleBasic]
    permissions: list[str] = []

    @model_validator(mode='before')
    @classmethod
    def collect_permissions(cls, data):
        if isinstance(data, dict):
            return data
        # SQLAlchemy User object — collect all permission codenames from all roles
        perms: set[str] = set()
        for role in getattr(data, 'roles', None) or []:
            for perm in getattr(role, 'permissions', None) or []:
                perms.add(perm.codename)
        return {
            'id': data.id,
            'email': data.email,
            'first_name': data.first_name,
            'last_name': data.last_name,
            'full_name': data.full_name,
            'avatar_path': getattr(data, 'avatar_path', None),
            'is_active': data.is_active,
            'is_superadmin': data.is_superadmin,
            'must_change_password': data.must_change_password,
            'last_login': getattr(data, 'last_login', None),
            'created_at': data.created_at,
            'roles': [
                {'id': str(role.id), 'name': role.name, 'color': role.color}
                for role in (getattr(data, 'roles', None) or [])
            ],
            'permissions': sorted(perms),
        }


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int
