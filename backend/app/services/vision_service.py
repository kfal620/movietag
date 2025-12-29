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
    
    Args:
        frame_id: Frame database ID
        pipeline_id: ID of the pipeline to use (e.g. "clip_vitb32", "openclip_vitl14")
        force: If True, recompute even if cached
        session: Database session (creates one if not provided)
        
    Returns:
        Dict with:
            - embedding: list of floats
            - embedding_dimension: int
            - attributes: list of AttributeScore dicts
            - cached: bool
            - embed_time: float (if computed)
            - attribute_time: float (if computed)
            
    Raises:
        ValueError: If frame not found or image cannot be loaded
        RuntimeError: If analysis fails
    """
    from app.models import Frame, SceneAttribute
    
    # Create session if needed
    should_close = False
    if session is None:
        session = SessionLocal()
        should_close = True
    
    try:
        # Get pipeline
        pipeline = get_pipeline(pipeline_id)
        if pipeline is None:
            raise ValueError(f"Pipeline '{pipeline_id}' not found")
        
        # Get frame
        frame = session.get(Frame, frame_id)
        if frame is None:
            raise ValueError(f"Frame {frame_id} not found")
        
        # Check cache
        if not force:
            cached = get_frame_embeddings(frame_id, pipeline_id, session)
            if cached:
                logger.info(
                    "Using cached embeddings for frame %d with pipeline %s",
                    frame_id,
                    pipeline_id,
                )
                # Get attributes from database
                attributes = (
                    session.query(SceneAttribute)
                    .filter(SceneAttribute.frame_id == frame_id)
                    .all()
                )
                
                return {
                    "embedding": cached["embedding"],
                    "embedding_dimension": len(cached["embedding"]),
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
        
        # Load image
        try:
            image = _load_frame_image(frame, session)
        except Exception as e:
            logger.error("Failed to load image for frame %d", frame_id)
            raise ValueError(f"Failed to load image: {e}") from e
        
        # Compute embedding
        logger.info(
            "Computing embedding for frame %d with pipeline %s",
            frame_id,
            pipeline_id,
        )
        embed_start = time.time()
        try:
            embedding_result = pipeline.embed_image(image)
        except Exception as e:
            logger.error("Failed to compute embedding for frame %d", frame_id)
            raise RuntimeError(f"Embedding computation failed: {e}") from e
        embed_time = time.time() - embed_start
        
        # Store embedding
        store_frame_embedding(
            frame_id=frame_id,
            pipeline_id=pipeline_id,
            embedding=embedding_result.embedding,
            model_version=embedding_result.model_version,
            session=session,
        )
        
        # Score attributes
        logger.info("Scoring attributes for frame %d", frame_id)
        attr_start = time.time()
        try:
            attribute_scores = pipeline.score_attributes(
                image=image,
                embedding=embedding_result.embedding,
                session=session,
            )
        except Exception as e:
            logger.error("Failed to score attributes for frame %d", frame_id)
            raise RuntimeError(f"Attribute scoring failed: {e}") from e
        attr_time = time.time() - attr_start
        
        # Store attributes in database
        _store_attributes(
            frame_id=frame_id,
            attribute_scores=attribute_scores,
            pipeline_id=pipeline_id,
            frame=frame,
            embedding=embedding_result.embedding,
            model_version=embedding_result.model_version,
            session=session,
        )
        
        # Create detailed analysis log
        pipeline_metadata = pipeline.get_metadata()
        analysis_log = {
            "timestamp": datetime.utcnow().isoformat(),
            "pipeline_id": pipeline_id,
            "pipeline_name": pipeline_metadata.name,
            "model_id": pipeline_metadata.model_id,
            "device": pipeline_metadata.device,
            "embedding": {
                "dimension": len(embedding_result.embedding),
                "model_version": embedding_result.model_version,
                "compute_time_sec": embed_time,
            },
            "attributes": {
                "compute_time_sec": attr_time,
                "scores": [
                    {
                        "attribute": score.attribute,
                        "value": score.value,
                        "confidence": score.confidence,
                        "debug_info": score.debug_info,
                    }
                    for score in attribute_scores
                ],
            },
        }
        
        # Update frame with analysis log
        frame.analysis_log = analysis_log
        session.add(frame)
        session.commit()
        
        logger.info(
            "Analysis complete for frame %d: embed=%.2fs, attr=%.2fs",
            frame_id,
            embed_time,
            attr_time,
        )
        
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
            "attribute_time": attr_time,
        }
    
    finally:
        if should_close:
            session.close()


def _store_attributes(
    frame_id: int, 
    attribute_scores: list, 
    pipeline_id: str,
    frame: Frame,
    embedding: list[float],
    model_version: Optional[str],
    session: Session
) -> None:
    """Helper to store attribute scores in the database."""
    from app.models import SceneAttribute

    # First delete old attributes for this frame
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
    
    # If this is the default pipeline, also update Frame.embedding for backwards compat
    if pipeline_id == "clip_vitb32":
        frame.embedding = json.dumps(embedding)
        frame.embedding_model = "CLIP"
        frame.embedding_model_version = model_version
    
    session.commit()


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
    from io import BytesIO
    
    # Try to load from S3/MinIO storage using boto3 directly
    if frame.storage_uri:
        try:
            # Parse the storage URI to get bucket and key
            from app.core.settings import get_settings
            settings = get_settings()
            
            storage_uri = frame.storage_uri
            if storage_uri.startswith("s3://"):
                remainder = storage_uri.removeprefix("s3://")
                if "/" in remainder:
                    bucket, key = remainder.split("/", 1)
                else:
                    bucket = settings.storage_frames_bucket
                    key = remainder
            else:
                bucket = settings.storage_frames_bucket
                key = storage_uri.lstrip("/")
            
            if bucket and key:
                # Use boto3 to download directly (works inside Docker)
                from app.services.storage import _build_s3_client
                client = _build_s3_client(settings.storage_endpoint_url)
                
                # Download object to BytesIO
                buffer = BytesIO()
                client.download_fileobj(bucket, key, buffer)
                buffer.seek(0)
                
                logger.info("Loaded image from storage: %s/%s", bucket, key)
                return Image.open(buffer)
        except Exception as e:
            logger.warning(
                "Failed to load from storage %s: %s",
                frame.storage_uri,
                e,
            )
    
    # Try to load from file_path as fallback
    if frame.file_path:
        try:
            # Check if it's an absolute path or needs to be resolved
            from pathlib import Path
            file_path = Path(frame.file_path)
            if file_path.exists():
                logger.info("Loaded image from file path: %s", file_path)
                return Image.open(file_path)
            else:
                # Try with /app prefix (Docker container path)
                docker_path = Path("/app") / frame.file_path
                if docker_path.exists():
                    logger.info("Loaded image from Docker path: %s", docker_path)
                    return Image.open(docker_path)
        except Exception as e:
            logger.warning(
                "Failed to load from file_path %s: %s",
                frame.file_path,
                e,
            )
    
    raise ValueError(
        f"Could not load image for frame {frame.id} from storage or filesystem. "
        f"storage_uri={frame.storage_uri}, file_path={frame.file_path}"
    )
