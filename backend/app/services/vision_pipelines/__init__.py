"""Vision pipelines package.

This package provides a clean abstraction for vision models used in the movie
tagging system. Different pipelines can be swapped out or used simultaneously.
"""

from .base import (
    AttributeScore,
    EmbeddingResult,
    PipelineMetadata,
    VisionPipeline,
)
from .clip_vitb32 import ClipViTB32Pipeline
from .openclip_vitl14 import OpenClipViTL14Pipeline
from .registry import (
    PipelineRegistry,
    get_pipeline,
    list_pipeline_ids,
    list_pipelines,
    register_pipeline,
)

__all__ = [
    # Base classes
    "VisionPipeline",
    "PipelineMetadata",
    "EmbeddingResult",
    "AttributeScore",
    # Implementations
    "ClipViTB32Pipeline",
    "OpenClipViTL14Pipeline",
    # Registry
    "PipelineRegistry",
    "register_pipeline",
    "get_pipeline",
    "list_pipelines",
    "list_pipeline_ids",
]


# Auto-register pipelines on import
def _auto_register_pipelines():
    """Auto-register all available pipelines."""
    import logging

    logger = logging.getLogger(__name__)

    try:
        standard_pipeline = ClipViTB32Pipeline()
        register_pipeline(standard_pipeline)
        logger.info("Auto-registered standard CLIP ViT-B/32 pipeline")
    except Exception as e:
        logger.error("Failed to register CLIP ViT-B/32 pipeline: %s", e)

    try:
        enhanced_pipeline = OpenClipViTL14Pipeline()
        register_pipeline(enhanced_pipeline)
        logger.info("Auto-registered enhanced OpenCLIP ViT-L/14 pipeline")
    except Exception as e:
        logger.error("Failed to register OpenCLIP ViT-L/14 pipeline: %s", e)


# Execute auto-registration on module import
_auto_register_pipelines()
