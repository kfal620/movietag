"""CLIP ViT-B/32 pipeline implementation (wraps existing model)."""

from __future__ import annotations

import io
import json
import logging
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from PIL import Image

from .base import AttributeScore, EmbeddingResult, PipelineMetadata, VisionPipeline

logger = logging.getLogger(__name__)


# Import scene attribute prompts from main vision module
# We'll keep these centralized for now
from app.services.vision import SCENE_ATTRIBUTE_PROMPTS, _get_attribute_prototypes


@lru_cache(maxsize=1)
def _get_clip_vitb32_components():
    """Load and cache CLIP ViT-B/32 model components.
    
    Returns:
        Tuple of (model, preprocess, tokenizer, device)
    """
    import open_clip  # type: ignore
    
    # Import device utility from main vision module
    from app.services.vision import _device
    
    # Get settings for model configuration
    try:
        from app.core.settings import get_settings
        settings = get_settings()
        model_name = settings.clip_model_name
        pretrained = settings.clip_pretrained
    except Exception:
        model_name = "ViT-B-32"
        pretrained = "openai"
    
    device = _device()
    model, _, preprocess = open_clip.create_model_and_transforms(
        model_name, pretrained=pretrained
    )
    model.to(device)
    model.eval()
    tokenizer = open_clip.get_tokenizer(model_name)
    
    logger.info(
        "Loaded CLIP ViT-B/32 pipeline: %s (%s) on %s",
        model_name,
        pretrained,
        device,
    )
    
    return model, preprocess, tokenizer, device


class ClipViTB32Pipeline(VisionPipeline):
    """Vision pipeline using CLIP ViT-B/32 model.
    
    This wraps the existing CLIP implementation to provide a consistent
    pipeline interface while preserving all current behavior.
    """

    def __init__(self):
        """Initialize the CLIP ViT-B/32 pipeline."""
        self._loaded = False
        self._error: Optional[str] = None

    def get_metadata(self) -> PipelineMetadata:
        """Return metadata about this pipeline."""
        try:
            _, _, _, device = _get_clip_vitb32_components()
            device_str = str(device)
            self._loaded = True
        except Exception as e:
            logger.exception("Failed to load CLIP ViT-B/32 model")
            device_str = "unknown"
            self._loaded = False
            self._error = str(e)
        
        # Get version from open_clip if available
        version = None
        try:
            import importlib.metadata
            version = importlib.metadata.version("open_clip_torch")
        except Exception:
            pass
        
        return PipelineMetadata(
            id="clip_vitb32",
            name="CLIP ViT-B/32 (Standard)",
            model_id="ViT-B-32",
            input_resolution=224,
            device=device_str,
            dtype="float32",
            version=version,
            loaded=self._loaded,
        )

    def embed_image(
        self, image: Image.Image | bytes | str
    ) -> EmbeddingResult:
        """Extract normalized CLIP embedding from image.
        
        Args:
            image: PIL Image, image bytes, or path to image file
            
        Returns:
            EmbeddingResult with normalized float32 embedding
        """
        # Convert to PIL Image if needed
        if isinstance(image, bytes):
            image = Image.open(io.BytesIO(image))
        elif isinstance(image, str):
            image = Image.open(Path(image))
        elif not isinstance(image, Image.Image):
            raise ValueError(f"Unsupported image type: {type(image)}")
        
        # Ensure RGB mode
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        try:
            # Lazy import torch
            from app.services.vision import _lazy_import_torch
            torch = _lazy_import_torch()
            
            model, preprocess, _, device = _get_clip_vitb32_components()
            
            # Preprocess and embed
            image_tensor = preprocess(image).unsqueeze(0).to(device)
            with torch.no_grad():
                features = model.encode_image(image_tensor)
                features = features / features.norm(dim=-1, keepdim=True)
            
            embedding = features.squeeze(0).detach().cpu().tolist()
            
            # Get model version
            try:
                import importlib.metadata
                model_version = importlib.metadata.version("open_clip_torch")
            except Exception:
                model_version = None
            
            return EmbeddingResult(
                embedding=embedding,
                model_version=model_version,
                computed_at=datetime.utcnow(),
            )
        
        except Exception as e:
            logger.exception("Failed to embed image with CLIP ViT-B/32")
            raise RuntimeError(f"Embedding extraction failed: {e}") from e

    def score_attributes(
        self,
        image: Optional[Image.Image] = None,
        embedding: Optional[list[float]] = None,
        session: Optional[Any] = None,
    ) -> list[AttributeScore]:
        """Score scene attributes using CLIP zero-shot classification.
        
        Args:
            image: PIL Image to analyze (optional if embedding provided)
            embedding: Pre-computed embedding (optional if image provided)
            session: Database session for prototype lookup (optional)
            
        Returns:
            List of AttributeScore objects
        """
        if image is None and embedding is None:
            raise ValueError("Must provide either image or embedding")
        
        try:
            from app.services.vision import _lazy_import_torch
            torch = _lazy_import_torch()
            
            model, preprocess, tokenizer, device = _get_clip_vitb32_components()
            
            # Get image features
            if embedding is not None:
                # Use pre-computed embedding
                image_features = torch.tensor(embedding, dtype=torch.float32).unsqueeze(0).to(device)
            else:
                # Compute from image
                if image.mode != "RGB":
                    image = image.convert("RGB")
                image_tensor = preprocess(image).unsqueeze(0).to(device)
                with torch.no_grad():
                    image_features = model.encode_image(image_tensor)
                    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            
            predictions: list[AttributeScore] = []
            
            # Iterate over attributes and encode text prompts
            for attribute, options in SCENE_ATTRIBUTE_PROMPTS.items():
                labels = list(options.keys())
                prompts = list(options.values())
                
                text_tokens = tokenizer(prompts).to(device)
                with torch.no_grad():
                    text_features = model.encode_text(text_tokens)
                    text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                    
                    # Compute similarity
                    similarity = (image_features @ text_features.T).squeeze(0)
                    
                    # Integrate prototypes if session provided
                    proto_map = {}
                    if session is not None:
                        proto_map = _get_attribute_prototypes(session, attribute, pipeline_id="clip_vitb32")
                    
                    # Store debug info
                    label_scores = []
                    
                    for i, label in enumerate(labels):
                        clip_score = similarity[i].item()
                        proto_score = None
                        proto_count = 0
                        
                        if label in proto_map:
                            proto_vec, count = proto_map[label]
                            proto_vec = proto_vec.to(device)
                            proto_sim = (image_features @ proto_vec.unsqueeze(0).T).squeeze(0).item()
                            
                            # Weight: 60% text, 40% prototypes
                            new_score = 0.6 * clip_score + 0.4 * proto_sim
                            similarity[i] = new_score
                            
                            proto_score = proto_sim
                            proto_count = count
                        
                        label_scores.append({
                            "label": label,
                            "clip_score": clip_score,
                            "prototype_score": proto_score,
                            "prototype_count": proto_count,
                            "final_score": similarity[i].item(),
                        })
                    
                    # Handle multi-label for lighting
                    if attribute == "lighting":
                        best_score = float(similarity.max())
                        threshold = max(0.2, best_score * 0.85)
                        
                        sorted_indices = similarity.argsort(descending=True)
                        for idx in sorted_indices:
                            score = float(similarity[idx])
                            if score < threshold:
                                break
                            
                            lbl = labels[idx]
                            d_info = next((x for x in label_scores if x["label"] == lbl), None)
                            
                            predictions.append(
                                AttributeScore(
                                    attribute=attribute,
                                    value=lbl,
                                    confidence=round(score, 3),
                                    debug_info={"selected": d_info, "candidates": label_scores},
                                )
                            )
                    else:
                        # Single-label: argmax
                        best_idx = similarity.argmax().item()
                        best_score = float(similarity[best_idx])
                        
                        lbl = labels[best_idx]
                        d_info = next((x for x in label_scores if x["label"] == lbl), None)
                        
                        predictions.append(
                            AttributeScore(
                                attribute=attribute,
                                value=lbl,
                                confidence=round(best_score, 3),
                                debug_info={"selected": d_info, "candidates": label_scores},
                            )
                        )
            
            return predictions
        
        except Exception as e:
            logger.exception("Failed to score attributes with CLIP ViT-B/32")
            raise RuntimeError(f"Attribute scoring failed: {e}") from e

    def status(self) -> dict[str, Any]:
        """Get current status of this pipeline."""
        try:
            _, _, _, device = _get_clip_vitb32_components()
            return {
                "loaded": True,
                "device": str(device),
                "error": None,
            }
        except Exception as e:
            return {
                "loaded": False,
                "device": "unknown",
                "error": str(e),
            }
