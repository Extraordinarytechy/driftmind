"""Orchestration service for report formatting and SES delivery."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Protocol

from logger import get_logger

from ..ai.models import ExecutiveAnalysis
from .email import SESEmailClient, SESClientProtocol
from .formatter import format_notification
from .models import NotificationRequest, NotificationResult

LOGGER = get_logger(__name__)


class NotificationClientProtocol(Protocol):
    """Delivery behavior required by the notification service."""

    def send(self, request: NotificationRequest) -> NotificationResult:
        """Send one formatted notification."""


class NotificationService:
    """Format a validated analysis and deliver it through SES."""

    def __init__(
        self,
        client: NotificationClientProtocol,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        ses_client: SESClientProtocol | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> "NotificationService":
        """Create a service from environment-only SES configuration."""
        return cls(
            client=SESEmailClient(environ=environ, ses_client=ses_client),
            clock=clock,
        )

    def notify(self, analysis: ExecutiveAnalysis) -> NotificationResult:
        """Format a validated analysis and return its SES delivery result."""
        try:
            LOGGER.info(
                "Formatting started recommendation_count=%d",
                len(analysis.recommendations),
            )
            request = format_notification(analysis, self._clock())
            LOGGER.info(
                "Formatting successful text_chars=%d html_chars=%d",
                len(request.text_body),
                len(request.html_body),
            )
            result = self._client.send(request)
            result.validate()
            LOGGER.info(
                "Notification delivery successful message_id=%s",
                result.message_id,
            )
            return result
        except Exception as exc:
            LOGGER.error(
                "Notification delivery failed error_type=%s", type(exc).__name__
            )
            raise
