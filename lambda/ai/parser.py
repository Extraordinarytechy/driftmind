"""Strict parsing and validation of Bedrock executive analysis JSON."""

from __future__ import annotations

import json
from typing import Any

from logger import get_logger

from .models import ExecutiveAnalysis, Recommendation, ValidationError

LOGGER = get_logger(__name__)
_REQUIRED_FIELDS = {
    "summary",
    "security_impact",
    "operational_impact",
    "cost_impact",
    "recommendations",
}


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"Model response contains duplicate field: {key}")
        result[key] = value
    return result


def _reject_nonstandard_constant(value: str) -> None:
    raise ValidationError(f"Model response contains invalid JSON constant: {value}")


def _decode_payload(payload: str | bytes) -> str:
    if isinstance(payload, bytes):
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError("Model response must be UTF-8 encoded") from exc
    if not isinstance(payload, str):
        raise ValidationError("Model response must be text or bytes")
    return payload


def parse_executive_analysis(payload: str | bytes) -> ExecutiveAnalysis:
    """Parse strict JSON and return a validated ExecutiveAnalysis."""
    text = _decode_payload(payload)
    LOGGER.info("Model response parsing started response_chars=%d", len(text))
    try:
        document = json.loads(
            text,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_nonstandard_constant,
        )
    except json.JSONDecodeError as exc:
        LOGGER.error("Model response validation failed reason=malformed_json")
        raise ValidationError("Model response is not valid JSON") from exc

    except ValidationError:
        LOGGER.error("Model response validation failed reason=nonstandard_json")
        raise

    if not isinstance(document, dict):
        LOGGER.error("Model response validation failed reason=non_object")
        raise ValidationError("Model response root must be a JSON object")

    actual_fields = set(document)
    if actual_fields != _REQUIRED_FIELDS:
        missing = sorted(_REQUIRED_FIELDS - actual_fields)
        unexpected = sorted(actual_fields - _REQUIRED_FIELDS)
        details: list[str] = []
        if missing:
            details.append(f"missing={missing}")
        if unexpected:
            details.append(f"unexpected={unexpected}")
        LOGGER.error("Model response validation failed reason=invalid_fields")
        raise ValidationError(
            f"Model response fields are invalid: {', '.join(details)}"
        )

    recommendations_data = document["recommendations"]
    if not isinstance(recommendations_data, list):
        LOGGER.error("Model response validation failed reason=recommendations_type")
        raise ValidationError("recommendations must be an array of strings")
    recommendations: list[Recommendation] = []
    for index, item in enumerate(recommendations_data):
        if not isinstance(item, str) or not item.strip():
            LOGGER.error(
                "Model response validation failed reason=recommendation_item index=%d",
                index,
            )
            raise ValidationError(
                f"recommendations[{index}] must be a non-empty string"
            )
        recommendations.append(Recommendation(text=item))

    analysis = ExecutiveAnalysis(
        summary=document["summary"],
        security_impact=document["security_impact"],
        operational_impact=document["operational_impact"],
        cost_impact=document["cost_impact"],
        recommendations=tuple(recommendations),
    )
    try:
        analysis.validate()
    except ValidationError:
        LOGGER.error("Model response validation failed reason=field_type")
        raise

    LOGGER.info("Model response validation successful")
    LOGGER.info(
        "Model response parsing successful recommendation_count=%d",
        len(analysis.recommendations),
    )
    return analysis
