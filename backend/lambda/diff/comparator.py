"""Pure deterministic comparison of two validated infrastructure snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from models import Snapshot, SnapshotResource

from .models import Change, ChangeReport, ChangeSummary


class SnapshotCompatibilityError(ValueError):
    """Raised when two snapshots cannot be compared safely."""


@dataclass(frozen=True, slots=True)
class _PendingChange:
    change_type: str
    resource_type: str
    logical_name: str
    field: str | None
    old: Any
    new: Any


def _index_resources(snapshot: Snapshot) -> dict[tuple[str, str], SnapshotResource]:
    return {
        (resource.resource_type, resource.logical_name): resource
        for resource in snapshot.resources
    }


def _json_equal(old: Any, new: Any) -> bool:
    if type(old) is not type(new):
        return False
    if isinstance(old, dict):
        return old.keys() == new.keys() and all(
            _json_equal(old[key], new[key]) for key in old
        )
    if isinstance(old, list):
        return len(old) == len(new) and all(
            _json_equal(old_item, new_item)
            for old_item, new_item in zip(old, new)
        )
    return bool(old == new)


def _field_path(prefix: str, key: str) -> str:
    return f"{prefix}.{key}" if prefix else key


def _compare_properties(
    old: dict[str, Any],
    new: dict[str, Any],
    resource_type: str,
    logical_name: str,
    prefix: str = "",
) -> list[_PendingChange]:
    changes: list[_PendingChange] = []
    for key in sorted(old.keys() | new.keys()):
        field = _field_path(prefix, key)
        if key not in old:
            changes.append(
                _PendingChange("modified", resource_type, logical_name, field, None, new[key])
            )
            continue
        if key not in new:
            changes.append(
                _PendingChange("modified", resource_type, logical_name, field, old[key], None)
            )
            continue

        old_value = old[key]
        new_value = new[key]
        if isinstance(old_value, dict) and isinstance(new_value, dict):
            changes.extend(
                _compare_properties(
                    old_value,
                    new_value,
                    resource_type,
                    logical_name,
                    field,
                )
            )
        elif not _json_equal(old_value, new_value):
            changes.append(
                _PendingChange(
                    "modified", resource_type, logical_name, field, old_value, new_value
                )
            )
    return changes


def _validate_compatibility(previous: Snapshot, current: Snapshot) -> None:
    previous.validate()
    current.validate()
    mismatches: list[str] = []
    if previous.schema_version != current.schema_version:
        mismatches.append("schema_version")
    if previous.provider != current.provider:
        mismatches.append("provider")
    if previous.environment != current.environment:
        mismatches.append("environment")
    if mismatches:
        raise SnapshotCompatibilityError(
            f"Snapshots differ in compatibility field(s): {', '.join(mismatches)}"
        )


def compare_snapshots(previous: Snapshot, current: Snapshot) -> ChangeReport:
    """Compare compatible snapshots and return a deterministic change report."""
    _validate_compatibility(previous, current)
    previous_resources = _index_resources(previous)
    current_resources = _index_resources(current)
    previous_ids = set(previous_resources)
    current_ids = set(current_resources)
    pending: list[_PendingChange] = []

    for resource_id in sorted(current_ids - previous_ids):
        current_resource = current_resources[resource_id]
        pending.append(
            _PendingChange(
                "added",
                current_resource.resource_type,
                current_resource.logical_name,
                None,
                None,
                current_resource.properties,
            )
        )

    for resource_id in sorted(previous_ids - current_ids):
        previous_resource = previous_resources[resource_id]
        pending.append(
            _PendingChange(
                "removed",
                previous_resource.resource_type,
                previous_resource.logical_name,
                None,
                previous_resource.properties,
                None,
            )
        )

    for resource_id in sorted(previous_ids & current_ids):
        previous_resource = previous_resources[resource_id]
        current_resource = current_resources[resource_id]
        pending.extend(
            _compare_properties(
                previous_resource.properties,
                current_resource.properties,
                current_resource.resource_type,
                current_resource.logical_name,
            )
        )

    changes = tuple(
        Change(
            change_id=f"CHG-{index:04d}",
            change_type=item.change_type,
            resource_type=item.resource_type,
            logical_name=item.logical_name,
            field=item.field,
            old=item.old,
            new=item.new,
        )
        for index, item in enumerate(pending, start=1)
    )
    summary = ChangeSummary(
        total_changes=len(changes),
        added=sum(change.change_type == "added" for change in changes),
        removed=sum(change.change_type == "removed" for change in changes),
        modified=sum(change.change_type == "modified" for change in changes),
    )
    report = ChangeReport(summary=summary, changes=changes)
    report.validate()
    return report
