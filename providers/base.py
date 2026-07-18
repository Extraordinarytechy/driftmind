"""Provider interface for infrastructure resource collection."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from models import SnapshotResource


class InfrastructureProvider(ABC):
    """Abstract source of normalized infrastructure resources."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider identifier stored in the snapshot."""

    @property
    @abstractmethod
    def environment(self) -> str:
        """Return the environment identifier stored in the snapshot."""

    @abstractmethod
    def collect_resources(self) -> Sequence[SnapshotResource]:
        """Return a complete collection of normalized resources."""
