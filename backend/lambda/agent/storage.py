"""Deterministic Amazon S3 storage for autonomous reports."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Protocol

from logger import get_logger

from .models import AutonomousReport, AutonomousReportError

LOGGER = get_logger(__name__)
LATEST_REPORT_KEY = "reports/latest.json"


class ReportStorageError(RuntimeError):
    """Raised when an autonomous report cannot be stored."""


class ReportS3Client(Protocol):
    """S3 operations required for report persistence."""

    def put_object(self, **kwargs: Any) -> Any:
        """Store one report object."""

    def get_object(self, **kwargs: Any) -> Any:
        """Read one report object (used to carry prior analysis into latest)."""


def serialize_autonomous_report(report: AutonomousReport) -> str:
    """Serialize a validated report as deterministic UTF-8 JSON."""
    if not isinstance(report, AutonomousReport):
        raise AutonomousReportError("report must be an AutonomousReport")
    report.validate()
    return _serialize_document(report.to_dict())


def _serialize_document(document: dict[str, Any]) -> str:
    """Serialize a JSON-ready report document with the canonical formatting."""
    return json.dumps(
        document,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    ) + "\n"


def build_latest_report_payload(
    current: dict[str, Any],
    previous_latest: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return the latest-only document, reusing prior drift analysis when healthy.

    This never mutates the immutable historical report. It only adds the
    additive ``analysis_source``, ``last_drift_analysis``, and
    ``last_drift_run_time`` fields to the frontend's stable latest object.
    """
    enriched = dict(current)
    if current.get("analysis") is not None:
        enriched["analysis_source"] = "generated"
        enriched["last_drift_analysis"] = current["analysis"]
        enriched["last_drift_run_time"] = current.get("run_time")
        return enriched

    prior_analysis: dict[str, Any] | None = None
    prior_time: Any = None
    if isinstance(previous_latest, dict):
        if isinstance(previous_latest.get("last_drift_analysis"), dict):
            prior_analysis = previous_latest["last_drift_analysis"]
            prior_time = previous_latest.get("last_drift_run_time")
        elif isinstance(previous_latest.get("analysis"), dict):
            prior_analysis = previous_latest["analysis"]
            prior_time = previous_latest.get("run_time")

    if prior_analysis is not None:
        enriched["analysis_source"] = "last_drift"
        enriched["last_drift_analysis"] = prior_analysis
        enriched["last_drift_run_time"] = prior_time
    else:
        enriched["analysis_source"] = "none"
        enriched["last_drift_analysis"] = None
        enriched["last_drift_run_time"] = None
    return enriched


def build_report_key(report: AutonomousReport) -> str:
    """Build a date-partitioned immutable report key."""
    report.validate()
    generated_at = datetime.fromisoformat(report.run_time.replace("Z", "+00:00"))
    timestamp = generated_at.strftime("%Y%m%dT%H%M%S%fZ")
    return f"reports/{generated_at:%Y/%m/%d}/report-{timestamp}.json"


class ReportStorage:
    """Persist immutable reports and refresh the frontend's stable latest object."""

    def __init__(self, bucket: str, s3_client: ReportS3Client) -> None:
        if not isinstance(bucket, str) or not bucket.strip():
            raise ReportStorageError("Report bucket must not be empty")
        self._bucket = bucket
        self._s3_client = s3_client

    def _load_previous_latest(self) -> dict[str, Any] | None:
        """Best-effort read of the existing latest report; never raises."""
        try:
            response = self._s3_client.get_object(
                Bucket=self._bucket, Key=LATEST_REPORT_KEY
            )
            if not isinstance(response, dict) or "Body" not in response:
                return None
            body = response["Body"]
            payload = body.read() if hasattr(body, "read") else body
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")
            if not isinstance(payload, str):
                return None
            document = json.loads(payload)
            return document if isinstance(document, dict) else None
        except Exception:
            return None

    def store(self, report: AutonomousReport) -> str:
        """Store one historical report, refresh latest, and return the historical key."""
        report_document = report.to_dict()
        payload = serialize_autonomous_report(report).encode("utf-8")
        key = build_report_key(report)
        try:
            self._s3_client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=payload,
                ContentType="application/json",
                ServerSideEncryption="AES256",
                IfNoneMatch="*",
            )
        except Exception as exc:
            LOGGER.error(
                "Report storage failed operation=put_object key=%s error_type=%s",
                key,
                type(exc).__name__,
            )
            raise ReportStorageError("Report storage failed") from exc
        LOGGER.info("Report stored key=%s bytes=%d", key, len(payload))

        # Only read the prior latest object when this run has no generated
        # analysis; drift runs already carry their own analysis, so the read
        # would be discarded (see build_latest_report_payload).
        previous_latest = (
            None
            if report_document.get("analysis") is not None
            else self._load_previous_latest()
        )
        latest_document = build_latest_report_payload(report_document, previous_latest)
        latest_payload = _serialize_document(latest_document).encode("utf-8")
        try:
            self._s3_client.put_object(
                Bucket=self._bucket,
                Key=LATEST_REPORT_KEY,
                Body=latest_payload,
                ContentType="application/json",
                CacheControl="no-cache, max-age=0",
                ServerSideEncryption="AES256",
            )
        except Exception as exc:
            LOGGER.error(
                "Latest report update failed operation=put_object key=%s error_type=%s",
                LATEST_REPORT_KEY,
                type(exc).__name__,
            )
        else:
            LOGGER.info(
                "Latest report updated key=%s bytes=%d source=%s",
                LATEST_REPORT_KEY,
                len(latest_payload),
                latest_document.get("analysis_source"),
            )
        return key
