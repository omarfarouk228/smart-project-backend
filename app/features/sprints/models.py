import uuid
import enum
from datetime import datetime, date
from sqlalchemy import String, Text, Date, DateTime, ForeignKey, func, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class SprintStatus(str, enum.Enum):
    planning = "planning"
    active = "active"
    completed = "completed"


class Sprint(Base):
    __tablename__ = "sprints"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[SprintStatus] = mapped_column(SAEnum(SprintStatus), default=SprintStatus.planning)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship("Project")
    sprint_tasks: Mapped[list["SprintTask"]] = relationship(
        "SprintTask", back_populates="sprint", cascade="all, delete-orphan"
    )

    @property
    def task_count(self) -> int:
        return len(self.sprint_tasks)


class SprintTask(Base):
    __tablename__ = "sprint_tasks"

    sprint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sprints.id", ondelete="CASCADE"), primary_key=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sprint: Mapped["Sprint"] = relationship("Sprint", back_populates="sprint_tasks")
    task: Mapped["Task"] = relationship("Task")
