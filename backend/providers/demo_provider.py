"""Deterministic provider used for local execution and development."""

from __future__ import annotations

from collections.abc import Sequence

from models import SnapshotResource
from providers.base import InfrastructureProvider


class DemoProvider(InfrastructureProvider):
    """Return a stable set of representative, non-account AWS resources."""

    @property
    def name(self) -> str:
        return "demo"

    @property
    def environment(self) -> str:
        return "demo"

    def collect_resources(self) -> Sequence[SnapshotResource]:
        return (
            SnapshotResource(
                resource_type="AWS::EC2::Instance",
                logical_name="demo-web-server",
                properties={
                    "instance_type": "t3.micro",
                    "state": "running",
                    "tags": {"Environment": "demo", "Name": "demo-web-server"},
                },
            ),
            SnapshotResource(
                resource_type="AWS::EC2::SecurityGroup",
                logical_name="demo-web-security-group",
                properties={
                    "description": "Demo HTTPS ingress",
                    "ingress": [
                        {
                            "cidr": "0.0.0.0/0",
                            "from_port": 443,
                            "protocol": "tcp",
                            "to_port": 443,
                        }
                    ],
                },
            ),
            SnapshotResource(
                resource_type="AWS::S3::Bucket",
                logical_name="demo-artifacts-bucket",
                properties={"encryption": "AES256", "versioning": True},
            ),
        )
