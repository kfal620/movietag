"""Vision analysis orchestration tasks."""

from __future__ import annotations

from typing import Any

from app.core.celery import celery_app
from app.services.vision import warmup_vision_models
from app.tasks.frames import _mark_failure, detect_actor_faces, detect_scene_attributes


@celery_app.task(name="vision.warmup_models")
def warmup_models_task() -> dict[str, str]:
    """Warm up vision models in a Celery worker."""
    try:
        warmup_vision_models()
        return {"status": "success", "message": "Models warmed up successfully"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@celery_app.task(name="vision.analyze_frames", bind=True)
def analyze_frames(self, frame_ids: list[int]) -> dict[str, Any]:
    total = len(frame_ids)
    processed = 0
    errors: list[dict[str, Any]] = []

    if total == 0:
        return {"status": "done", "processed": 0, "total": 0}

    for frame_id in frame_ids:
        try:
            detect_scene_attributes(frame_id)
            detect_actor_faces(frame_id)
        except Exception as exc:
            _mark_failure(frame_id, f"Vision analysis failed: {exc}")
            errors.append({"frame_id": frame_id, "error": str(exc)})
        finally:
            processed += 1
            self.update_state(state="PROGRESS", meta={"processed": processed, "total": total})

    status = "done" if not errors else "done_with_errors"
    return {"status": status, "processed": processed, "total": total, "errors": errors}
