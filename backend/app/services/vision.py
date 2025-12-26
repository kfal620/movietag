"""Shared utilities for production-grade vision models.

This module centralizes heavyweight model loading (CLIP for embeddings and
FaceNet/MTCNN for face detection) so Celery tasks can reuse a single set of
weights instead of re-downloading them on every invocation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
import importlib.metadata
import importlib.util
from typing import Any, Iterable
import io

import numpy as np
import requests
from PIL import Image

logger = logging.getLogger(__name__)

MODEL_STATUS: dict[str, dict[str, Any]] = {
    "clip": {"last_loaded_at": None, "error": None, "device": None, "version": None},
    "face": {"last_loaded_at": None, "error": None, "device": None, "version": None},
}


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _record_model_load(model_id: str, device: str | None, version: str | None) -> None:
    MODEL_STATUS.setdefault(model_id, {})
    MODEL_STATUS[model_id].update(
        {
            "last_loaded_at": datetime.now(timezone.utc).isoformat(),
            "error": None,
            "device": device,
            "version": version,
        }
    )


def _record_model_error(model_id: str, message: str) -> None:
    MODEL_STATUS.setdefault(model_id, {})
    MODEL_STATUS[model_id].update({"error": message})


def _resolve_device_name() -> str:
    if not _module_available("torch"):
        return "cpu"
    torch = _lazy_import_torch()
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _lazy_import_torch():
    import torch  # type: ignore

    return torch


def _device():
    torch = _lazy_import_torch()
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


@dataclass
class ClipComponents:
    model: Any
    preprocess: callable
    tokenizer: callable
    device: Any


@lru_cache
def get_clip_components(model_name: str, pretrained: str) -> ClipComponents:
    """Load and cache a CLIP encoder."""
    import open_clip  # type: ignore

    device = _device()
    model, _, preprocess = open_clip.create_model_and_transforms(
        model_name, pretrained=pretrained
    )
    model.to(device)
    model.eval()
    tokenizer = open_clip.get_tokenizer(model_name)
    logger.info("Loaded CLIP model %s (%s) on %s", model_name, pretrained, device)
    try:
        open_clip_version = importlib.metadata.version("open_clip_torch")
    except importlib.metadata.PackageNotFoundError:
        open_clip_version = None
    _record_model_load("clip", str(device), open_clip_version)
    return ClipComponents(model=model, preprocess=preprocess, tokenizer=tokenizer, device=device)


def encode_image_with_clip(image: Image.Image, model_name: str, pretrained: str) -> list[float]:
    """Compute a normalized CLIP embedding for an image."""
    torch = _lazy_import_torch()
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
    emotion: str | None = None
    pose_yaw: float | None = None
    pose_pitch: float | None = None
    pose_roll: float | None = None


@dataclass
class FaceModels:
    detector: Any
    embedder: Any
    device: Any


@lru_cache
def get_face_models(min_confidence: float) -> FaceModels:
    """Load and cache face detection/recognition models."""
    from facenet_pytorch import InceptionResnetV1, MTCNN  # type: ignore

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
    try:
        facenet_version = importlib.metadata.version("facenet-pytorch")
    except importlib.metadata.PackageNotFoundError:
        facenet_version = None
    _record_model_load("face", str(device), facenet_version)
    return FaceModels(detector=detector, embedder=embedder, device=device)


def _detect_faces_with_service(image: Image.Image, service_url: str, timeout: int = 20) -> list[FaceDetection]:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    response = requests.post(
        service_url,
        files={"file": ("frame.png", buffer.getvalue(), "image/png")},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    faces: list[FaceDetection] = []
    for face in payload.get("faces", []):
        try:
            bbox = [float(value) for value in face["bbox"]]
            faces.append(
                FaceDetection(
                    bbox=bbox,
                    confidence=float(face.get("confidence", 0.0)),
                    embedding=[float(x) for x in face.get("embedding", [])],
                    emotion=face.get("emotion"),
                    pose_yaw=float(face.get("pose_yaw")) if face.get("pose_yaw") is not None else None,
                    pose_pitch=float(face.get("pose_pitch")) if face.get("pose_pitch") is not None else None,
                    pose_roll=float(face.get("pose_roll")) if face.get("pose_roll") is not None else None,
                )
            )
        except Exception:
            continue
    return faces


def detect_faces(
    image: Image.Image,
    min_confidence: float = 0.9,
    service_url: str | None = None,
) -> list[FaceDetection]:
    """Run face detection and embed each detected face."""
    if service_url:
        try:
            predictions = _detect_faces_with_service(image, service_url)
            filtered = [face for face in predictions if face.confidence >= min_confidence]
            if filtered:
                return filtered
        except Exception:
            logger.exception("Remote face analytics failed, using on-device models")

    torch = _lazy_import_torch()
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

    width, height = rgb_image.size

    def _pose_from_bbox(bbox: list[float]) -> tuple[float, float, float]:
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        yaw = ((cx / max(width, 1)) - 0.5) * 45  # degrees
        pitch = ((cy / max(height, 1)) - 0.5) * 30
        roll = (x2 - x1) / max(width, 1) * 10 - 5
        return round(yaw, 3), round(pitch, 3), round(roll, 3)

    def _emotion_from_intensity(bbox: list[float]) -> str:
        _, y1, _, y2 = bbox
        vertical_span = (y2 - y1) / max(height, 1)
        if vertical_span > 0.35:
            return "engaged"
        if vertical_span > 0.25:
            return "focused"
        return "neutral"

    for box, prob, embedding in zip(boxes, probs, embeddings):
        if prob is None or float(prob) < min_confidence:
            continue
        bbox_list = [float(value) for value in box.tolist()]
        embedding_list = [float(x) for x in embedding.cpu().tolist()]
        yaw, pitch, roll = _pose_from_bbox(bbox_list)
        faces.append(
            FaceDetection(
                bbox=bbox_list,
                confidence=float(prob),
                embedding=embedding_list,
                emotion=_emotion_from_intensity(bbox_list),
                pose_yaw=yaw,
                pose_pitch=pitch,
                pose_roll=roll,
            )
        )
    return faces


@dataclass
class SceneAttributePrediction:
    attribute: str
    value: str
    confidence: float


def _normalize(vector: Iterable[float]) -> np.ndarray:
    arr = np.asarray(list(vector), dtype=float)
    norm = np.linalg.norm(arr) or 1.0
    return arr / norm


def cosine_similarity(a: Iterable[float], b: Iterable[float]) -> float:
    lhs = _normalize(a)
    rhs = _normalize(b)
    return float(np.dot(lhs, rhs))


def encode_face_image(image: Image.Image) -> list[float]:
    """Encode a cropped face image using the shared embedder."""
    torch = _lazy_import_torch()
    models = get_face_models(0.5)
    rgb_image = image.convert("RGB")
    boxes, probs = models.detector.detect(rgb_image)
    if boxes is not None and probs is not None and len(boxes):
        aligned = models.detector.extract(rgb_image, boxes, save_path=None)
    else:
        aligned = None

    if aligned is None:
        tensor = models.detector._resize(rgb_image)  # type: ignore[attr-defined]
        if tensor.dim() == 3:
            tensor = tensor.unsqueeze(0)
    else:
        tensor = aligned

    tensor = tensor.to(models.device)
    with torch.no_grad():
        embedding = models.embedder(tensor)
        embedding = embedding / embedding.norm(dim=1, keepdim=True)
    return [float(x) for x in embedding.squeeze(0).cpu().tolist()]


def _dominant_colors(image: Image.Image, k: int = 3) -> list[SceneAttributePrediction]:
    small = image.convert("RGB").resize((64, 64))
    pixels = np.array(small).reshape(-1, 3)
    unique, counts = np.unique(pixels, axis=0, return_counts=True)
    total = counts.sum() or 1
    sorted_idx = np.argsort(counts)[::-1][:k]
    predictions: list[SceneAttributePrediction] = []
    for rank, idx in enumerate(sorted_idx):
        rgb = unique[idx]
        confidence = float(counts[idx] / total)
        hex_color = "#%02x%02x%02x" % tuple(int(c) for c in rgb.tolist())
        predictions.append(
            SceneAttributePrediction(
                attribute="dominant_color",
                value=f"{hex_color}:{rank}",
                confidence=round(confidence, 4),
            )
        )
    return predictions


def predict_scene_attributes(
    image: Image.Image, service_url: str | None = None
) -> list[SceneAttributePrediction]:
    """Run production scene classifiers or fall back to lightweight heuristics."""
    if service_url:
        try:
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            buffer.seek(0)
            response = requests.post(
                service_url,
                files={"file": ("frame.png", buffer.getvalue(), "image/png")},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            predictions: list[SceneAttributePrediction] = []
            for entry in payload.get("attributes", []):
                try:
                    predictions.append(
                        SceneAttributePrediction(
                            attribute=entry["attribute"],
                            value=entry["value"],
                            confidence=float(entry.get("confidence", 0.0)),
                        )
                    )
                except Exception:
                    continue
            if predictions:
                return predictions
        except Exception:
            logger.exception("Scene attribute service failed, using heuristics instead")

    rgb = image.convert("RGB")
    arr = np.asarray(rgb)
    brightness = float(arr.mean() / 255)
    saturation = float(np.std(arr) / 255)
    height, width = arr.shape[:2]
    aspect_ratio = width / max(1, height)

    def _score(center: float, spread: float = 0.25) -> float:
        return max(0.05, 1.0 - abs(brightness - center) / spread)

    time_of_day = "night" if brightness < 0.42 else "day"
    lighting = "low_key" if brightness < 0.35 else "high_key"
    environment = "interior" if saturation < 0.18 else "exterior"
    if brightness < 0.3 and saturation < 0.12:
        environment = "underwater"
    vehicle_presence = "vehicle" if (np.mean(arr[:, :, 1]) / 255) > 0.4 and aspect_ratio > 1.2 else "no_vehicle"
    if aspect_ratio > 2.1:
        composition_tag = "panoramic"
    elif aspect_ratio < 0.8:
        composition_tag = "portrait_frame"
    else:
        composition_tag = "balanced_frame"

    cool_strength = float(np.mean(arr[:, :, 2]) / 255)
    warm_strength = float(np.mean(arr[:, :, 0]) / 255)
    emotion = "calm" if cool_strength >= warm_strength else "intense"
    location_type = "urban" if saturation > 0.25 else "natural"
    if environment == "interior":
        location_type = "interior"
    composition_secondary = "rule_of_thirds" if saturation > 0.1 else "centered"

    predictions: list[SceneAttributePrediction] = [
        SceneAttributePrediction("time_of_day", time_of_day, round(_score(0.55), 3)),
        SceneAttributePrediction("lighting", lighting, round(_score(0.5), 3)),
        SceneAttributePrediction("environment", environment, round(0.6 + 0.4 * saturation, 3)),
        SceneAttributePrediction("location_type", location_type, round(0.55 + 0.35 * saturation, 3)),
        SceneAttributePrediction("composition", composition_tag, 0.62),
        SceneAttributePrediction("composition", composition_secondary, 0.58),
        SceneAttributePrediction("emotion", emotion, round(0.5 + 0.4 * brightness, 3)),
        SceneAttributePrediction("vehicle_presence", vehicle_presence, round(0.45 + 0.45 * saturation, 3)),
        SceneAttributePrediction(
            "color_temperature",
            "warm" if warm_strength >= cool_strength else "cool",
            round(abs(warm_strength - cool_strength) + 0.5, 3),
        ),
        SceneAttributePrediction(
            "saturation_level",
            "rich" if saturation > 0.25 else "muted",
            round(0.5 + 0.5 * saturation, 3),
        ),
        SceneAttributePrediction(
            "lighting_style",
            "backlit" if brightness < 0.35 and saturation > 0.25 else lighting,
            round(0.55 + 0.35 * abs(0.5 - brightness), 3),
        ),
    ]
    predictions.extend(_dominant_colors(image, k=3))
    return predictions


def get_vision_model_status() -> list[dict[str, Any]]:
    clip_loaded = get_clip_components.cache_info().currsize > 0
    face_loaded = get_face_models.cache_info().currsize > 0
    device = _resolve_device_name()

    models: list[dict[str, Any]] = []
    clip_meta = MODEL_STATUS.get("clip", {})
    models.append(
        {
            "id": "clip",
            "name": "CLIP image encoder",
            "available": _module_available("open_clip"),
            "loaded": clip_loaded,
            "device": clip_meta.get("device") or device,
            "version": clip_meta.get("version"),
            "last_loaded_at": clip_meta.get("last_loaded_at"),
            "error": clip_meta.get("error"),
        }
    )
    face_meta = MODEL_STATUS.get("face", {})
    models.append(
        {
            "id": "face",
            "name": "Face detection",
            "available": _module_available("facenet_pytorch"),
            "loaded": face_loaded,
            "device": face_meta.get("device") or device,
            "version": face_meta.get("version"),
            "last_loaded_at": face_meta.get("last_loaded_at"),
            "error": face_meta.get("error"),
        }
    )
    return models


def warmup_vision_models() -> None:
    """Trigger light-weight model loading to populate cache entries."""
    settings = None
    try:
        from app.core.settings import get_settings  # local import to avoid cycles

        settings = get_settings()
    except Exception:
        settings = None

    try:
        if settings:
            get_clip_components(settings.clip_model_name, settings.clip_pretrained)
        else:
            get_clip_components("ViT-B-32", "openai")
    except Exception as exc:
        logger.exception("CLIP warmup failed")
        _record_model_error("clip", str(exc))

    try:
        min_confidence = settings.face_min_confidence if settings else 0.9
        get_face_models(min_confidence)
    except Exception as exc:
        logger.exception("Face model warmup failed")
        _record_model_error("face", str(exc))
