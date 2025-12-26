from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.celery import celery_app

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}")
def get_task_status(task_id: str) -> dict[str, Any]:
    result = celery_app.AsyncResult(task_id)
    state = result.state
    status_map = {
        "PENDING": "queued",
        "RECEIVED": "queued",
        "STARTED": "running",
        "PROGRESS": "running",
        "SUCCESS": "done",
        "FAILURE": "failed",
        "RETRY": "running",
    }
    status = status_map.get(state, "running")

    processed = None
    total = None
    error = None

    if isinstance(result.info, dict):
        processed = result.info.get("processed", processed)
        total = result.info.get("total", total)

    if result.successful() and isinstance(result.result, dict):
        processed = result.result.get("processed", processed)
        total = result.result.get("total", total)

    if result.failed():
        error = str(result.result)
    elif isinstance(result.result, dict) and result.result.get("errors"):
        error = "Some frames failed during analysis."

    return {
        "status": status,
        "processed": processed,
        "total": total,
        "error": error,
    }
