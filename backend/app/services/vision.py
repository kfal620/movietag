"""Shared utilities for production-grade vision models.

This module centralizes heavyweight model loading (CLIP for embeddings and
FaceNet/MTCNN for face detection) so Celery tasks can reuse a single set of
weights instead of re-downloading them on every invocation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
import open_clip
import torch
from PIL import Image
from facenet_pytorch import InceptionResnetV1, MTCNN

logger = logging.getLogger(__name__)


def _device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


@dataclass
class ClipComponents:
    model: torch.nn.Module
    preprocess: callable
    tokenizer: callable
    device: torch.device


@lru_cache
def get_clip_components(model_name: str, pretrained: str) -> ClipComponents:
    """Load and cache a CLIP encoder."""
    device = _device()
    model, _, preprocess = open_clip.create_model_and_transforms(
        model_name, pretrained=pretrained
    )
    model.to(device)
    model.eval()
    tokenizer = open_clip.get_tokenizer(model_name)
    logger.info("Loaded CLIP model %s (%s) on %s", model_name, pretrained, device)
    return ClipComponents(model=model, preprocess=preprocess, tokenizer=tokenizer, device=device)


def encode_image_with_clip(image: Image.Image, model_name: str, pretrained: str) -> list[float]:
    """Compute a normalized CLIP embedding for an image."""
    components = get_clip_components(model_name, pretrained)
    image_tensor = components.preprocess(image).unsqueeze(0).to(components.device)
    with torch.no_grad():
        features = components.model.encode_image(image_tensor)
        features = features / features.norm(dim=-1, keepdim=True)
    return features.squeeze(0).detach().cpu().tolist()


@dataclass
class FaceDetection:
    bbox: list[float]
    confidence: float
    embedding: list[float]


@dataclass
class FaceModels:
    detector: MTCNN
    embedder: InceptionResnetV1
    device: torch.device


@lru_cache
def get_face_models(min_confidence: float) -> FaceModels:
    """Load and cache face detection/recognition models."""
    device = _device()
    detector = MTCNN(
        image_size=160,
        margin=14,
        min_face_size=40,
        thresholds=[min_confidence, min_confidence, min_confidence],
        keep_all=True,
        device=device,
    )
    embedder = InceptionResnetV1(pretrained="vggface2").eval().to(device)
    logger.info("Loaded face models on %s (threshold=%s)", device, min_confidence)
    return FaceModels(detector=detector, embedder=embedder, device=device)


def detect_faces(image: Image.Image, min_confidence: float = 0.9) -> list[FaceDetection]:
    """Run face detection and embed each detected face."""
    models = get_face_models(min_confidence)
    # Ensure RGB for detector
    rgb_image = image.convert("RGB")

    boxes, probs = models.detector.detect(rgb_image)
    if boxes is None or probs is None:
        return []

    faces: list[FaceDetection] = []
    # Extract aligned face crops for embedding
    aligned = models.detector.extract(rgb_image, boxes, save_path=None)
    if aligned is None:
        return []

    with torch.no_grad():
        embeddings = models.embedder(aligned.to(models.device))
        embeddings = embeddings / embeddings.norm(dim=1, keepdim=True)

    for box, prob, embedding in zip(boxes, probs, embeddings):
        if prob is None or float(prob) < min_confidence:
            continue
        bbox_list = [float(value) for value in box.tolist()]
        embedding_list = [float(x) for x in embedding.cpu().tolist()]
        faces.append(
            FaceDetection(
                bbox=bbox_list,
                confidence=float(prob),
                embedding=embedding_list,
            )
        )
    return faces
