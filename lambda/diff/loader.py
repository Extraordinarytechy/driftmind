"""Strict local JSON loading for Phase 2 infrastructure snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from models import Snapshot, SnapshotResource, SnapshotValidationError

_SNAPSHOT_FIELDS = {
    "schema_version",
    "generated_at",
    "provider",
    "environment",
    "resources",
}
_RESOURCE_FIELDS = {"resource_type", "logical_name", "properties"}


class SnapshotLoadError(ValueError):
    """Raised when local JSON cannot be loaded as a valid snapshot."""


def _require_exact_fields(
    document: dict[str, Any], expected: set[str], location: str
) -> None:
    actual = set(document)
    if actual == expected:
        return
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    details: list[str] = []
    if missing:
        details.append(f"missing={missing}")
    if unexpected:
        details.append(f"unexpected={unexpected}")
    raise SnapshotLoadError(f"Invalid fields at {location}: {', '.join(details)}")


def parse_snapshot_json(payload: str | bytes) -> Snapshot:
    """Parse strict schema 1.0 JSON into the existing Snapshot model."""
    if isinstance(payload, bytes):
        try:
            payload = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SnapshotLoadError("Snapshot must be UTF-8 encoded") from exc
    if not isinstance(payload, str):
        raise SnapshotLoadError("Snapshot payload must be text or bytes")

    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SnapshotLoadError("Snapshot contains invalid JSON") from exc
    if not isinstance(document, dict):
        raise SnapshotLoadError("Snapshot root must be an object")
    _require_exact_fields(document, _SNAPSHOT_FIELDS, "snapshot")

    resources_data = document["resources"]
    if not isinstance(resources_data, list):
        raise SnapshotLoadError("Snapshot resources must be an array")

    resources: list[SnapshotResource] = []
    for index, resource_data in enumerate(resources_data):
        if not isinstance(resource_data, dict):
            raise SnapshotLoadError(f"Resource at index {index} must be an object")
        _require_exact_fields(resource_data, _RESOURCE_FIELDS, f"resources[{index}]")
        resources.append(
            SnapshotResource(
                resource_type=resource_data["resource_type"],
                logical_name=resource_data["logical_name"],
                properties=resource_data["properties"],
            )
        )

    snapshot = Snapshot(
        schema_version=document["schema_version"],
        generated_at=document["generated_at"],
        provider=document["provider"],
        environment=document["environment"],
        resources=resources,
    )
    try:
        snapshot.validate()
    except SnapshotValidationError as exc:
        raise SnapshotLoadError(f"Snapshot validation failed: {exc}") from exc
    return snapshot


class LocalSnapshotLoader:
    """Load current and previous snapshots from local JSON files."""

    def load(self, path: str | Path) -> Snapshot:
        """Load one strict snapshot from a local UTF-8 JSON file."""
        snapshot_path = Path(path)
        try:
            payload = snapshot_path.read_bytes()
        except OSError as exc:
            raise SnapshotLoadError(
                f"Could not read snapshot file: {snapshot_path}"
            ) from exc
        return parse_snapshot_json(payload)

    def load_pair(
        self,
        previous_path: str | Path,
        current_path: str | Path,
    ) -> tuple[Snapshot, Snapshot]:
        """Load and return snapshots in previous, current order."""
        previous = self.load(previous_path)
        current = self.load(current_path)
        return previous, current


def load_snapshot(path: str | Path) -> Snapshot:
    """Convenience function for loading one local snapshot."""
    return LocalSnapshotLoader().load(path)
