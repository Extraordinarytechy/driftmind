"""Stable report contract for autonomous runs and read-only frontends."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from ..ai.drift import DriftAnalysis
from ..diff.models import ChangeReport
from .decision import DecisionStatus

REPORT_SCHEMA_VERSION = "1.0"
ActivityStatus = Literal["COMPLETED", "SKIPPED", "FAILED"]


class AutonomousReportError(ValueError):
    """Raised when an autonomous report violates its stable contract."""


@dataclass(frozen=True, slots=True)
class ActivityEvent:
    """One frontend-safe autonomous run activity entry."""

    stage: str
    status: ActivityStatus
    timestamp: str

    def validate(self) -> None:
        if not isinstance(self.stage, str) or not self.stage.strip():
            raise AutonomousReportError("activity stage must be non-empty")
        if self.status not in {"COMPLETED", "SKIPPED", "FAILED"}:
            raise AutonomousReportError("activity status is invalid")
        _validate_run_time(self.timestamp)

    def to_dict(self) -> dict[str, str]:
        self.validate()
        return {
            "stage": self.stage,
            "status": self.status,
            "timestamp": self.timestamp,
        }


def _validate_run_time(value: str) -> None:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise AutonomousReportError("run_time must be a UTC ISO 8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AutonomousReportError("run_time must be valid ISO 8601") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise AutonomousReportError("run_time must be UTC")


@dataclass(frozen=True, slots=True)
class AutonomousReport:
    """Single source of truth consumed by future read-only dashboards."""

    run_time: str
    status: DecisionStatus
    resources_scanned: int
    changes_detected: bool
    bedrock_invoked: bool
    summary: str
    change_report: ChangeReport
    current_snapshot_key: str
    previous_snapshot_key: str | None
    analysis: DriftAnalysis | None = None
    ses_sent: bool = False
    ses_message_id: str | None = None
    activity_timeline: tuple[ActivityEvent, ...] = ()

    def validate(self) -> None:
        """Validate report state and cross-field consistency."""
        _validate_run_time(self.run_time)
        if self.status not in {"BASELINE_CREATED", "HEALTHY", "DRIFT_DETECTED"}:
            raise AutonomousReportError("report status is invalid")
        if type(self.resources_scanned) is not int or self.resources_scanned < 0:
            raise AutonomousReportError("resources_scanned must be non-negative")
        if type(self.changes_detected) is not bool:
            raise AutonomousReportError("changes_detected must be boolean")
        if type(self.bedrock_invoked) is not bool or type(self.ses_sent) is not bool:
            raise AutonomousReportError("service invocation flags must be boolean")
        if not isinstance(self.summary, str) or not self.summary.strip():
            raise AutonomousReportError("summary must be non-empty")
        if not isinstance(self.change_report, ChangeReport):
            raise AutonomousReportError("change_report must be a ChangeReport")
        self.change_report.validate()
        has_changes = self.change_report.summary.total_changes > 0
        if self.changes_detected != has_changes:
            raise AutonomousReportError("changes_detected does not match drift summary")
        if self.status == "BASELINE_CREATED" and self.previous_snapshot_key is not None:
            raise AutonomousReportError("baseline report cannot have a previous snapshot")
        if self.status == "HEALTHY" and (self.previous_snapshot_key is None or has_changes):
            raise AutonomousReportError("healthy report requires an unchanged baseline")
        if self.status == "DRIFT_DETECTED" and not has_changes:
            raise AutonomousReportError("drift report requires detected changes")
        if not isinstance(self.current_snapshot_key, str) or not self.current_snapshot_key:
            raise AutonomousReportError("current_snapshot_key must be non-empty")
        if self.previous_snapshot_key is not None and (
            not isinstance(self.previous_snapshot_key, str)
            or not self.previous_snapshot_key
        ):
            raise AutonomousReportError("previous_snapshot_key must be null or non-empty")
        if self.analysis is not None:
            self.analysis.validate()
            if not self.changes_detected or not self.bedrock_invoked:
                raise AutonomousReportError("analysis requires an invoked drift run")
        if self.bedrock_invoked and not self.changes_detected:
            raise AutonomousReportError("Bedrock cannot be invoked without drift")
        if self.ses_sent:
            if self.analysis is None or not self.ses_message_id:
                raise AutonomousReportError("SES success requires analysis and message ID")
        elif self.ses_message_id is not None:
            raise AutonomousReportError("SES message ID requires successful delivery")
        if not isinstance(self.activity_timeline, tuple):
            raise AutonomousReportError("activity_timeline must be a tuple")
        for event in self.activity_timeline:
            if not isinstance(event, ActivityEvent):
                raise AutonomousReportError("activity_timeline contains invalid entries")
            event.validate()

    def _group_changes(self) -> dict[str, list[dict[str, Any]]]:
        grouped = {"added": [], "removed": [], "modified": []}
        for change in self.change_report.changes:
            grouped[change.change_type].append(change.to_dict())
        return grouped

    def to_dict(self) -> dict[str, Any]:
        """Return the stable JSON-ready frontend contract."""
        self.validate()
        grouped = self._group_changes()
        analysis = self.analysis.to_dict() if self.analysis is not None else None
        recommendations = (
            list(self.analysis.recommendations) if self.analysis is not None else []
        )
        return {
            "schema_version": REPORT_SCHEMA_VERSION,
            "run_time": self.run_time,
            "status": self.status,
            "resources_scanned": self.resources_scanned,
            "changes_detected": self.changes_detected,
            "bedrock_invoked": self.bedrock_invoked,
            "summary": self.summary,
            "drift_summary": self.change_report.summary.to_dict(),
            "added": grouped["added"],
            "removed": grouped["removed"],
            "modified": grouped["modified"],
            "risk": self.analysis.risk_level if self.analysis is not None else None,
            "ai_summary": (
                self.analysis.executive_summary if self.analysis is not None else None
            ),
            "ai_explanation": (
                self.analysis.change_explanation if self.analysis is not None else None
            ),
            "potential_impact": (
                self.analysis.potential_impact if self.analysis is not None else None
            ),
            "recommendation": " ".join(recommendations) if recommendations else None,
            "recommendations": recommendations,
            "analysis": analysis,
            "snapshots": {
                "current": self.current_snapshot_key,
                "previous": self.previous_snapshot_key,
            },
            "ses_sent": self.ses_sent,
            "ses_message_id": self.ses_message_id,
            "activity_timeline": [
                event.to_dict() for event in self.activity_timeline
            ],
        }
