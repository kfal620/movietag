"""Object storage helpers for generating browser-safe URLs."""

from __future__ import annotations

import logging
from typing import Tuple

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.settings import get_settings

logger = logging.getLogger(__name__)


def _bucket_and_key(storage_uri: str, default_bucket: str | None) -> Tuple[str, str] | None:
    if not storage_uri:
        return None

    if storage_uri.startswith("s3://"):
        remainder = storage_uri.removeprefix("s3://")
        if "/" not in remainder:
            return None
        bucket, key = remainder.split("/", 1)
    else:
        bucket = default_bucket
        key = storage_uri.lstrip("/")

    if not bucket or not key:
        return None

    return bucket, key


def _build_s3_client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint_url,
        aws_access_key_id=settings.storage_access_key,
        aws_secret_access_key=settings.storage_secret_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def generate_presigned_url(storage_uri: str | None, *, expires_in: int = 600) -> str | None:
    """Return a short-lived URL for an object stored in S3/MinIO.

    The helper is resilient to missing configuration and will return ``None`` when
    it cannot safely build a signed URL.
    """

    if not storage_uri:
        return None

    settings = get_settings()
    bucket_key = _bucket_and_key(storage_uri, settings.storage_frames_bucket)
    if bucket_key is None:
        return None

    if not settings.storage_access_key or not settings.storage_secret_key:
        logger.debug("Storage credentials not configured; skipping signed URL generation")
        return None

    bucket, key = bucket_key

    try:
        client = _build_s3_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key, "ResponseContentDisposition": "inline"},
            ExpiresIn=expires_in,
        )
    except (BotoCoreError, ClientError) as exc:
        logger.warning("Could not generate signed URL for %s: %s", storage_uri, exc)
        return None
    except Exception:  # pragma: no cover - safety net for unexpected boto errors
        logger.exception("Unexpected error generating signed URL for %s", storage_uri)
        return None


def resolve_frame_signed_url(frame, *, expires_in: int = 600) -> str | None:
    """Return the best available signed URL for a frame preview."""

    if getattr(frame, "signed_url", None):
        return frame.signed_url

    return generate_presigned_url(getattr(frame, "storage_uri", None), expires_in=expires_in)


def upload_fileobj(file_obj, *, bucket: str | None = None, key: str | None = None, content_type: str | None = None) -> str:
    """Upload a file-like object to storage and return an ``s3://`` URI."""

    settings = get_settings()
    resolved_bucket = bucket or settings.storage_frames_bucket
    if not resolved_bucket:
        raise ValueError("A target bucket is required to upload files")

    target_key = key
    if not target_key:
        import uuid

        target_key = f"uploads/{uuid.uuid4().hex}"

    extra_args = {"ContentType": content_type} if content_type else None
    client = _build_s3_client()
    client.upload_fileobj(file_obj, resolved_bucket, target_key, ExtraArgs=extra_args or {})
    return f"s3://{resolved_bucket}/{target_key}"


def download_to_path(storage_uri: str, destination: str) -> None:
    """Download an object to a specific path."""

    bucket_key = _bucket_and_key(storage_uri, get_settings().storage_frames_bucket)
    if bucket_key is None:
        raise ValueError(f"Unsupported storage URI: {storage_uri}")

    bucket, key = bucket_key
    client = _build_s3_client()
    client.download_file(bucket, key, destination)
