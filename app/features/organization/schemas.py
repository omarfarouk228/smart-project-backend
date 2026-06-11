import uuid
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class OrganizationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    app_name: str
    logo_path: Optional[str]
    favicon_path: Optional[str]
    primary_color: str
    secondary_color: str
    accent_color: str
    default_theme: str
    setup_completed: bool
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_from: Optional[str] = None
    smtp_ssl: bool = True
    smtp_configured: bool = False


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    app_name: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    secondary_color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    accent_color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    default_theme: Optional[str] = Field(None, pattern=r"^(light|dark|system)$")


class SMTPConfig(BaseModel):
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_password: str
    smtp_from: str
    smtp_ssl: bool = True


class SMTPTestResult(BaseModel):
    success: bool
    message: str
