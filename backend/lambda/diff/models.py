"""Structured models for deterministic infrastructure change reports."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, Literal

ChangeType = Literal["added", "removed", "modified"]
_CHANGE_ID_PATTERN = re.compile(r"^CHG-[0-9]{4,}$")


class DiffValidationError(ValueError):
    """Raised when a change report violates its machine-readable contract."""


def _validate_json_value(value: Any, path: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DiffValidationError(f"{path} must contain only finite numbers")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise DiffValidationError(f"{path} keys must be strings")
            _validate_json_value(item, f"{path}.{key}")
        return
    raise DiffValidationError(f"{path} contains a non-JSON value")


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class Change:
    """One added resource, removed resource, or modified property."""

    change_id: str
    change_type: ChangeType
    resource_type: str
    logical_name: str
    field: str | None
    old: Any
    new: Any

    def validate(self) -> None:
        """Validate the exact change entry contract."""
        if not isinstance(self.change_id, str) or not _CHANGE_ID_PATTERN.fullmatch(
            self.change_id
        ):
            raise DiffValidationError("change_id must match CHG-0001 format")
        if self.change_type not in {"added", "removed", "modified"}:
            raise DiffValidationError("change_type must be added, removed, or modified")
        if not isinstance(self.resource_type, str) or not self.resource_type.strip():
            raise DiffValidationError("resource_type must be a non-empty string")
        if not isinstance(self.logical_name, str) or not self.logical_name.strip():
            raise DiffValidationError("logical_name must be a non-empty string")
        if self.change_type == "modified":
            if not isinstance(self.field, str) or not self.field.strip():
                raise DiffValidationError("modified changes require a field")
        elif self.field is not None:
            raise DiffValidationError("added and removed changes require field=null")
        if self.change_type == "added" and self.old is not None:
            raise DiffValidationError("added changes require old=null")
        if self.change_type == "removed" and self.new is not None:
            raise DiffValidationError("removed changes require new=null")
        _validate_json_value(self.old, "old")
        _validate_json_value(self.new, "new")

    def to_dict(self) -> dict[str, Any]:
        """Return the exact machine-readable change representation."""
        self.validate()
        return {
            "change_id": self.change_id,
            "change_type": self.change_type,
            "resource_type": self.resource_type,
            "logical_name": self.logical_name,
            "field": self.field,
            "old": _canonicalize(self.old),
            "new": _canonicalize(self.new),
        }


@dataclass(frozen=True, slots=True)
class ChangeSummary:
    """Numeric counts for property-level change entries."""

    total_changes: int
    added: int
    removed: int
    modified: int

    def validate(self) -> None:
        """Validate non-negative, internally consistent counts."""
        counts = (self.total_changes, self.added, self.removed, self.modified)
        if any(type(count) is not int or count < 0 for count in counts):
            raise DiffValidationError("summary counts must be non-negative integers")
        if self.total_changes != self.added + self.removed + self.modified:
            raise DiffValidationError("total_changes must equal categorized change counts")

    def to_dict(self) -> dict[str, int]:
        """Return deterministic summary fields."""
        self.validate()
        return {
            "total_changes": self.total_changes,
            "added": self.added,
            "removed": self.removed,
            "modified": self.modified,
        }


@dataclass(frozen=True, slots=True)
class ChangeReport:
    """A deterministic machine-readable report with no generated prose."""

    summary: ChangeSummary
    changes: tuple[Change, ...]

    def validate(self) -> None:
        """Validate summary consistency and stable sequential change IDs."""
        if not isinstance(self.summary, ChangeSummary):
            raise DiffValidationError("summary must be a ChangeSummary")
        if not isinstance(self.changes, tuple):
            raise DiffValidationError("changes must be a tuple")
        self.summary.validate()
        if self.summary.total_changes != len(self.changes):
            raise DiffValidationError("total_changes must equal the changes length")

        counts = {"added": 0, "removed": 0, "modified": 0}
        for index, change in enumerate(self.changes, start=1):
            if not isinstance(change, Change):
                raise DiffValidationError("changes must contain Change models")
            change.validate()
            expected_id = f"CHG-{index:04d}"
            if change.change_id != expected_id:
                raise DiffValidationError(
                    f"Expected change_id {expected_id}, got {change.change_id}"
                )
            counts[change.change_type] += 1
        if counts != {
            "added": self.summary.added,
            "removed": self.summary.removed,
            "modified": self.summary.modified,
        }:
            raise DiffValidationError("summary counts do not match changes")

    def to_dict(self) -> dict[str, Any]:
        """Return exactly the summary and changes report fields."""
        self.validate()
        return {
            "summary": self.summary.to_dict(),
            "changes": [change.to_dict() for change in self.changes],
        }

    def __str__(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, allow_nan=False)
