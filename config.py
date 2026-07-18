"""Environment-based configuration for the snapshot pipeline."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


class ConfigurationError(ValueError):
    """Raised when required runtime configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class Config:
    """Validated runtime configuration loaded exclusively from the environment."""

    snapshot_bucket: str
    aws_region: str
    provider: str

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Config":
        """Load and validate configuration from environment variables."""
        source = os.environ if environ is None else environ
        values = {
            "SNAPSHOT_BUCKET": source.get("SNAPSHOT_BUCKET", "").strip(),
            "AWS_REGION": source.get("AWS_REGION", "").strip(),
            "PROVIDER": source.get("PROVIDER", "").strip().lower(),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ConfigurationError(
                f"Missing required environment variable(s): {', '.join(missing)}"
            )

        return cls(
            snapshot_bucket=values["SNAPSHOT_BUCKET"],
            aws_region=values["AWS_REGION"],
            provider=values["PROVIDER"],
        )
