from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import desc, select, text
from sqlalchemy.exc import IntegrityError

from .celery_app import celery_app
from .config import settings
from .database import SessionLocal, engine
from .logging_config import configure_logging
from .models import DeploymentJob, WebhookEvent
from .rate_limit import consume_fixed_window
from .schemas import EventDetail, EventSummary, JobDetail, JobSummary
from .security import verify_dashboard_token, verify_github_signature

configure_logging(settings.log_level)
logger = logging.getLogger(__name__)
redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    redis_client.close()


app = FastAPI(
    title="RelayOps API",
    version="1.0.0",
    description="Self-hosted GitHub webhook monitoring and controlled deployment automation.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-RelayOps-Token"],
)


def require_dashboard_access(
    x_relayops_token: Annotated[str | None, Header(alias="X-RelayOps-Token")] = None,
) -> None:
    if not verify_dashboard_token(
        expected=settings.dashboard_api_token,
        supplied=x_relayops_token,
    ):
        raise HTTPException(status_code=401, detail="Dashboard token is invalid or missing")


def _event_summary(event: WebhookEvent) -> EventSummary:
    return EventSummary.model_validate(event)


def _job_summary(job: DeploymentJob) -> JobSummary:
    return JobSummary.model_validate(job)


def _enqueue_job(job_id: int) -> None:
    try:
        celery_app.send_task("relayops.run_deployment_job", args=[job_id])
    except Exception as exc:
        logger.exception("Unable to enqueue deployment job", extra={"job_id": job_id})
        with SessionLocal() as session:
            job = session.get(DeploymentJob, job_id)
            if job:
                job.status = "queue_error"
                logs = list(job.logs or [])
                logs.append({"timestamp": "queue", "message": f"Queue error: {exc}"})
                job.logs = logs[-100:]
                session.commit()


def _request_ip(request: Request) -> str:
    # The API is only exposed through the Nginx gateway in Docker Compose.
    # Nginx adds X-Forwarded-For, so the first value is the original caller.
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()
    return request.client.host if request.client else "unknown"


@app.get("/health")
def health_check() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        redis_client.ping()
    except Exception as exc:
        logger.exception("Health check failed")
        raise HTTPException(status_code=503, detail="A dependency is unavailable") from exc
    return {"status": "ok", "database": "ok", "redis": "ok"}


@app.post("/webhooks/github", status_code=status.HTTP_202_ACCEPTED)
async def receive_github_webhook(
    request: Request,
    x_hub_signature_256: Annotated[str | None, Header(alias="X-Hub-Signature-256")] = None,
    x_github_event: Annotated[str | None, Header(alias="X-GitHub-Event")] = None,
    x_github_delivery: Annotated[str | None, Header(alias="X-GitHub-Delivery")] = None,
) -> dict[str, Any]:
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.max_webhook_bytes:
        raise HTTPException(status_code=413, detail="Webhook payload is too large")

    try:
        allowed = consume_fixed_window(
            redis_client=redis_client,
            namespace="github-webhook",
            subject=_request_ip(request),
            limit=settings.webhook_rate_limit_per_minute,
        )
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Rate-limit service unavailable") from exc
    if not allowed:
        raise HTTPException(status_code=429, detail="Webhook rate limit exceeded")

    raw_payload = await request.body()
    if len(raw_payload) > settings.max_webhook_bytes:
        raise HTTPException(status_code=413, detail="Webhook payload is too large")

    if not verify_github_signature(
        secret=settings.github_webhook_secret,
        payload=raw_payload,
        signature=x_hub_signature_256,
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    if not x_github_event or not x_github_delivery:
        raise HTTPException(status_code=400, detail="Missing GitHub webhook headers")

    try:
        payload = json.loads(raw_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Payload must be valid UTF-8 JSON") from exc

    repository = payload.get("repository", {}).get("full_name")
    sender = payload.get("sender", {}).get("login")
    action = payload.get("action")
    job_id: int | None = None

    try:
        with SessionLocal.begin() as session:
            event = WebhookEvent(
                delivery_id=x_github_delivery,
                event_type=x_github_event,
                action=action,
                repository=repository,
                sender=sender,
                payload=payload,
            )
            session.add(event)
            session.flush()

            if x_github_event == "push":
                job = DeploymentJob(event_id=event.id, status="queued", logs=[])
                session.add(job)
                session.flush()
                job_id = job.id
    except IntegrityError:
        logger.info("Duplicate webhook delivery ignored: %s", x_github_delivery)
        return {"status": "ignored_duplicate", "delivery_id": x_github_delivery}

    if job_id is not None:
        _enqueue_job(job_id)

    logger.info(
        "Webhook accepted: delivery=%s event=%s repository=%s",
        x_github_delivery,
        x_github_event,
        repository,
    )
    return {"status": "accepted", "delivery_id": x_github_delivery, "job_id": job_id}


@app.get("/events", response_model=list[EventSummary], dependencies=[Depends(require_dashboard_access)])
def list_events(
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    event_type: str | None = None,
    repository: str | None = None,
) -> list[EventSummary]:
    statement = select(WebhookEvent).order_by(desc(WebhookEvent.received_at)).limit(limit)
    if event_type:
        statement = statement.where(WebhookEvent.event_type == event_type)
    if repository:
        statement = statement.where(WebhookEvent.repository == repository)

    with SessionLocal() as session:
        events = session.scalars(statement).all()
    return [_event_summary(event) for event in events]


@app.get("/events/{event_id}", response_model=EventDetail, dependencies=[Depends(require_dashboard_access)])
def get_event(event_id: int) -> EventDetail:
    with SessionLocal() as session:
        event = session.get(WebhookEvent, event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        return EventDetail(**_event_summary(event).model_dump(), payload=event.payload)


@app.post("/events/{event_id}/replay", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_dashboard_access)])
def replay_event(event_id: int) -> dict[str, int | str]:
    with SessionLocal.begin() as session:
        event = session.get(WebhookEvent, event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        if event.event_type != "push":
            raise HTTPException(status_code=409, detail="Only push events can create deployment jobs")
        job = DeploymentJob(event_id=event.id, status="queued", logs=[])
        session.add(job)
        session.flush()
        job_id = job.id

    _enqueue_job(job_id)
    return {"status": "queued", "job_id": job_id}


@app.get("/jobs", response_model=list[JobSummary], dependencies=[Depends(require_dashboard_access)])
def list_jobs(
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[JobSummary]:
    statement = select(DeploymentJob).order_by(desc(DeploymentJob.created_at)).limit(limit)
    if status_filter:
        statement = statement.where(DeploymentJob.status == status_filter)

    with SessionLocal() as session:
        jobs = session.scalars(statement).all()
    return [_job_summary(job) for job in jobs]


@app.get("/jobs/{job_id}", response_model=JobDetail, dependencies=[Depends(require_dashboard_access)])
def get_job(job_id: int) -> JobDetail:
    with SessionLocal() as session:
        job = session.get(DeploymentJob, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobDetail(**_job_summary(job).model_dump(), logs=job.logs or [])


@app.post("/jobs/{job_id}/retry", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_dashboard_access)])
def retry_job(job_id: int) -> dict[str, int | str]:
    with SessionLocal.begin() as session:
        job = session.get(DeploymentJob, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.status == "running":
            raise HTTPException(status_code=409, detail="Job is already running")
        job.status = "queued"
        job.error_message = None
        job.finished_at = None
        logs = list(job.logs or [])
        logs.append({"timestamp": "manual", "message": "Manual retry requested."})
        job.logs = logs[-100:]

    _enqueue_job(job_id)
    return {"status": "queued", "job_id": job_id}
