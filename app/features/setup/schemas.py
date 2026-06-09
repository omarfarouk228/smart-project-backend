from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class SetupOrganizationData(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    app_name: str = Field(default="SmartTask", max_length=255)
    primary_color: str = Field(default="#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")
    secondary_color: str = Field(default="#8b5cf6", pattern=r"^#[0-9a-fA-F]{6}$")
    accent_color: str = Field(default="#06b6d4", pattern=r"^#[0-9a-fA-F]{6}$")
    default_theme: str = Field(default="light", pattern=r"^(light|dark|system)$")


class SetupAdminData(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8)


class SetupSMTPData(BaseModel):
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    smtp_from: str
    smtp_ssl: bool = True


class SetupPayload(BaseModel):
    organization: SetupOrganizationData
    admin: SetupAdminData
    smtp: Optional[SetupSMTPData] = None


class SetupStatus(BaseModel):
    completed: bool
