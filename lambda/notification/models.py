"""Typed request and result models for notification delivery."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


class NotificationValidationError(ValueError):
    """Raised when notification data violates its delivery contract."""


def _require_nonempty_text(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise NotificationValidationError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class NotificationRequest:
    """A fully formatted multipart email request."""

    subject: str
    text_body: str
    html_body: str

    def validate(self) -> None:
        """Validate safe headers and non-empty alternatives."""
        _require_nonempty_text(self.subject, "subject")
        _require_nonempty_text(self.text_body, "text_body")
        _require_nonempty_text(self.html_body, "html_body")
        if "\r" in self.subject or "\n" in self.subject:
            raise NotificationValidationError("subject must not contain newlines")


@dataclass(frozen=True, slots=True)
class NotificationResult:
    """Successful SES delivery metadata safe to expose to callers."""

    message_id: str
    status: Literal["sent"] = "sent"

    def validate(self) -> None:
        """Validate successful delivery metadata."""
        _require_nonempty_text(self.message_id, "message_id")
        if self.status != "sent":
            raise NotificationValidationError("status must be 'sent'")

    def to_dict(self) -> dict[str, str]:
        """Return delivery metadata safe for structured responses."""
        self.validate()
        return {"message_id": self.message_id, "status": self.status}
