"""Cost-aware autonomous pipeline decision engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..diff.models import ChangeReport

DecisionStatus = Literal["BASELINE_CREATED", "HEALTHY", "DRIFT_DETECTED"]


@dataclass(frozen=True, slots=True)
class PipelineDecision:
    """Deterministic actions selected from baseline and drift state."""

    status: DecisionStatus
    invoke_bedrock: bool
    send_ses: bool
    summary: str


def decide(previous_exists: bool, report: ChangeReport) -> PipelineDecision:
    """Select the minimum-cost actions required for the current run."""
    if not isinstance(previous_exists, bool):
        raise ValueError("previous_exists must be a boolean")
    if not isinstance(report, ChangeReport):
        raise ValueError("report must be a ChangeReport")
    report.validate()

    if not previous_exists:
        if report.summary.total_changes != 0:
            raise ValueError("baseline creation requires an empty change report")
        return PipelineDecision(
            status="BASELINE_CREATED",
            invoke_bedrock=False,
            send_ses=False,
            summary="Initial infrastructure baseline created.",
        )
    if report.summary.total_changes == 0:
        return PipelineDecision(
            status="HEALTHY",
            invoke_bedrock=False,
            send_ses=False,
            summary="Infrastructure Healthy. No drift detected.",
        )
    return PipelineDecision(
        status="DRIFT_DETECTED",
        invoke_bedrock=True,
        send_ses=True,
        summary="Infrastructure drift detected.",
    )
