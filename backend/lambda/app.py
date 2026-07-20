"""AWS Lambda entry point for the DriftMind snapshot pipeline."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from config import Config
from logger import configure_logging, get_logger
from snapshot.collector import SnapshotCollector
from storage import S3Client, SnapshotStorage

from .agent.service import AutonomousPipeline, CollectorProtocol
from .ai.client import BedrockRuntimeProtocol
from .notification.email import SESClientProtocol

configure_logging()
LOGGER = get_logger(__name__)


def run_snapshot_pipeline(
    environ: Mapping[str, str] | None = None,
    s3_client: S3Client | None = None,
    clock: Callable[[], datetime] | None = None,
    bedrock_runtime_client: BedrockRuntimeProtocol | None = None,
    ses_client: SESClientProtocol | None = None,
    collector: CollectorProtocol | None = None,
) -> dict[str, Any]:
    """Execute the autonomous pipeline while preserving snapshot result fields."""
    config = Config.from_env(environ)
    LOGGER.info(
        "Configuration loaded provider=%s region=%s",
        config.provider,
        config.aws_region,
    )
    return AutonomousPipeline(
        config=config,
        environ=environ,
        s3_client=s3_client,
        bedrock_runtime_client=bedrock_runtime_client,
        ses_client=ses_client,
        clock=clock,
        collector=collector,
    ).run()


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
