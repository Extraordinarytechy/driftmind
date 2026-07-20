"""Drift-only SES notification formatting and delivery."""

from __future__ import annotations

import html
from collections.abc import Mapping

from ..notification.email import SESEmailClient, SESClientProtocol
from ..notification.models import NotificationRequest, NotificationResult
from .models import AutonomousReport


class DriftNotificationError(ValueError):
    """Raised when a report cannot be formatted for drift notification."""


def _change_lines(report: AutonomousReport) -> list[str]:
    lines: list[str] = []
    for change in report.change_report.changes:
        field = f" field={change.field}" if change.field is not None else ""
        lines.append(
            f"{change.change_id} {change.change_type} "
            f"{change.resource_type}/{change.logical_name}{field}"
        )
    return lines


def format_drift_notification(report: AutonomousReport) -> NotificationRequest:
    """Create a multipart request containing evidence, risk, and recommendations."""
    if not isinstance(report, AutonomousReport):
        raise DriftNotificationError("report must be an AutonomousReport")
    report.validate()
    if not report.changes_detected or report.analysis is None:
        raise DriftNotificationError("drift notification requires completed analysis")

    changes = _change_lines(report)
    recommendations = list(report.analysis.recommendations)
    text_body = "\n".join(
        (
            "DriftMind Infrastructure Drift Alert",
            f"Run: {report.run_time}",
            f"Risk: {report.analysis.risk_level}",
            "",
            "Detected Changes",
            *[f"- {line}" for line in changes],
            "",
            "AI Summary",
            report.analysis.executive_summary,
            "",
            "Explanation",
            report.analysis.change_explanation,
            "",
            "Potential Impact",
            report.analysis.potential_impact,
            "",
            "Recommendations",
            *[f"- {item}" for item in recommendations],
        )
    )
    changes_html = "".join(f"<li>{html.escape(line)}</li>" for line in changes)
    recommendations_html = "".join(
        f"<li>{html.escape(item)}</li>" for item in recommendations
    )
    html_body = "".join(
        (
            "<!DOCTYPE html><html lang=\"en\"><body>",
            "<h1>DriftMind Infrastructure Drift Alert</h1>",
            f"<p><strong>Run:</strong> {html.escape(report.run_time)}</p>",
            f"<p><strong>Risk:</strong> {html.escape(report.analysis.risk_level)}</p>",
            f"<h2>Detected Changes</h2><ul>{changes_html}</ul>",
            f"<h2>AI Summary</h2><p>{html.escape(report.analysis.executive_summary)}</p>",
            f"<h2>Explanation</h2><p>{html.escape(report.analysis.change_explanation)}</p>",
            f"<h2>Potential Impact</h2><p>{html.escape(report.analysis.potential_impact)}</p>",
            f"<h2>Recommendations</h2><ul>{recommendations_html}</ul>",
            "</body></html>",
        )
    )
    request = NotificationRequest(
        subject=f"DriftMind {report.analysis.risk_level} Risk Drift Alert",
        text_body=text_body,
        html_body=html_body,
    )
    request.validate()
    return request


class DriftNotificationService:
    """Send notifications only for reports containing analyzed drift."""

    def __init__(self, client: SESEmailClient) -> None:
        self._client = client

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        ses_client: SESClientProtocol | None = None,
    ) -> "DriftNotificationService":
        """Create a notification service from environment settings."""
        return cls(SESEmailClient(environ=environ, ses_client=ses_client))

    def notify(self, report: AutonomousReport) -> NotificationResult:
        """Format and deliver one drift-only report."""
        return self._client.send(format_drift_notification(report))
