from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.auth import require_role
from app.db import get_db
from app.models import Frame, FrameEmbedding, SceneAttribute

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.get("")
def list_embeddings(
    frame_id: int | None = Query(default=None, description="Filter by frame ID"),
    pipeline_id: str | None = Query(default=None, description="Filter by pipeline ID"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List all embeddings across all frames with optional filtering.
    
    Returns embeddings with frame context, pipeline information, and metadata.
    Supports pagination similar to the frames endpoint.
    """
    query = (
        db.query(FrameEmbedding)
        .options(joinedload(FrameEmbedding.frame))
    )
    
    if frame_id is not None:
        query = query.filter(FrameEmbedding.frame_id == frame_id)
    if pipeline_id:
        query = query.filter(FrameEmbedding.pipeline_id == pipeline_id)
    
    total = query.count()
    
    embeddings = (
        query
        .order_by(FrameEmbedding.frame_id.desc(), FrameEmbedding.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    
    items = []
    for emb in embeddings:
        # Parse embedding to get dimension
        try:
            embedding_data = json.loads(emb.embedding) if isinstance(emb.embedding, str) else emb.embedding
            dimension = len(embedding_data) if embedding_data else 0
        except Exception:
            dimension = 0
        
        items.append({
            "id": emb.id,
            "frame_id": emb.frame_id,
            "pipeline_id": emb.pipeline_id,
            "dimension": dimension,
            "model_version": emb.model_version,
            "created_at": emb.created_at.isoformat() if emb.created_at else None,
            "frame": {
                "id": emb.frame.id,
                "movie_title": emb.frame.movie.title if emb.frame.movie else None,
                "status": emb.frame.status,
            } if emb.frame else None,
        })
    
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/verified-attributes")
def get_verified_attributes(
    attribute: str | None = Query(default=None, description="Filter by attribute name"),
    value: str | None = Query(default=None, description="Filter by attribute value"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get all verified attributes used in prototype computation.
    
    Returns aggregated data showing which attributes are verified,
    how many examples exist, and which frames contribute to each prototype.
    """
    query = (
        db.query(
            SceneAttribute.attribute,
            SceneAttribute.value,
            func.count(SceneAttribute.id).label("count"),
            func.array_agg(SceneAttribute.frame_id).label("frame_ids"),
        )
        .filter(SceneAttribute.is_verified == True)
        .group_by(SceneAttribute.attribute, SceneAttribute.value)
    )
    
    if attribute:
        query = query.filter(SceneAttribute.attribute == attribute)
    if value:
        query = query.filter(SceneAttribute.value == value)
    
    results = query.all()
    
    prototypes = []
    for row in results:
        prototypes.append({
            "attribute": row.attribute,
            "value": row.value,
            "count": row.count,
            "frame_ids": row.frame_ids,
        })
    
    return {
        "prototypes": prototypes,
        "total": len(prototypes),
    }


@router.get("/frames/{frame_id}")
def get_frame_embeddings(
    frame_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Fetch all embeddings for a specific frame.
    
    Returns all pipeline embeddings with metadata and flags
    indicating which are user-edited vs pipeline defaults.
    """
    frame = db.get(Frame, frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="Frame not found")
    
    embeddings = (
        db.query(FrameEmbedding)
        .filter(FrameEmbedding.frame_id == frame_id)
        .order_by(FrameEmbedding.created_at.desc())
        .all()
    )
    
    items = []
    for emb in embeddings:
        # Parse embedding to get dimension
        try:
            embedding_data = json.loads(emb.embedding) if isinstance(emb.embedding, str) else emb.embedding
            dimension = len(embedding_data) if embedding_data else 0
        except Exception:
            dimension = 0
        
        items.append({
            "id": emb.id,
            "frame_id": emb.frame_id,
            "pipeline_id": emb.pipeline_id,
            "dimension": dimension,
            "model_version": emb.model_version,
            "created_at": emb.created_at.isoformat() if emb.created_at else None,
        })
    
    return {
        "frame_id": frame_id,
        "embeddings": items,
        "total": len(items),
    }


@router.delete("/frames/{frame_id}/embeddings/{pipeline_id}")
def delete_frame_embedding(
    frame_id: int,
    pipeline_id: str,
    db: Session = Depends(get_db),
    _: object = Depends(require_role("moderator", "admin")),
) -> dict[str, Any]:
    """Delete a specific embedding for a frame.
    
    If other embeddings exist for this frame/pipeline, the most recent
    is kept (implementing revert behavior). If this is the last embedding
    for this pipeline, it's deleted with a warning flag.
    """
    frame = db.get(Frame, frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="Frame not found")
    
    # Get all embeddings for this frame and pipeline, ordered by creation time
    embeddings = (
        db.query(FrameEmbedding)
        .filter(
            FrameEmbedding.frame_id == frame_id,
            FrameEmbedding.pipeline_id == pipeline_id,
        )
        .order_by(FrameEmbedding.created_at.desc())
        .all()
    )
    
    if not embeddings:
        raise HTTPException(status_code=404, detail="Embedding not found")
    
    # Delete the most recent embedding (assumed to be user-edited)
    most_recent = embeddings[0]
    db.delete(most_recent)
    db.commit()
    
    # Check if there are remaining embeddings for this pipeline
    remaining_count = len(embeddings) - 1
    reverted = remaining_count > 0
    
    # Check if frame has any embeddings left at all
    total_remaining = (
        db.query(func.count(FrameEmbedding.id))
        .filter(FrameEmbedding.frame_id == frame_id)
        .scalar()
    )
    
    warning = None
    if total_remaining == 0:
        warning = "Frame has no embeddings remaining. Re-analysis recommended."
        # Optionally update frame status
        frame.status = "needs_analyzing"
        db.add(frame)
        db.commit()
    
    return {
        "status": "deleted",
        "frame_id": frame_id,
        "pipeline_id": pipeline_id,
        "reverted": reverted,
        "remaining_for_pipeline": remaining_count,
        "total_remaining": total_remaining,
        "warning": warning,
    }


@router.delete("/frames/{frame_id}/embeddings")
def delete_all_frame_embeddings(
    frame_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(require_role("moderator", "admin")),
) -> dict[str, Any]:
    """Delete all embeddings for a frame (bulk deletion).
    
    Requires moderator/admin role. Removes all pipeline embeddings
    and updates frame status to needs_analyzing.
    """
    frame = db.get(Frame, frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="Frame not found")
    
    # Count how many we're deleting
    count = (
        db.query(func.count(FrameEmbedding.id))
        .filter(FrameEmbedding.frame_id == frame_id)
        .scalar()
    )
    
    if count == 0:
        raise HTTPException(status_code=404, detail="No embeddings found for this frame")
    
    # Delete all embeddings
    db.query(FrameEmbedding).filter(FrameEmbedding.frame_id == frame_id).delete()
    
    # Update frame status
    frame.status = "needs_analyzing"
    db.add(frame)
    db.commit()
    
    return {
        "status": "deleted",
        "frame_id": frame_id,
        "deleted_count": count,
        "warning": "All embeddings removed. Frame requires re-analysis.",
    }
