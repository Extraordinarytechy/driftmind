"""Provider loading and validated snapshot generation."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from logger import get_logger
from models import SCHEMA_VERSION, Snapshot
from providers.aws_provider import AWSProvider
from providers.base import InfrastructureProvider
from providers.demo_provider import DemoProvider

LOGGER = get_logger(__name__)


class ProviderError(ValueError):
    """Raised when a provider cannot be loaded or collected."""


def load_provider(provider_name: str) -> InfrastructureProvider:
    """Load a configured provider by its normalized name."""
    normalized_name = provider_name.strip().lower()
    providers: dict[str, type[InfrastructureProvider]] = {
        "demo": DemoProvider,
        "aws": AWSProvider,
    }
    provider_type = providers.get(normalized_name)
    if provider_type is None:
        raise ProviderError(f"Unsupported provider: {provider_name!r}")

    provider = provider_type()
    LOGGER.info("Provider loaded provider=%s", provider.name)
    return provider


def format_utc_timestamp(value: datetime) -> str:
    """Format an aware datetime as an ISO 8601 UTC timestamp."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ProviderError("Snapshot clock must return a timezone-aware datetime")
    utc_value = value.astimezone(timezone.utc)
    return utc_value.isoformat(timespec="microseconds").replace("+00:00", "Z")


class SnapshotCollector:
    """Load a provider and generate a complete, validated snapshot."""

    def __init__(
        self,
        provider_name: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._provider_name = provider_name
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def collect(self) -> Snapshot:
        """Collect normalized resources and return a validated snapshot."""
        provider = load_provider(self._provider_name)
        resources = list(provider.collect_resources())
        snapshot = Snapshot(
            schema_version=SCHEMA_VERSION,
            generated_at=format_utc_timestamp(self._clock()),
            provider=provider.name,
            environment=provider.environment,
            resources=resources,
        )
        LOGGER.info(
            "Snapshot generated provider=%s resource_count=%d",
            snapshot.provider,
            len(snapshot.resources),
        )
        snapshot.validate()
        LOGGER.info(
            "Snapshot validation successful schema_version=%s resource_count=%d",
            snapshot.schema_version,
            len(snapshot.resources),
        )
        return snapshot
