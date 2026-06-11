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
    my_role: str | None = None

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int


class AddMemberRequest(BaseModel):
    user_id: uuid.UUID
    role: str = "member"

    def model_post_init(self, __context) -> None:
        if self.role not in ("owner", "member", "viewer"):
            raise ValueError("role doit être 'owner', 'member' ou 'viewer'")


class ColumnCreate(BaseModel):
    name: str
    color: str = "#94a3b8"
    is_done_column: bool = False


class ColumnUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    is_done_column: bool | None = None
    position: int | None = None


class ColumnReorderRequest(BaseModel):
    ids: list[uuid.UUID]


class RecentProjectItem(BaseModel):
    id: str
    name: str
    key: str
    color: str
    member_count: int
    task_count: int


class UpcomingTaskItem(BaseModel):
    id: str
    title: str
    priority: str
    due_date: str
    project_name: str
    project_color: str


class DashboardResponse(BaseModel):
    projects_count: int
    tasks_in_progress: int
    active_sprints: int
    my_tasks_count: int
    overdue_tasks: int
    completed_this_week: int
    recent_projects: list[RecentProjectItem]
    upcoming_tasks: list[UpcomingTaskItem]


class ColumnStat(BaseModel):
    column_id: str
    column_name: str
    color: str
    task_count: int
    is_done_column: bool


class PriorityStat(BaseModel):
    priority: str
    count: int


class MemberWorkload(BaseModel):
    user_id: str
    full_name: str
    avatar_path: str | None
    task_count: int
    done_count: int


class SprintStat(BaseModel):
    sprint_id: str
    sprint_name: str
    status: str
    total_tasks: int
    done_tasks: int


class ProjectAnalyticsResponse(BaseModel):
    total_tasks: int
    overdue_tasks: int
    done_tasks: int
    by_column: list[ColumnStat]
    by_priority: list[PriorityStat]
    member_workload: list[MemberWorkload]
    sprint_stats: list[SprintStat]
