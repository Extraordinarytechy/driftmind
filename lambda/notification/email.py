"""Environment-configured Amazon SES multipart email client."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from dataclasses import dataclass
from email import policy
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr
from typing import Any, Protocol

from logger import get_logger

from .models import NotificationRequest, NotificationResult

LOGGER = get_logger(__name__)


class SESConfigurationError(ValueError):
    """Raised when required SES environment configuration is invalid."""


class SESDeliveryError(RuntimeError):
    """Raised when SES cannot accept a notification for delivery."""


class SESClientProtocol(Protocol):
    """Narrow protocol for the boto3 SES client."""

    def send_raw_email(self, **kwargs: Any) -> dict[str, Any]:
        """Send one raw MIME email through SES."""


def _validate_address(value: str, variable_name: str) -> None:
    if "\r" in value or "\n" in value:
        raise SESConfigurationError(f"{variable_name} must not contain newlines")
    display_name, address = parseaddr(value)
    if display_name or address != value or "@" not in address:
        raise SESConfigurationError(
            f"{variable_name} must contain one plain email address"
        )
    local_part, domain = address.rsplit("@", 1)
    if not local_part or not domain or any(character.isspace() for character in address):
        raise SESConfigurationError(
            f"{variable_name} must contain one valid email address"
        )


@dataclass(frozen=True, slots=True)
class SESConfig:
    """Validated SES settings sourced exclusively from environment values."""

    region: str
    sender: str
    recipient: str

    @classmethod
    def from_env(
        cls, environ: Mapping[str, str] | None = None
    ) -> "SESConfig":
        """Load SES Region and identities from required environment variables."""
        source = os.environ if environ is None else environ
        values = {
            "AWS_REGION": source.get("AWS_REGION", "").strip(),
            "SES_SENDER": source.get("SES_SENDER", "").strip(),
            "SES_RECIPIENT": source.get("SES_RECIPIENT", "").strip(),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise SESConfigurationError(
                f"Missing required environment variable(s): {', '.join(missing)}"
            )
        _validate_address(values["SES_SENDER"], "SES_SENDER")
        _validate_address(values["SES_RECIPIENT"], "SES_RECIPIENT")
        return cls(
            region=values["AWS_REGION"],
            sender=values["SES_SENDER"],
            recipient=values["SES_RECIPIENT"],
        )


def _build_multipart_message(
    request: NotificationRequest,
    sender: str,
    recipient: str,
) -> bytes:
    request.validate()
    boundary_material = "\0".join(
        (request.subject, request.text_body, request.html_body)
    ).encode("utf-8")
    boundary = f"driftmind-{hashlib.sha256(boundary_material).hexdigest()[:24]}"
    message = MIMEMultipart("alternative", boundary=boundary)
    message["Subject"] = request.subject
    message["From"] = sender
    message["To"] = recipient
    message.attach(MIMEText(request.text_body, "plain", "utf-8"))
    message.attach(MIMEText(request.html_body, "html", "utf-8"))
    return message.as_bytes(policy=policy.SMTP)


class SESEmailClient:
    """Generate and send one multipart report through Amazon SES."""

    def __init__(
        self,
        environ: Mapping[str, str] | None = None,
        ses_client: SESClientProtocol | None = None,
    ) -> None:
        self._config = SESConfig.from_env(environ)
        self._ses_client = (
            ses_client
            if ses_client is not None
            else self._create_ses_client(self._config.region)
        )
        LOGGER.info("SES client initialized region=%s", self._config.region)

    @staticmethod
    def _create_ses_client(region: str) -> SESClientProtocol:
        try:
            import boto3
        except ModuleNotFoundError as exc:
            raise SESConfigurationError(
                "boto3 is required when an SES client is not injected"
            ) from exc
        return boto3.client("ses", region_name=region)

    def send(self, request: NotificationRequest) -> NotificationResult:
        """Generate a multipart message and submit it to SES."""
        LOGGER.info("Email generation started")
        raw_message = _build_multipart_message(
            request,
            sender=self._config.sender,
            recipient=self._config.recipient,
        )
        LOGGER.info("Email generation successful message_bytes=%d", len(raw_message))
        LOGGER.info("SES send attempt recipient_count=1")
        try:
            response = self._ses_client.send_raw_email(
                Source=self._config.sender,
                Destinations=[self._config.recipient],
                RawMessage={"Data": raw_message},
            )
        except Exception as exc:
            LOGGER.error("Delivery failure error_type=%s", type(exc).__name__)
            raise SESDeliveryError("SES notification delivery failed") from None

        message_id = response.get("MessageId") if isinstance(response, dict) else None
        if not isinstance(message_id, str) or not message_id.strip():
            LOGGER.error("Delivery failure reason=missing_message_id")
            raise SESDeliveryError("SES response did not contain a message ID")

        result = NotificationResult(message_id=message_id)
        result.validate()
        LOGGER.info("Delivery success message_id=%s", result.message_id)
        return result
