"""JSON serialization and Amazon S3 storage for validated snapshots."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Protocol

from logger import get_logger
from models import Snapshot, SnapshotValidationError

LOGGER = get_logger(__name__)


class SnapshotStorageError(RuntimeError):
    """Raised when a validated snapshot cannot be stored."""


class S3Client(Protocol):
    """Minimal S3 client contract used by the storage adapter."""

    def put_object(self, **kwargs: Any) -> Any:
        """Upload an object to S3."""


def serialize_snapshot(snapshot: Snapshot) -> str:
    """Serialize a validated snapshot into deterministic UTF-8 JSON."""
    snapshot.validate()
    try:
        return json.dumps(
            snapshot.to_dict(),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ) + "\n"
    except (TypeError, ValueError) as exc:
        raise SnapshotValidationError("Snapshot could not be serialized as JSON") from exc


def build_snapshot_key(snapshot: Snapshot) -> str:
    """Build the required date-partitioned immutable snapshot key."""
    generated_at = snapshot.generated_datetime()
    timestamp = generated_at.strftime("%Y%m%dT%H%M%S%fZ")
    return (
        f"snapshots/{generated_at:%Y/%m/%d}/"
        f"snapshot-{timestamp}.json"
    )


class SnapshotStorage:
    """Upload validated snapshots to an externally provisioned S3 bucket."""

    def __init__(
        self,
        bucket: str,
        region: str,
        s3_client: S3Client | None = None,
    ) -> None:
        if not bucket.strip():
            raise SnapshotStorageError("S3 bucket name must not be empty")
        if not region.strip():
            raise SnapshotStorageError("AWS Region must not be empty")

        self._bucket = bucket
        self._region = region
        self._s3_client = s3_client or self._create_s3_client(region)

    @property
    def client(self) -> S3Client:
        """Return the configured client for cohesive snapshot/report operations."""
        return self._s3_client

    @staticmethod
    def _create_s3_client(region: str) -> S3Client:
        try:
            import boto3
        except ModuleNotFoundError as exc:
            raise SnapshotStorageError(
                "boto3 is required when an S3 client is not injected"
            ) from exc
        return boto3.client("s3", region_name=region)

    def upload(self, snapshot: Snapshot) -> str:
        """Serialize and conditionally upload a snapshot, returning its S3 key."""
        payload = serialize_snapshot(snapshot).encode("utf-8")
        key = build_snapshot_key(snapshot)
        try:
            self._s3_client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=payload,
                ContentType="application/json",
                ServerSideEncryption="AES256",
                IfNoneMatch="*",
            )
        except Exception as exc:
            LOGGER.error(
                "Snapshot upload failed operation=put_object key=%s error_type=%s",
                key,
                type(exc).__name__,
            )
            raise SnapshotStorageError("Snapshot upload failed") from exc

        LOGGER.info(
            "Snapshot upload successful key=%s bytes=%d region=%s",
            key,
            len(payload),
            self._region,
        )
        return key
