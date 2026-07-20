"""End-to-end cost-aware autonomous infrastructure watcher."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime
from typing import Any, Protocol

from config import Config
from logger import get_logger
from models import Snapshot
from snapshot.collector import SnapshotCollector
from storage import S3Client, SnapshotStorage

from ..ai.client import BedrockRuntimeProtocol
from ..ai.drift import DriftAnalysis, DriftIntelligenceService
from ..diff.comparator import compare_snapshots
from ..diff.models import ChangeReport, ChangeSummary
from ..diff.s3_loader import S3SnapshotHistory
from ..notification.email import SESClientProtocol
from .decision import PipelineDecision, decide
from .models import ActivityEvent, AutonomousReport
from .notification import DriftNotificationService
from .storage import ReportStorage

LOGGER = get_logger(__name__)


class CollectorProtocol(Protocol):
    """Snapshot collector behavior required by the agent."""

    def collect(self) -> Snapshot:
        """Return one validated current snapshot."""


def _empty_change_report() -> ChangeReport:
    report = ChangeReport(
        summary=ChangeSummary(total_changes=0, added=0, removed=0, modified=0),
        changes=(),
    )
    report.validate()
    return report


def _event(stage: str, status: str, run_time: str) -> ActivityEvent:
    return ActivityEvent(stage=stage, status=status, timestamp=run_time)  # type: ignore[arg-type]


class AutonomousPipeline:
    """Collect, compare, decide, analyze, notify, and persist one run."""

    def __init__(
        self,
        config: Config,
        environ: Mapping[str, str] | None = None,
        s3_client: S3Client | None = None,
        bedrock_runtime_client: BedrockRuntimeProtocol | None = None,
        ses_client: SESClientProtocol | None = None,
        clock: Callable[[], datetime] | None = None,
        collector: CollectorProtocol | None = None,
    ) -> None:
        self._config = config
        self._environ = environ
        self._s3_client = s3_client
        self._bedrock_runtime_client = bedrock_runtime_client
        self._ses_client = ses_client
        self._clock = clock
        self._collector = collector

    def _build_report(
        self,
        snapshot: Snapshot,
        current_key: str,
        previous_key: str | None,
        decision: PipelineDecision,
        change_report: ChangeReport,
        analysis: DriftAnalysis | None,
        ses_sent: bool,
        ses_message_id: str | None,
        events: tuple[ActivityEvent, ...],
        summary: str | None = None,
    ) -> AutonomousReport:
        report = AutonomousReport(
            run_time=snapshot.generated_at,
            status=decision.status,
            resources_scanned=len(snapshot.resources),
            changes_detected=change_report.summary.total_changes > 0,
            bedrock_invoked=decision.invoke_bedrock,
            summary=summary or (
                analysis.executive_summary if analysis is not None else decision.summary
            ),
            change_report=change_report,
            current_snapshot_key=current_key,
            previous_snapshot_key=previous_key,
            analysis=analysis,
            ses_sent=ses_sent,
            ses_message_id=ses_message_id,
            activity_timeline=events,
        )
        report.validate()
        return report

    def _response(
        self,
        snapshot: Snapshot,
        snapshot_key: str,
        report: AutonomousReport,
        report_key: str,
    ) -> dict[str, Any]:
        """Return the original snapshot fields plus additive autonomous metadata."""
        return {
            "status": "success",
            "schema_version": snapshot.schema_version,
            "generated_at": snapshot.generated_at,
            "provider": snapshot.provider,
            "environment": snapshot.environment,
            "resource_count": len(snapshot.resources),
            "s3": {"bucket": self._config.snapshot_bucket, "key": snapshot_key},
            "pipeline_status": report.status,
            "changes_detected": report.changes_detected,
            "change_summary": report.change_report.summary.to_dict(),
            "bedrock_invoked": report.bedrock_invoked,
            "ses_sent": report.ses_sent,
            "report": {"bucket": self._config.snapshot_bucket, "key": report_key},
        }

    def _store_report(
        self,
        storage: ReportStorage,
        report: AutonomousReport,
    ) -> str:
        key = storage.store(report)
        LOGGER.info("Report stored key=%s", key)
        return key

    def run(self) -> dict[str, Any]:
        """Execute one autonomous run with conditional Bedrock and SES usage."""
        collector = self._collector or SnapshotCollector(
            provider_name=self._config.provider,
            clock=self._clock,
        )
        snapshot = collector.collect()
        snapshot.validate()
        snapshot_storage = SnapshotStorage(
            bucket=self._config.snapshot_bucket,
            region=self._config.aws_region,
            s3_client=self._s3_client,
        )
        current_key = snapshot_storage.upload(snapshot)
        s3_client = snapshot_storage.client
        report_storage = ReportStorage(self._config.snapshot_bucket, s3_client)

        LOGGER.info("Loading previous snapshot...")
        loaded = S3SnapshotHistory(
            bucket=self._config.snapshot_bucket,
            s3_client=s3_client,  # type: ignore[arg-type]
        ).load_latest_before(current_key)
        previous_key = loaded.key if loaded is not None else None
        if loaded is None:
            change_report = _empty_change_report()
        else:
            change_report = compare_snapshots(loaded.snapshot, snapshot)
        LOGGER.info("Snapshot comparison completed")
        LOGGER.info("Changes detected: %d", change_report.summary.total_changes)

        decision = decide(loaded is not None, change_report)
        events: tuple[ActivityEvent, ...] = (
            _event("SNAPSHOT_COLLECTED", "COMPLETED", snapshot.generated_at),
            _event("SNAPSHOT_STORED", "COMPLETED", snapshot.generated_at),
            _event(
                "PREVIOUS_SNAPSHOT_LOADED",
                "COMPLETED" if loaded is not None else "SKIPPED",
                snapshot.generated_at,
            ),
            _event("SNAPSHOT_COMPARISON", "COMPLETED", snapshot.generated_at),
        )

        if not decision.invoke_bedrock:
            LOGGER.info("Bedrock invoked: NO")
            LOGGER.info("SES sent: NO")
            events += (
                _event("BEDROCK_ANALYSIS", "SKIPPED", snapshot.generated_at),
                _event("SES_NOTIFICATION", "SKIPPED", snapshot.generated_at),
                _event("REPORT_STORED", "COMPLETED", snapshot.generated_at),
            )
            report = self._build_report(
                snapshot,
                current_key,
                previous_key,
                decision,
                change_report,
                analysis=None,
                ses_sent=False,
                ses_message_id=None,
                events=events,
            )
            report_key = self._store_report(report_storage, report)
            return self._response(snapshot, current_key, report, report_key)

        LOGGER.info("Bedrock invoked: YES")
        try:
            analysis = DriftIntelligenceService.from_env(
                environ=self._environ,
                runtime_client=self._bedrock_runtime_client,
            ).analyze(change_report)
        except Exception:
            failure_events = events + (
                _event("BEDROCK_ANALYSIS", "FAILED", snapshot.generated_at),
                _event("SES_NOTIFICATION", "SKIPPED", snapshot.generated_at),
                _event("REPORT_STORED", "COMPLETED", snapshot.generated_at),
            )
            failed_report = self._build_report(
                snapshot,
                current_key,
                previous_key,
                decision,
                change_report,
                analysis=None,
                ses_sent=False,
                ses_message_id=None,
                events=failure_events,
                summary="Infrastructure drift detected. AI analysis failed.",
            )
            self._store_report(report_storage, failed_report)
            LOGGER.info("SES sent: NO")
            raise

        analyzed_events = events + (
            _event("BEDROCK_ANALYSIS", "COMPLETED", snapshot.generated_at),
        )
        pending_report = self._build_report(
            snapshot,
            current_key,
            previous_key,
            decision,
            change_report,
            analysis=analysis,
            ses_sent=False,
            ses_message_id=None,
            events=analyzed_events,
        )
        try:
            notification = DriftNotificationService.from_env(
                environ=self._environ,
                ses_client=self._ses_client,
            ).notify(pending_report)
        except Exception:
            failure_events = analyzed_events + (
                _event("SES_NOTIFICATION", "FAILED", snapshot.generated_at),
                _event("REPORT_STORED", "COMPLETED", snapshot.generated_at),
            )
            failed_report = replace(
                pending_report,
                activity_timeline=failure_events,
            )
            self._store_report(report_storage, failed_report)
            LOGGER.info("SES sent: NO")
            raise

        LOGGER.info("SES sent: YES")
        completed_events = analyzed_events + (
            _event("SES_NOTIFICATION", "COMPLETED", snapshot.generated_at),
            _event("REPORT_STORED", "COMPLETED", snapshot.generated_at),
        )
        report = replace(
            pending_report,
            ses_sent=True,
            ses_message_id=notification.message_id,
            activity_timeline=completed_events,
        )
        report.validate()
        report_key = self._store_report(report_storage, report)
        return self._response(snapshot, current_key, report, report_key)
