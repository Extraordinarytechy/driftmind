"""Environment-configured Amazon Bedrock Runtime client wrapper."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from logger import get_logger

LOGGER = get_logger(__name__)
_DEFAULT_TEMPERATURE = 0.0
_DEFAULT_MAX_TOKENS = 1024


class BedrockConfigurationError(ValueError):
    """Raised when Bedrock environment configuration is invalid."""


class BedrockInvocationError(RuntimeError):
    """Raised when Bedrock cannot return a usable text response."""


class BedrockRuntimeProtocol(Protocol):
    """Narrow protocol for the boto3 Bedrock Runtime client."""

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        """Invoke a model through the Bedrock Converse API."""


@dataclass(frozen=True, slots=True)
class BedrockConfig:
    """Validated Bedrock settings sourced exclusively from environment values."""

    region: str
    model_id: str
    temperature: float
    max_tokens: int

    @classmethod
    def from_env(
        cls, environ: Mapping[str, str] | None = None
    ) -> "BedrockConfig":
        """Load required and optional Bedrock settings from the environment."""
        source = os.environ if environ is None else environ
        region = source.get("AWS_REGION", "").strip()
        model_id = source.get("BEDROCK_MODEL_ID", "").strip()
        missing = [
            name
            for name, value in (("AWS_REGION", region), ("BEDROCK_MODEL_ID", model_id))
            if not value
        ]

        if missing:
            raise BedrockConfigurationError(
                f"Missing required environment variable(s): {', '.join(missing)}"
            )

        temperature_text = source.get(
            "BEDROCK_TEMPERATURE", str(_DEFAULT_TEMPERATURE)
        ).strip()
        max_tokens_text = source.get(
            "BEDROCK_MAX_TOKENS", str(_DEFAULT_MAX_TOKENS)
        ).strip()
        try:
            temperature = float(temperature_text)
        except ValueError as exc:
            raise BedrockConfigurationError(
                "BEDROCK_TEMPERATURE must be a number"
            ) from exc
        if not math.isfinite(temperature) or not 0.0 <= temperature <= 1.0:
            raise BedrockConfigurationError(
                "BEDROCK_TEMPERATURE must be between 0.0 and 1.0"
            )
        try:
            max_tokens = int(max_tokens_text)
        except ValueError as exc:
            raise BedrockConfigurationError(
                "BEDROCK_MAX_TOKENS must be an integer"
            ) from exc
        if max_tokens <= 0:
            raise BedrockConfigurationError(
                "BEDROCK_MAX_TOKENS must be greater than zero"
            )
        return cls(
            region=region,
            model_id=model_id,
            temperature=temperature,
            max_tokens=max_tokens,
        )


@dataclass(frozen=True, slots=True)
class BedrockResponse:
    """Structured metadata and text returned by a Bedrock invocation."""

    text: str
    request_id: str | None
    stop_reason: str | None


class BedrockClient:
    """Invoke one environment-configured model through Bedrock Runtime."""

    def __init__(
        self,
        environ: Mapping[str, str] | None = None,
        runtime_client: BedrockRuntimeProtocol | None = None,
    ) -> None:
        self._config = BedrockConfig.from_env(environ)
        self._runtime_client = (
            runtime_client
            if runtime_client is not None
            else self._create_runtime_client(self._config.region)
        )
        LOGGER.info(
            "Bedrock client initialized region=%s model_id=%s",
            self._config.region,
            self._config.model_id,
        )

    @staticmethod
    def _create_runtime_client(region: str) -> BedrockRuntimeProtocol:
        try:
            import boto3
        except ModuleNotFoundError as exc:
            raise BedrockConfigurationError(
                "boto3 is required when a Bedrock Runtime client is not injected"
            ) from exc
        return boto3.client("bedrock-runtime", region_name=region)

    @staticmethod
    def _extract_text(response: dict[str, Any]) -> str:
        try:
            content = response["output"]["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise BedrockInvocationError(
                "Bedrock response did not contain model content"
            ) from exc
        if not isinstance(content, list):
            raise BedrockInvocationError("Bedrock model content must be an array")
        text_parts = [
            block["text"]
            for block in content
            if isinstance(block, dict)
            and isinstance(block.get("text"), str)
            and block["text"]
        ]
        if not text_parts:
            raise BedrockInvocationError("Bedrock response contained no text")
        return "".join(text_parts)

    def invoke(self, prompt: str) -> BedrockResponse:
        """Invoke Bedrock and return a structured response without credential data."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise BedrockInvocationError("Prompt must be a non-empty string")
        LOGGER.info(
            "Model invocation started model_id=%s prompt_chars=%d",
            self._config.model_id,
            len(prompt),
        )
        try:
            response = self._runtime_client.converse(
                modelId=self._config.model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={
                    "temperature": self._config.temperature,
                    "maxTokens": self._config.max_tokens,
                },
            )
            text = self._extract_text(response)
            metadata = response.get("ResponseMetadata", {})
            request_id = (
                metadata.get("RequestId") if isinstance(metadata, dict) else None
            )
            stop_reason = response.get("stopReason")
        except BedrockInvocationError:
            LOGGER.error("Model invocation failed reason=invalid_response")
            raise
        except Exception as exc:
            response = getattr(exc, "response", None)
            error_details = response.get("Error") if isinstance(response, dict) else None
            if isinstance(error_details, dict):
                error_code = str(error_details.get("Code", ""))
                error_message = str(error_details.get("Message", ""))
                LOGGER.error(
                    "Model invocation failed error_type=%s aws_error_code=%s aws_error_message=%s",
                    type(exc).__name__,
                    error_code,
                    error_message,
                )
            else:
                LOGGER.error(
                    "Model invocation failed error_type=%s", type(exc).__name__
                )
            raise BedrockInvocationError("Bedrock model invocation failed") from None

        LOGGER.info(
            "Model invocation successful request_id=%s stop_reason=%s",
            request_id or "unavailable",
            stop_reason or "unavailable",
        )
        return BedrockResponse(
            text=text,
            request_id=request_id,
            stop_reason=stop_reason if isinstance(stop_reason, str) else None,
        )
