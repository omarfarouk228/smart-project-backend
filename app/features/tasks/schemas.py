import uuid
from datetime import datetime, date
from pydantic import BaseModel
from app.features.tasks.models import Priority


class UserBasic(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    full_name: str
    avatar_path: str | None = None

    model_config = {"from_attributes": True}


class LabelResponse(BaseModel):
    id: uuid.UUID
    name: str
    color: str

    model_config = {"from_attributes": True}


class SubTaskResponse(BaseModel):
    id: uuid.UUID
    title: str
    is_done: bool
    position: float
    created_at: datetime

    model_config = {"from_attributes": True}


class CommentResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user: UserBasic
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    column_id: uuid.UUID
    assignee_id: uuid.UUID | None = None
    priority: Priority = Priority.medium
    start_date: date | None = None
    due_date: date | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    column_id: uuid.UUID | None = None
    assignee_id: uuid.UUID | None = None
    priority: Priority | None = None
    start_date: date | None = None
    due_date: date | None = None
    estimated_minutes: int | None = None


class TaskMoveRequest(BaseModel):
    column_id: uuid.UUID
    position: float


class TimeEntryResponse(BaseModel):
    id: uuid.UUID
    user: UserBasic
    minutes: int
    description: str | None
    logged_at: datetime

    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    column_id: uuid.UUID | None
    title: str
    description: str | None
    assignee: UserBasic | None
    reporter: UserBasic
    priority: Priority
    position: float
    start_date: date | None
    due_date: date | None
    estimated_minutes: int | None
    logged_minutes: int
    labels: list[LabelResponse]
    subtask_count: int
    subtask_done_count: int
    comment_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskDetailResponse(TaskResponse):
    subtasks: list[SubTaskResponse]
    comments: list[CommentResponse]
    time_entries: list[TimeEntryResponse]


class BoardResponse(BaseModel):
    columns: list[dict]
    tasks: list[TaskResponse]


class LabelCreate(BaseModel):
    name: str
    color: str = "#94a3b8"


class SubTaskCreate(BaseModel):
    title: str


class SubTaskUpdate(BaseModel):
    title: str | None = None
    is_done: bool | None = None


class CommentCreate(BaseModel):
    content: str


class CommentUpdate(BaseModel):
    content: str


class TimeEntryCreate(BaseModel):
    minutes: int
    description: str | None = None
