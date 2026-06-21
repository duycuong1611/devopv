from __future__ import annotations

import logging
import shlex
import subprocess
import time
from datetime import datetime, timezone

from celery import Task

from .celery_app import celery_app
from .config import settings
from .database import SessionLocal
from .models import DeploymentJob, WebhookEvent

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _append_log(job: DeploymentJob, message: str) -> None:
    entries = list(job.logs or [])
    entries.append({"timestamp": _now().isoformat(), "message": message[:4_000]})
    job.logs = entries[-100:]


def _is_allowed(event: WebhookEvent) -> tuple[bool, str]:
    if settings.allowed_repository and event.repository != settings.allowed_repository:
        return False, f"Repository '{event.repository}' is not allowed."

    if settings.allowed_branch:
        ref = str(event.payload.get("ref", ""))
        expected_ref = f"refs/heads/{settings.allowed_branch}"
        if ref != expected_ref:
            return False, f"Branch '{ref or 'unknown'}' is not allowed; expected {expected_ref}."

    return True, ""


def _run_configured_deploy() -> list[str]:
    """Execute an operator-configured command without using any webhook payload as shell input."""
    if settings.deploy_mode == "simulate":
        time.sleep(1)
        return [
            "Simulation mode selected.",
            "Build validation completed.",
            "Deployment simulation completed successfully.",
        ]

    if settings.deploy_mode != "command":
        raise RuntimeError("DEPLOY_MODE must be either 'simulate' or 'command'.")
    if not settings.deploy_command:
        raise RuntimeError("DEPLOY_COMMAND is required when DEPLOY_MODE=command.")

    command = shlex.split(settings.deploy_command)
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=settings.deploy_timeout_seconds,
    )
    output = [f"Configured command: {command[0]}"]
    if result.stdout.strip():
        output.append(result.stdout.strip()[-4_000:])
    if result.stderr.strip():
        output.append(result.stderr.strip()[-4_000:])
    if result.returncode != 0:
        raise RuntimeError(f"Deployment command exited with code {result.returncode}.")
    output.append("Deployment command completed successfully.")
    return output


@celery_app.task(
    bind=True,
    name="relayops.run_deployment_job",
    max_retries=settings.celery_task_max_retries,
)
def run_deployment_job(self: Task, job_id: int) -> dict[str, str]:
    """Run a safe, asynchronous deployment job for a saved webhook event."""
    with SessionLocal() as session:
        job = session.get(DeploymentJob, job_id)
        if not job:
            return {"status": "ignored", "reason": "job_not_found"}
        if job.status == "success":
            return {"status": "ignored", "reason": "already_successful"}

        event = session.get(WebhookEvent, job.event_id)
        if not event:
            job.status = "failed"
            job.error_message = "Source webhook event no longer exists."
            job.finished_at = _now()
            _append_log(job, job.error_message)
            session.commit()
            return {"status": "failed", "reason": "event_not_found"}

        allowed, reason = _is_allowed(event)
        if not allowed:
            job.status = "skipped"
            job.finished_at = _now()
            _append_log(job, reason)
            session.commit()
            return {"status": "skipped", "reason": reason}

        job.status = "running"
        job.error_message = None
        job.attempts += 1
        job.started_at = _now()
        _append_log(
            job,
            f"Worker started {job.job_type} for {event.repository or 'unknown repository'} "
            f"(attempt {job.attempts}).",
        )
        session.commit()

    try:
        lines = _run_configured_deploy()
    except Exception as exc:  # The task records the failure before optional retry.
        message = str(exc)
        with SessionLocal() as session:
            job = session.get(DeploymentJob, job_id)
            if not job:
                return {"status": "failed", "reason": "job_not_found_after_run"}

            _append_log(job, f"Attempt failed: {message}")
            retries_remaining = self.request.retries < settings.celery_task_max_retries
            if retries_remaining:
                delay_seconds = min(2 ** self.request.retries, 60)
                job.status = "queued"
                _append_log(job, f"Retry scheduled in {delay_seconds} seconds.")
                session.commit()
                raise self.retry(exc=exc, countdown=delay_seconds)

            job.status = "failed"
            job.error_message = message
            job.finished_at = _now()
            _append_log(job, "No retries remain; job marked as failed.")
            session.commit()
        logger.exception("Deployment job %s failed", job_id)
        return {"status": "failed", "reason": message}

    with SessionLocal() as session:
        job = session.get(DeploymentJob, job_id)
        if not job:
            return {"status": "failed", "reason": "job_not_found_after_success"}
        for line in lines:
            _append_log(job, line)
        job.status = "success"
        job.finished_at = _now()
        session.commit()

    return {"status": "success"}
