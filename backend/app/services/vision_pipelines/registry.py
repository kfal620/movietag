"""Pipeline registry for managing available vision pipelines."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import PipelineMetadata, VisionPipeline

logger = logging.getLogger(__name__)


class PipelineRegistry:
    """Singleton registry for vision pipelines."""

    _instance: PipelineRegistry | None = None
    _pipelines: dict[str, VisionPipeline]

    def __new__(cls) -> PipelineRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._pipelines = {}
        return cls._instance

    def register(self, pipeline: VisionPipeline) -> None:
        """Register a pipeline.
        
        Args:
            pipeline: VisionPipeline instance to register
        """
        metadata = pipeline.get_metadata()
        pipeline_id = metadata.id
        
        if pipeline_id in self._pipelines:
            logger.warning(
                "Pipeline %s already registered, overwriting", pipeline_id
            )
        
        self._pipelines[pipeline_id] = pipeline
        logger.info("Registered vision pipeline: %s (%s)", pipeline_id, metadata.name)

    def get_pipeline(self, pipeline_id: str) -> VisionPipeline:
        """Get a pipeline by ID.
        
        Args:
            pipeline_id: Unique pipeline identifier
            
        Returns:
            VisionPipeline instance
            
        Raises:
            KeyError: If pipeline_id is not registered
        """
        if pipeline_id not in self._pipelines:
            available = list(self._pipelines.keys())
            raise KeyError(
                f"Pipeline '{pipeline_id}' not found. "
                f"Available pipelines: {available}"
            )
        return self._pipelines[pipeline_id]

    def list_pipelines(self) -> list[PipelineMetadata]:
        """List all registered pipelines.
        
        Returns:
            List of PipelineMetadata for all registered pipelines
        """
        return [p.get_metadata() for p in self._pipelines.values()]

    def list_pipeline_ids(self) -> list[str]:
        """List all registered pipeline IDs.
        
        Returns:
            List of pipeline IDs
        """
        return list(self._pipelines.keys())


# Global registry instance
_registry = PipelineRegistry()


def register_pipeline(pipeline: VisionPipeline) -> None:
    """Register a pipeline with the global registry.
    
    Args:
        pipeline: VisionPipeline instance to register
    """
    _registry.register(pipeline)


def get_pipeline(pipeline_id: str) -> VisionPipeline:
    """Get a pipeline from the global registry.
    
    Args:
        pipeline_id: Unique pipeline identifier
        
    Returns:
        VisionPipeline instance
        
    Raises:
        KeyError: If pipeline_id is not registered
    """
    return _registry.get_pipeline(pipeline_id)


def list_pipelines() -> list[PipelineMetadata]:
    """List all registered pipelines from the global registry.
    
    Returns:
        List of PipelineMetadata for all registered pipelines
    """
    return _registry.list_pipelines()


def list_pipeline_ids() -> list[str]:
    """List all registered pipeline IDs.
    
    Returns:
        List of pipeline IDs
    """
    return _registry.list_pipeline_ids()
