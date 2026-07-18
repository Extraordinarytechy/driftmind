"""Orchestration service for grounded Bedrock infrastructure analysis."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from logger import get_logger

from ..diff.models import ChangeReport
from .client import BedrockClient, BedrockResponse, BedrockRuntimeProtocol
from .models import ExecutiveAnalysis
from .parser import parse_executive_analysis
from .prompt import PROMPT_VERSION, build_prompt

LOGGER = get_logger(__name__)


class IntelligenceClientProtocol(Protocol):
    """Client behavior required by the intelligence service."""

    def invoke(self, prompt: str) -> BedrockResponse:
        """Invoke the configured intelligence model."""


class IntelligenceService:
    """Build prompts, invoke Bedrock, and validate model output."""

    def __init__(self, client: IntelligenceClientProtocol) -> None:
        self._client = client

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        runtime_client: BedrockRuntimeProtocol | None = None,
    ) -> "IntelligenceService":
        """Create a service from environment-only Bedrock configuration."""
        return cls(BedrockClient(environ=environ, runtime_client=runtime_client))

    def analyze(self, report: ChangeReport) -> ExecutiveAnalysis:
        """Transform one deterministic diff report into validated analysis."""
        try:
            prompt = build_prompt(report)
            LOGGER.info(
                "Prompt creation successful prompt_version=%s change_count=%d",
                PROMPT_VERSION,
                report.summary.total_changes,
            )
            response = self._client.invoke(prompt)
            analysis = parse_executive_analysis(response.text)
            LOGGER.info(
                "Executive analysis parsing successful recommendation_count=%d",
                len(analysis.recommendations),
            )
            return analysis
        except Exception as exc:
            LOGGER.error(
                "Intelligence analysis failed error_type=%s", type(exc).__name__
            )
            raise
