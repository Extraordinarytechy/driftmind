"""Shared normalization helpers for read-only AWS resource collectors."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from logger import get_logger

LOGGER = get_logger("collectors")


def log_api_failure(service: str, operation: str, error: BaseException) -> None:
    """Log only non-sensitive failure metadata."""
    LOGGER.error(
        "AWS collection failed service=%s operation=%s error_type=%s",
        service,
        operation,
        type(error).__name__,
    )


def error_code(error: BaseException) -> str:
    """Safely extract an AWS error code without exposing response content."""
    response = getattr(error, "response", None)
    if not isinstance(response, dict):
        return ""
    details = response.get("Error", {})
    return str(details.get("Code", "")) if isinstance(details, dict) else ""


def parse_json(value: Any) -> Any:
    """Parse SDK JSON strings when valid, preserving non-JSON strings."""
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def normalize(value: Any, *, sort_lists: bool = False) -> Any:
    """Recursively convert SDK values to deterministic JSON-compatible values."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {
            str(key): normalize(value[key], sort_lists=sort_lists)
            for key in sorted(value, key=str)
        }
    if isinstance(value, (list, tuple, set)):
        items = [normalize(item, sort_lists=sort_lists) for item in value]
        if sort_lists:
            items.sort(key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
        return items
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


def policy(value: Any) -> Any:
    """Parse and canonicalize policy or event-pattern JSON."""
    return normalize(parse_json(value), sort_lists=True)


def selected(source: dict[str, Any], names: tuple[str, ...]) -> dict[str, Any]:
    """Copy present allow-listed fields with recursive normalization."""
    return {name: normalize(source[name]) for name in names if name in source}
