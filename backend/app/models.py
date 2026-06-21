from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    delivery_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    action: Mapped[str | None] = mapped_column(String(100), nullable=True)
    repository: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    sender: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    jobs: Mapped[list["DeploymentJob"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class DeploymentJob(Base):
    __tablename__ = "deployment_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("webhook_events.id", ondelete="CASCADE"), index=True, nullable=False
    )
    job_type: Mapped[str] = mapped_column(String(50), default="deployment", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    logs: Mapped[list[dict[str, str]]] = mapped_column(JSONB, default=list, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    event: Mapped["WebhookEvent"] = relationship(back_populates="jobs")
