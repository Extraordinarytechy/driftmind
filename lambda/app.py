"""AWS Lambda entry point for the DriftMind snapshot pipeline."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from config import Config
from logger import configure_logging, get_logger
from snapshot.collector import SnapshotCollector
from storage import S3Client, SnapshotStorage

configure_logging()
LOGGER = get_logger(__name__)


def run_snapshot_pipeline(
    environ: Mapping[str, str] | None = None,
    s3_client: S3Client | None = None,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Execute the configured snapshot pipeline and return its result."""
    config = Config.from_env(environ)
    LOGGER.info(
        "Configuration loaded provider=%s region=%s",
        config.provider,
        config.aws_region,
    )

    collector = SnapshotCollector(provider_name=config.provider, clock=clock)
    snapshot = collector.collect()
    storage = SnapshotStorage(
        bucket=config.snapshot_bucket,
        region=config.aws_region,
        s3_client=s3_client,
    )
    key = storage.upload(snapshot)

    return {
        "status": "success",
        "schema_version": snapshot.schema_version,
        "generated_at": snapshot.generated_at,
        "provider": snapshot.provider,
        "environment": snapshot.environment,
        "resource_count": len(snapshot.resources),
        "s3": {"bucket": config.snapshot_bucket, "key": key},
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Handle a Lambda invocation without exposing internal stack details."""
    del event, context
    try:
        return run_snapshot_pipeline()
    except Exception as exc:  # Lambda boundary must log all pipeline failures.
        LOGGER.error(
            "Snapshot pipeline failed operation=run_snapshot_pipeline error_type=%s",
            type(exc).__name__,
        )
        return {
            "status": "error",
            "error_type": type(exc).__name__,
            "message": "Snapshot pipeline execution failed.",
        }
