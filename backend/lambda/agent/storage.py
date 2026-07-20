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
    """S3 operation required for report persistence."""

    def put_object(self, **kwargs: Any) -> Any:
        """Store one report object."""


def serialize_autonomous_report(report: AutonomousReport) -> str:
    """Serialize a validated report as deterministic UTF-8 JSON."""
    if not isinstance(report, AutonomousReport):
        raise AutonomousReportError("report must be an AutonomousReport")
    report.validate()
    return json.dumps(
        report.to_dict(),
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    ) + "\n"


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

    def store(self, report: AutonomousReport) -> str:
        """Store one historical report, refresh latest, and return the historical key."""
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

        try:
            self._s3_client.put_object(
                Bucket=self._bucket,
                Key=LATEST_REPORT_KEY,
                Body=payload,
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
                "Latest report updated key=%s bytes=%d",
                LATEST_REPORT_KEY,
                len(payload),
            )
        return key
