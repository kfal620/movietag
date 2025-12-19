"""Lightweight film matching using stored frame embeddings."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
from sqlalchemy.orm import Session

from app.models import Frame

logger = logging.getLogger(__name__)


def _normalize_vector(values: Iterable[float]) -> np.ndarray | None:
    try:
        vector = np.asarray(list(values), dtype=float)
    except Exception:
        logger.warning("Could not convert embedding values to vector")
        return None

    if vector.size == 0:
        return None

    norm = np.linalg.norm(vector)
    if norm == 0:
        return None
    return vector / norm


def _load_embedding(raw: str | Iterable[float] | None) -> np.ndarray | None:
    if raw is None:
        return None

    try:
        payload: Any = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        logger.warning("Failed to parse embedding payload for matcher")
        return None
    return _normalize_vector(payload or [])


@dataclass
class MatchCandidate:
    frame_id: int
    movie_id: int
    similarity: float
    captured_at: str | None


class FilmMatcher:
    """Compute similarity against existing frame embeddings to guess a movie."""

    def __init__(self, session: Session, *, min_confidence: float = 0.2) -> None:
        self.session = session
        self.min_confidence = min_confidence

    def _candidate_rows(self) -> list[tuple[int, int, str | None, Any]]:
        return (
            self.session.query(
                Frame.id,
                Frame.movie_id,
                Frame.embedding,
                Frame.captured_at,
            )
            .filter(Frame.movie_id.isnot(None), Frame.embedding.isnot(None))
            .all()
        )

    def _compute_similarity(
        self, target: np.ndarray, candidate_embedding: np.ndarray
    ) -> float:
        similarity = float(np.dot(target, candidate_embedding))
        # Scale cosine similarity (-1..1) into a confidence-like 0..1 range
        confidence = max(0.0, min(1.0, (similarity + 1) / 2))
        return round(confidence, 4)

    def match_movie(self, embedding: Iterable[float] | None) -> dict[str, Any] | None:
        target_vector = _normalize_vector(embedding or [])
        if target_vector is None:
            return None

        candidates: list[MatchCandidate] = []
        for frame_id, movie_id, raw_embedding, captured_at in self._candidate_rows():
            candidate_vector = _load_embedding(raw_embedding)
            if candidate_vector is None:
                continue
            similarity = self._compute_similarity(target_vector, candidate_vector)
            candidates.append(
                MatchCandidate(
                    frame_id=frame_id,
                    movie_id=movie_id,
                    similarity=similarity,
                    captured_at=captured_at.isoformat() if captured_at else None,
                )
            )

        if not candidates:
            return None

        # Consolidate by movie to avoid one prolific movie dominating matches
        best_by_movie: dict[int, MatchCandidate] = {}
        for candidate in candidates:
            existing = best_by_movie.get(candidate.movie_id)
            if existing is None or candidate.similarity > existing.similarity:
                best_by_movie[candidate.movie_id] = candidate

        best_match = max(best_by_movie.values(), key=lambda candidate: candidate.similarity)
        if best_match.similarity < self.min_confidence:
            return None

        return {
            "movie_id": best_match.movie_id,
            "confidence": best_match.similarity,
            "timestamp": best_match.captured_at,
            "shot_id": str(best_match.frame_id),
        }
