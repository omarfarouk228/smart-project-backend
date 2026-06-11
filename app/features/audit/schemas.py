import uuid
from datetime import datetime
from pydantic import BaseModel


class AuditUserBasic(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    full_name: str

    model_config = {"from_attributes": True}


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    user: AuditUserBasic | None
    action: str
    entity_type: str
    entity_id: str | None
    entity_name: str | None
    details: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
