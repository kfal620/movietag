"""Base classes and interfaces for vision pipelines."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class PipelineMetadata:
    """Metadata describing a vision pipeline."""

    id: str
    name: str
    model_id: str
    input_resolution: int
    device: str
    dtype: str
    version: Optional[str] = None
    loaded: bool = False


@dataclass
class EmbeddingResult:
    """Result of embedding extraction."""

    embedding: list[float]
    model_version: Optional[str]
    computed_at: datetime


@dataclass
class AttributeScore:
    """Score for a single attribute value."""

    attribute: str
    value: str
    confidence: float
    debug_info: Optional[dict[str, Any]] = None


class VisionPipeline(ABC):
    """Abstract base class for vision pipelines.
    
    A vision pipeline encapsulates a specific vision model (e.g., CLIP ViT-B/32)
    and provides a consistent interface for embedding extraction and attribute
    classification.
    """

    @abstractmethod
    def get_metadata(self) -> PipelineMetadata:
        """Return metadata about this pipeline.
        
        Returns:
            PipelineMetadata with id, name, model info, device, etc.
        """
        pass

    @abstractmethod
    def embed_image(
        self, image: Image.Image | bytes | str
    ) -> EmbeddingResult:
        """Extract a normalized embedding vector from an image.
        
        Args:
            image: PIL Image, image bytes, or path to image file
            
        Returns:
            EmbeddingResult with normalized float32 embedding vector
            
        Raises:
            ValueError: If image format is invalid
            RuntimeError: If model fails to process image
        """
        pass

    @abstractmethod
    def score_attributes(
        self,
        image: Optional[Image.Image] = None,
        embedding: Optional[list[float]] = None,
        session: Optional[Any] = None,
    ) -> list[AttributeScore]:
        """Score scene attributes for an image.
        
        Can accept either an image (will compute embedding) or a pre-computed
        embedding vector for efficiency.
        
        Args:
            image: PIL Image to analyze (optional if embedding provided)
            embedding: Pre-computed embedding vector (optional if image provided)
            session: Database session for prototype lookup (optional)
            
        Returns:
            List of AttributeScore objects with confidence scores
            
        Raises:
            ValueError: If neither image nor embedding is provided
            RuntimeError: If classification fails
        """
        pass

    @abstractmethod
    def status(self) -> dict[str, Any]:
        """Get current status of this pipeline.
        
        Returns:
            Dict with keys:
                - loaded: bool - whether model is loaded in memory
                - device: str - device name (cpu, cuda, mps)
                - memory_estimate: int - estimated memory usage in bytes (optional)
                - error: str - error message if load failed (optional)
        """
        pass
