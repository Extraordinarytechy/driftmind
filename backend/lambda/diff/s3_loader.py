"""Load the latest previous canonical snapshot from Amazon S3."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from logger import get_logger
from models import Snapshot

from .loader import parse_snapshot_json

LOGGER = get_logger(__name__)
_SNAPSHOT_KEY_PATTERN = re.compile(
    r"^snapshots/(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})/"
    r"snapshot-(?P<timestamp>\d{8}T\d{12}Z)\.json$"
)


class SnapshotHistoryError(RuntimeError):
    """Raised when snapshot history cannot be listed or loaded safely."""


class S3SnapshotHistoryClient(Protocol):
    """S3 operations required for automatic baseline discovery."""

    def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]:
        """List snapshot objects."""

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        """Get one snapshot object."""


@dataclass(frozen=True, slots=True)
class LoadedSnapshot:
    """A validated historical snapshot and its S3 key."""

    key: str
    snapshot: Snapshot


def _key_timestamp(key: str) -> datetime | None:
    match = _SNAPSHOT_KEY_PATTERN.fullmatch(key)
    if match is None:
        return None
    try:
        timestamp = datetime.strptime(
            match.group("timestamp"), "%Y%m%dT%H%M%S%fZ"
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    if (
        match.group("year") != timestamp.strftime("%Y")
        or match.group("month") != timestamp.strftime("%m")
        or match.group("day") != timestamp.strftime("%d")
    ):
        return None
    return timestamp


class S3SnapshotHistory:
    """Discover and load the most recent snapshot before the current run."""

    def __init__(self, bucket: str, s3_client: S3SnapshotHistoryClient) -> None:
        if not isinstance(bucket, str) or not bucket.strip():
            raise SnapshotHistoryError("Snapshot history bucket must not be empty")
        self._bucket = bucket
        self._s3_client = s3_client

    def _list_keys(self) -> tuple[str, ...]:
        keys: list[str] = []
        request: dict[str, Any] = {
            "Bucket": self._bucket,
            "Prefix": "snapshots/",
        }
        try:
            while True:
                response = self._s3_client.list_objects_v2(**request)
                if not isinstance(response, dict):
                    raise SnapshotHistoryError("S3 snapshot listing response is invalid")
                contents = response.get("Contents", [])
                if not isinstance(contents, list):
                    raise SnapshotHistoryError("S3 snapshot listing contents are invalid")
                for item in contents:
                    if isinstance(item, dict) and isinstance(item.get("Key"), str):
                        keys.append(item["Key"])
                if not response.get("IsTruncated", False):
                    break
                token = response.get("NextContinuationToken")
                if not isinstance(token, str) or not token:
                    raise SnapshotHistoryError(
                        "S3 snapshot listing pagination token is missing"
                    )
                request["ContinuationToken"] = token
        except SnapshotHistoryError:
            raise
        except Exception as exc:
            LOGGER.error(
                "Snapshot history listing failed operation=list_objects_v2 error_type=%s",
                type(exc).__name__,
            )
            raise SnapshotHistoryError("Snapshot history listing failed") from exc
        return tuple(keys)

    def load_latest_before(self, current_key: str) -> LoadedSnapshot | None:
        """Return the latest canonical snapshot older than current_key."""
        current_timestamp = _key_timestamp(current_key)
        if current_timestamp is None:
            raise SnapshotHistoryError("Current snapshot key is not canonical")

        candidates = [
            (timestamp, key)
            for key in self._list_keys()
            if (timestamp := _key_timestamp(key)) is not None
            and timestamp < current_timestamp
        ]
        if not candidates:
            return None
        _, key = max(candidates, key=lambda item: (item[0], item[1]))

        try:
            response = self._s3_client.get_object(Bucket=self._bucket, Key=key)
            if not isinstance(response, dict) or "Body" not in response:
                raise SnapshotHistoryError("S3 snapshot object response is invalid")
            body = response["Body"]
            payload = body.read() if hasattr(body, "read") else body
            snapshot = parse_snapshot_json(payload)
        except SnapshotHistoryError:
            raise
        except Exception as exc:
            LOGGER.error(
                "Previous snapshot loading failed operation=get_object key=%s error_type=%s",
                key,
                type(exc).__name__,
            )
            raise SnapshotHistoryError("Previous snapshot loading failed") from exc

        LOGGER.info("Previous snapshot loaded key=%s", key)
        return LoadedSnapshot(key=key, snapshot=snapshot)
