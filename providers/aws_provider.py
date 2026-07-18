"""Reserved AWS provider boundary for a future implementation phase."""

from __future__ import annotations

from collections.abc import Sequence

from models import SnapshotResource
from providers.base import InfrastructureProvider


class AWSProvider(InfrastructureProvider):
    """Placeholder for future read-only AWS API collection."""

    @property
    def name(self) -> str:
        return "aws"

    @property
    def environment(self) -> str:
        return "aws"

    def collect_resources(self) -> Sequence[SnapshotResource]:
        raise NotImplementedError("AWSProvider is not implemented in Phase 2")
