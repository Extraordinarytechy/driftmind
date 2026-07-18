"""Deterministic JSON output for infrastructure change reports."""

from __future__ import annotations

import json
from pathlib import Path

from .models import ChangeReport, DiffValidationError


def serialize_change_report(report: ChangeReport) -> str:
    """Serialize a validated report as deterministic UTF-8 JSON."""
    report.validate()
    try:
        return json.dumps(
            report.to_dict(),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ) + "\n"
    except (TypeError, ValueError) as exc:
        raise DiffValidationError("Change report could not be serialized") from exc


def write_change_report(report: ChangeReport, path: str | Path) -> Path:
    """Write a report to a local UTF-8 JSON file and return its path."""
    output_path = Path(path)
    output_path.write_text(serialize_change_report(report), encoding="utf-8")
    return output_path
