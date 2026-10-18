"""MinIO client construction shared by the VOD indexer and playback proxy."""
from __future__ import annotations

from minio import Minio

from .config import Settings


def client(settings: Settings) -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,
    )
