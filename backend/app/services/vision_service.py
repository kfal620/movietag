"""Vision service orchestration layer.

This module provides high-level functions for analyzing frames with different
vision pipelines, managing embedding storage, and caching results.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Optional

from PIL import Image
from sqlalchemy.orm import Session

from app.models import Frame, FrameEmbedding, SceneAttribute
from app.services import storage
from app.services.vision_pipelines import get_pipeline

logger = logging.getLogger(__name__)


def analyze_frame(
    frame_id: int,
    pipeline_id: str,
    force: bool = False,
    session: Optional[Session] = None,
) -> dict[str, Any]:
    """Analyze a frame with a specified vision pipeline.
    
    This is the main orchestration function that:
    1. Checks for cached embeddings/attributes
    2. If not cached or force=True, loads image and runs pipeline
    3. Stores results in database
    4. Returns embeddings + attributes
    
    Args:
        frame_id: Database ID of frame to analyze
        pipeline_id: ID of vision pipeline to use
        force: If True, recompute even if cached
        session: Database session
        
    Returns:
        Dict with:
            - embedding: list[float]
            - embedding_dimension: int
            - attributes: list[dict] with attribute predictions
            - cached: bool - whether result was from cache
            - embed_time: float - seconds to compute embedding (if not cached)
            - attribute_time: float - seconds to score attributes (if not cached)
            
    Raises:
        ValueError: If frame not found or image cannot be loaded
        KeyError: If pipeline_id is invalid
        RuntimeError: If analysis fails
    """
    if session is None:
        from app.db import get_db
        session = next(get_db())
    
    # Check if frame exists
    frame = session.query(Frame).filter(Frame.id == frame_id).first()
    if not frame:
        raise ValueError(f"Frame {frame_id} not found")
    
    # Check for cached embedding
    cached_embedding = None
    if not force:
        cached = (
            session.query(FrameEmbedding)
            .filter(
                FrameEmbedding.frame_id == frame_id,
                FrameEmbedding.pipeline_id == pipeline_id,
            )
            .first()
        )
        if cached:
            logger.info(
                "Cache hit for frame %d with pipeline %s",
                frame_id,
                pipeline_id,
            )
            cached_embedding = json.loads(cached.embedding)
    
    # If cached and not forcing, get attributes from DB
    if cached_embedding is not None and not force:
        # Get existing attributes for this frame
        # Note: We don't store pipeline_id with SceneAttribute yet,
        # so we assume attributes correspond to most recent analysis
        attributes = (
            session.query(SceneAttribute)
            .filter(SceneAttribute.frame_id == frame_id)
            .all()
        )
        
        return {
            "embedding": cached_embedding,
            "embedding_dimension": len(cached_embedding),
            "attributes": [
                {
                    "attribute": attr.attribute,
                    "value": attr.value,
                    "confidence": attr.confidence,
                    "is_verified": attr.is_verified,
                }
                for attr in attributes
            ],
            "cached": True,
        }
    
    # Need to compute - load image
    try:
        image = _load_frame_image(frame, session)
    except Exception as e:
        logger.exception("Failed to load image for frame %d", frame_id)
        raise ValueError(f"Failed to load image: {e}") from e
    
    # Get pipeline
    pipeline = get_pipeline(pipeline_id)
    logger.info(
        "Analyzing frame %d with pipeline %s (force=%s)",
        frame_id,
        pipeline_id,
        force,
    )
    
    # Extract embedding
    start_time = time.time()
    try:
        embedding_result = pipeline.embed_image(image)
        embed_time = time.time() - start_time
        logger.info(
            "Embedded frame %d in %.2fs (dim=%d)",
            frame_id,
            embed_time,
            len(embedding_result.embedding),
        )
    except Exception as e:
        logger.exception("Failed to embed frame %d", frame_id)
        raise RuntimeError(f"Embedding extraction failed: {e}") from e
    
    # Score attributes
    start_time = time.time()
    try:
        attribute_scores = pipeline.score_attributes(
            embedding=embedding_result.embedding,
            session=session,
        )
        attribute_time = time.time() - start_time
        logger.info(
            "Scored %d attributes for frame %d in %.2fs",
            len(attribute_scores),
            frame_id,
            attribute_time,
        )
    except Exception as e:
        logger.exception("Failed to score attributes for frame %d", frame_id)
        raise RuntimeError(f"Attribute scoring failed: {e}") from e
    
    # Store embedding
    store_frame_embedding(
        frame_id=frame_id,
        pipeline_id=pipeline_id,
        embedding=embedding_result.embedding,
        model_version=embedding_result.model_version or "unknown",
        session=session,
    )
    
    # Store attributes (replace existing for this frame)
    # First delete old attributes
    session.query(SceneAttribute).filter(
        SceneAttribute.frame_id == frame_id
    ).delete()
    
    # Insert new attributes
    for score in attribute_scores:
        attr = SceneAttribute(
            frame_id=frame_id,
            attribute=score.attribute,
            value=score.value,
            confidence=score.confidence,
            is_verified=False,
        )
        session.add(attr)
    
    session.commit()
    
    # If this is the default pipeline, also update Frame.embedding for backwards compat
    if pipeline_id == "clip_vitb32":
        frame.embedding = json.dumps(embedding_result.embedding)
        frame.embedding_model = "CLIP"
        frame.embedding_model_version = embedding_result.model_version
        session.commit()
    
    return {
        "embedding": embedding_result.embedding,
        "embedding_dimension": len(embedding_result.embedding),
        "attributes": [
            {
                "attribute": score.attribute,
                "value": score.value,
                "confidence": score.confidence,
                "is_verified": False,
            }
            for score in attribute_scores
        ],
        "cached": False,
        "embed_time": embed_time,
        "attribute_time": attribute_time,
    }


def store_frame_embedding(
    frame_id: int,
    pipeline_id: str,
    embedding: list[float],
    model_version: str,
    session: Session,
) -> None:
    """Store frame embedding in database.
    
    Updates existing embedding if (frame_id, pipeline_id) pair exists,
    otherwise creates new record.
    
    Args:
        frame_id: Frame database ID
        pipeline_id: Pipeline identifier
        embedding: Embedding vector
        model_version: Model version string
        session: Database session
    """
    # Check if embedding exists
    existing = (
        session.query(FrameEmbedding)
        .filter(
            FrameEmbedding.frame_id == frame_id,
            FrameEmbedding.pipeline_id == pipeline_id,
        )
        .first()
    )
    
    if existing:
        # Update
        existing.embedding = json.dumps(embedding)
        existing.model_version = model_version
        existing.updated_at = datetime.utcnow()
        logger.info(
            "Updated embedding for frame %d, pipeline %s",
            frame_id,
            pipeline_id,
        )
    else:
        # Insert
        frame_embedding = FrameEmbedding(
            frame_id=frame_id,
            pipeline_id=pipeline_id,
            embedding=json.dumps(embedding),
            model_version=model_version,
        )
        session.add(frame_embedding)
        logger.info(
            "Stored new embedding for frame %d, pipeline %s",
            frame_id,
            pipeline_id,
        )
    
    session.commit()


def get_frame_embeddings(
    frame_id: int,
    pipeline_id: str,
    session: Session,
) -> Optional[dict[str, Any]]:
    """Retrieve stored embeddings for a frame + pipeline.
    
    Args:
        frame_id: Frame database ID
        pipeline_id: Pipeline identifier
        session: Database session
        
    Returns:
        Dict with embedding and metadata, or None if not found
    """
    frame_embedding = (
        session.query(FrameEmbedding)
        .filter(
            FrameEmbedding.frame_id == frame_id,
            FrameEmbedding.pipeline_id == pipeline_id,
        )
        .first()
    )
    
    if not frame_embedding:
        return None
    
    return {
        "frame_id": frame_id,
        "pipeline_id": pipeline_id,
        "embedding": json.loads(frame_embedding.embedding),
        "model_version": frame_embedding.model_version,
        "created_at": frame_embedding.created_at.isoformat(),
        "updated_at": frame_embedding.updated_at.isoformat(),
    }


def _load_frame_image(frame: Frame, session: Session) -> Image.Image:
    """Load image for a frame from storage.
    
    Args:
        frame: Frame database object
        session: Database session
        
    Returns:
        PIL Image
        
    Raises:
        ValueError: If image cannot be loaded
    """
    # Try to load from storage
    if frame.storage_uri:
        try:
            image_bytes = storage.get_frame_image_bytes(frame.storage_uri)
            from io import BytesIO
            return Image.open(BytesIO(image_bytes))
        except Exception as e:
            logger.warning(
                "Failed to load from storage %s: %s",
                frame.storage_uri,
                e,
            )
    
    # Try to load from file_path as fallback
    if frame.file_path:
        try:
            return Image.open(frame.file_path)
        except Exception as e:
            logger.warning(
                "Failed to load from file_path %s: %s",
                frame.file_path,
                e,
            )
    
    raise ValueError(
        f"Could not load image for frame {frame.id} from storage or filesystem"
    )
