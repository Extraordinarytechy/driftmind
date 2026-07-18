"""Versioned data models for DriftMind infrastructure snapshots."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = "1.0"


class SnapshotValidationError(ValueError):
    """Raised when a snapshot does not satisfy schema version 1.0."""


def _validate_json_value(value: Any, path: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SnapshotValidationError(f"{path} must contain only finite numbers")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise SnapshotValidationError(f"{path} keys must be strings")
            _validate_json_value(item, f"{path}.{key}")
        return
    raise SnapshotValidationError(f"{path} contains a non-JSON value: {type(value).__name__}")


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


@dataclass(slots=True)
class SnapshotResource:
    """A normalized infrastructure resource in a snapshot."""

    resource_type: str
    logical_name: str
    properties: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """Validate resource identity and JSON-compatible properties."""
        if not isinstance(self.resource_type, str) or not self.resource_type.strip():
            raise SnapshotValidationError("resource_type must be a non-empty string")
        if not isinstance(self.logical_name, str) or not self.logical_name.strip():
            raise SnapshotValidationError("logical_name must be a non-empty string")
        if not isinstance(self.properties, dict):
            raise SnapshotValidationError("properties must be an object")
        _validate_json_value(self.properties, "properties")

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical JSON representation of this resource."""
        self.validate()
        return {
            "resource_type": self.resource_type,
            "logical_name": self.logical_name,
            "properties": _canonicalize(self.properties),
        }


@dataclass(slots=True)
class Snapshot:
    """A complete snapshot conforming exactly to schema version 1.0."""

    schema_version: str
    generated_at: str
    provider: str
    environment: str
    resources: list[SnapshotResource] = field(default_factory=list)

    def generated_datetime(self) -> datetime:
        """Parse and return the generation time after enforcing UTC."""
        if not isinstance(self.generated_at, str) or not self.generated_at.strip():
            raise SnapshotValidationError("generated_at must be a UTC ISO 8601 string")
        try:
            parsed = datetime.fromisoformat(self.generated_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise SnapshotValidationError(
                "generated_at must be a valid UTC ISO 8601 string"
            ) from exc
        if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(None):
            raise SnapshotValidationError("generated_at must include a UTC offset")
        return parsed.astimezone(timezone.utc)

    def validate(self) -> None:
        """Validate the snapshot and every nested resource."""
        if self.schema_version != SCHEMA_VERSION:
            raise SnapshotValidationError(
                f"schema_version must be {SCHEMA_VERSION!r}"
            )
        self.generated_datetime()
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise SnapshotValidationError("provider must be a non-empty string")
        if not isinstance(self.environment, str) or not self.environment.strip():
            raise SnapshotValidationError("environment must be a non-empty string")
        if not isinstance(self.resources, list):
            raise SnapshotValidationError("resources must be an array")

        identities: set[tuple[str, str]] = set()
        for resource in self.resources:
            if not isinstance(resource, SnapshotResource):
                raise SnapshotValidationError("resources must contain SnapshotResource models")
            resource.validate()
            identity = (resource.resource_type, resource.logical_name)
            if identity in identities:
                raise SnapshotValidationError(
                    f"Duplicate resource identity: {resource.resource_type}/{resource.logical_name}"
                )
            identities.add(identity)

    def to_dict(self) -> dict[str, Any]:
        """Return the exact schema 1.0 contract with canonical resource order."""
        self.validate()
        ordered_resources = sorted(
            self.resources,
            key=lambda resource: (resource.resource_type, resource.logical_name),
        )
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "provider": self.provider,
            "environment": self.environment,
            "resources": [resource.to_dict() for resource in ordered_resources],
        }

    def __str__(self) -> str:
        """Return canonical compact JSON for diagnostics without custom repr logic."""
        return json.dumps(self.to_dict(), ensure_ascii=False, allow_nan=False)
