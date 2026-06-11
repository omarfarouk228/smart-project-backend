import uuid
from datetime import datetime, date
from pydantic import BaseModel
from app.features.sprints.models import SprintStatus
from app.features.tasks.schemas import TaskResponse


class SprintCreate(BaseModel):
    name: str
    goal: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class SprintUpdate(BaseModel):
    name: str | None = None
    goal: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class SprintResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    goal: str | None
    start_date: date | None
    end_date: date | None
    status: SprintStatus
    task_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SprintBoardResponse(BaseModel):
    sprint: SprintResponse
    columns: list[dict]
    tasks: list[TaskResponse]


class SprintWithTasksResponse(SprintResponse):
    tasks: list[TaskResponse]


class BacklogResponse(BaseModel):
    tasks: list[TaskResponse]
    sprints: list[SprintWithTasksResponse]
