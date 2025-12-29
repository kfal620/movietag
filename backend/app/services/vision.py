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
import json

import numpy as np
import redis
import requests
from PIL import Image

logger = logging.getLogger(__name__)

MODEL_STATUS_KEY = "movietag:model_status"


def _get_redis_client():
    """Get Redis client for storing model status."""
    try:
        from app.core.settings import get_settings
        settings = get_settings()
        broker_url = settings.celery_broker_url
        if broker_url.startswith("redis://"):
            return redis.from_url(broker_url)
    except Exception:
        pass
    # Fallback to localhost
    return redis.Redis(host="localhost", port=6379, db=0)


def _get_model_status(model_id: str) -> dict[str, Any]:
    """Get model status from Redis."""
    client = _get_redis_client()
    try:
        data = client.hget(MODEL_STATUS_KEY, model_id)
        if data:
            return json.loads(data)
    except Exception:
        pass
    return {
        "last_loaded_at": None,
        "error": None,
        "device": None,
        "version": None,
        "model_name": None,
    }


def _set_model_status(model_id: str, status: dict[str, Any]) -> None:
    """Set model status in Redis."""
    client = _get_redis_client()
    try:
        client.hset(MODEL_STATUS_KEY, model_id, json.dumps(status))
    except Exception as exc:
        logger.warning("Failed to set model status in Redis: %s", exc)


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _record_model_load(model_id: str, device: str | None, version: str | None, model_name: str | None = None) -> None:
    status = _get_model_status(model_id)
    status.update(
        {
            "last_loaded_at": datetime.now(timezone.utc).isoformat(),
            "error": None,
            "device": device,
            "version": version,
            "model_name": model_name,
        }
    )
    _set_model_status(model_id, status)


def _record_model_error(model_id: str, message: str) -> None:
    status = _get_model_status(model_id)
    status.update({"error": message})
    _set_model_status(model_id, status)


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
    _record_model_load("clip", str(device), open_clip_version, model_name=f"{model_name} ({pretrained})")
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
    _record_model_load("face", str(device), facenet_version, model_name="MTCNN + InceptionResnetV1 (vggface2)")
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
    debug_info: dict[str, Any] | None = None


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



SCENE_ATTRIBUTE_PROMPTS = {
    "time_of_day": {"day": "a photo taken during the day", "night": "a photo taken at night"},
    "lighting": {
        "hard_light": "hard light",
        "soft_light": "soft light",
        "top_light": "top light",
        "silhouette": "silhouette",
        "high_contrast": "high contrast",
        "low_contrast": "low contrast",
        "side_light": "side light",
        "front_light": "front light",
    },
    "interior_exterior": {"interior": "interior view", "exterior": "exterior view"},
    "environment": {
        "urban": "urban environment",
        "natural": "natural environment",
        "underwater": "underwater scene",
        "space": "outer space",
    },
    "emotion": {
        "calm": "calm atmosphere",
        "intense": "intense atmosphere",
        "joyful": "joyful atmosphere",
        "melancholic": "melancholic atmosphere",
    },
    "composition": {
        "rule_of_thirds": "composition following rule of thirds",
        "centered": "centered composition",
        "symmetrical": "symmetrical composition",
        "panoramic": "panoramic view",
    },
    "color_temperature": {
        "warm": "warm color temperature",
        "cool": "cool color temperature",
        "neutral": "neutral color temperature",
    },
}


def _get_attribute_prototypes(session: Any, attribute: str) -> dict[str, Any]:
    """Fetch verified frame embeddings for an attribute and compute class centroids."""
    if not session:
        return {}
    
    # Avoid circular imports
    try:
        from app.models import Frame, SceneAttribute
    except ImportError:
        return {}

    # Query verified attributes
    rows = (
        session.query(SceneAttribute.value, Frame.embedding)
        .join(Frame, Frame.id == SceneAttribute.frame_id)
        .filter(
            SceneAttribute.attribute == attribute,
            SceneAttribute.is_verified == True,
            Frame.embedding.isnot(None),
        )
        .limit(100)  # Limit to avoid slow queries, maybe prioritize recent?
        .all()
    )

    if not rows:
        return {}

    torch = _lazy_import_torch()
    clusters: dict[str, list[list[float]]] = {}
    
    for value, embedding_json in rows:
        try:
            embedding = json.loads(embedding_json)
            if not embedding:
                continue
            if value not in clusters:
                clusters[value] = []
            clusters[value].append(embedding)
        except Exception:
            continue
            
    # Compute centroids
    prototypes: dict[str, Any] = {}
    for value, vectors in clusters.items():
        if not vectors:
            continue
        tensor = torch.tensor(vectors)
        centroid = tensor.mean(dim=0)
        centroid = centroid / centroid.norm(dim=-1, keepdim=True)
        prototypes[value] = (centroid, len(vectors))

    return prototypes



def classify_attributes_with_clip(image: Image.Image, session: Any | None = None) -> tuple[list[SceneAttributePrediction], list[float]]:
    """Run zero-shot classification using the local CLIP model."""
    torch = _lazy_import_torch()
    # Use default model settings
    settings = None
    try:
        from app.core.settings import get_settings
        settings = get_settings()
    except Exception:
        pass
    
    model_name = settings.clip_model_name if settings else "ViT-B-32"
    pretrained = settings.clip_pretrained if settings else "openai"
    components = get_clip_components(model_name, pretrained)

    image_tensor = components.preprocess(image).unsqueeze(0).to(components.device)
    with torch.no_grad():
        image_features = components.model.encode_image(image_tensor)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        # Convert to list for return
        embedding_list = image_features.squeeze(0).cpu().tolist()

    predictions: list[SceneAttributePrediction] = []

    # 2. Iterate over attributes and encode text prompts
    # Note: In a high-throughput system, we would cache these text embeddings.
    for attribute, options in SCENE_ATTRIBUTE_PROMPTS.items():
        labels = list(options.keys())
        prompts = list(options.values())
        
        text_tokens = components.tokenizer(prompts).to(components.device)
        with torch.no_grad():
            text_features = components.model.encode_text(text_tokens)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            
            # shape: (1, embed_dim) @ (num_classes, embed_dim).T -> (1, num_classes)
            similarity = (image_features @ text_features.T).squeeze(0)
            
            # Prototype Integration
            proto_map = _get_attribute_prototypes(session, attribute)
            
            # Store debug info for each label
            label_scores = []
            
            for i, label in enumerate(labels):
                clip_score = similarity[i].item()
                proto_score = None
                proto_count = 0
                
                if label in proto_map:
                    proto_vec, count = proto_map[label]
                    proto_vec = proto_vec.to(components.device)
                    # image_features (1, dim), proto_vec (dim)
                    proto_sim = (image_features @ proto_vec.unsqueeze(0).T).squeeze(0).item()
                    
                    # Weighting: 60% text (general knowledge), 40% specific examples
                    new_score = 0.6 * clip_score + 0.4 * proto_sim
                    similarity[i] = new_score
                    
                    proto_score = proto_sim
                    proto_count = count
                
                label_scores.append({
                    "label": label,
                    "clip_score": clip_score,
                    "prototype_score": proto_score,
                    "prototype_count": proto_count,
                    "final_score": similarity[i].item()
                })

            # Handle multi-label for 'lighting'
            if attribute == "lighting":
                # Multi-label strategy: select top K or threshold?
                # Let's verify matches > 0.85 * best_score to capture close seconds
                best_score = float(similarity.max())
                threshold = max(0.2, best_score * 0.85)
                
                # Sort indices by score descending
                sorted_indices = similarity.argsort(descending=True)
                for idx in sorted_indices:
                    score = float(similarity[idx])
                    if score < threshold:
                        break
                    
                    # Find debug info for this label
                    lbl = labels[idx]
                    d_info = next((x for x in label_scores if x["label"] == lbl), None)
                    
                    predictions.append(
                        SceneAttributePrediction(
                            attribute=attribute,
                            value=lbl,
                            confidence=round(score, 3),
                            debug_info={"selected": d_info, "candidates": label_scores}
                        )
                    )
            else:
                # Single-label: argmax
                best_idx = similarity.argmax().item()
                best_score = float(similarity[best_idx])
                
                lbl = labels[best_idx]
                d_info = next((x for x in label_scores if x["label"] == lbl), None)
                
                predictions.append(
                    SceneAttributePrediction(
                        attribute=attribute,
                        value=lbl,
                        confidence=round(best_score, 3),
                        debug_info={"selected": d_info, "candidates": label_scores}
                    )
                )

    # 3. Add dominant colors (kept as it is distinct from semantic attributes but useful)
    predictions.extend(_dominant_colors(image, k=3))
    
    return predictions, embedding_list


def predict_scene_attributes(
    image: Image.Image, service_url: str | None = None, session: Any | None = None
) -> tuple[list[SceneAttributePrediction], list[float] | None]:
    """Run production scene classifiers using CLIP zero-shot locally or via service."""
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
                            debug_info=entry.get("debug_info"),
                        )
                    )
                except Exception:
                    continue
            if predictions:
                # Service API currently doesn't return embedding, so None
                return predictions, None
        except Exception:
            logger.exception("Scene attribute service failed, falling back to local CLIP")

    # Local Fallback (now using CLIP instead of heuristics)
    try:
        return classify_attributes_with_clip(image, session=session)
    except Exception:
        logger.exception("Local CLIP classification failed")
        return [], None



def get_vision_model_status() -> list[dict[str, Any]]:
    device = _resolve_device_name()

    models: list[dict[str, Any]] = []
    clip_meta = _get_model_status("clip")
    models.append(
        {
            "id": "clip",
            "name": clip_meta.get("model_name") or "CLIP image encoder",
            "available": _module_available("open_clip"),
            "loaded": bool(clip_meta.get("last_loaded_at")) and not clip_meta.get("error"),
            "device": clip_meta.get("device") or device,
            "version": clip_meta.get("version"),
            "last_loaded_at": clip_meta.get("last_loaded_at"),
            "error": clip_meta.get("error"),
        }
    )
    face_meta = _get_model_status("face")
    models.append(
        {
            "id": "face",
            "name": face_meta.get("model_name") or "Face detection",
            "available": _module_available("facenet_pytorch"),
            "loaded": bool(face_meta.get("last_loaded_at")) and not face_meta.get("error"),
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
