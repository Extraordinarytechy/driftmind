"""Typed models for validated Bedrock executive analysis output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ValidationError(ValueError):
    """Raised when model output violates the executive analysis contract."""


def _validate_text(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class Recommendation:
    """One grounded review action returned by the model."""

    text: str

    def validate(self) -> None:
        """Validate recommendation text."""
        _validate_text(self.text, "recommendation")


@dataclass(frozen=True, slots=True)
class ExecutiveAnalysis:
    """Strict, typed representation of the Bedrock JSON response."""

    summary: str
    security_impact: str
    operational_impact: str
    cost_impact: str
    recommendations: tuple[Recommendation, ...]

    def validate(self) -> None:
        """Validate all required fields and recommendation models."""
        _validate_text(self.summary, "summary")
        _validate_text(self.security_impact, "security_impact")
        _validate_text(self.operational_impact, "operational_impact")
        _validate_text(self.cost_impact, "cost_impact")
        if not isinstance(self.recommendations, tuple):
            raise ValidationError("recommendations must be a tuple")
        for recommendation in self.recommendations:
            if not isinstance(recommendation, Recommendation):
                raise ValidationError(
                    "recommendations must contain Recommendation models"
                )
            recommendation.validate()

    def to_dict(self) -> dict[str, Any]:
        """Return the exact JSON response schema."""
        self.validate()
        return {
            "summary": self.summary,
            "security_impact": self.security_impact,
            "operational_impact": self.operational_impact,
            "cost_impact": self.cost_impact,
            "recommendations": [
                recommendation.text for recommendation in self.recommendations
            ],
        }
