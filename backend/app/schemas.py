from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class EventSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    delivery_id: str
    event_type: str
    action: str | None
    repository: str | None
    sender: str | None
    received_at: datetime


class EventDetail(EventSummary):
    payload: dict[str, Any]


class JobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    job_type: str
    status: str
    attempts: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class JobDetail(JobSummary):
    logs: list[dict[str, str]]
