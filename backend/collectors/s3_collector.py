"""Read-only Amazon S3 bucket collector."""

from __future__ import annotations

from typing import Any

from collectors import error_code, log_api_failure, normalize
from models import SnapshotResource


class S3Collector:
    """Collect buckets in one region and their stable configuration."""

    service = "s3"
    _NOT_CONFIGURED = {
        "get_bucket_encryption": {"ServerSideEncryptionConfigurationNotFoundError"},
        "get_public_access_block": {"NoSuchPublicAccessBlockConfiguration"},
        "get_bucket_tagging": {"NoSuchTagSet"},
    }

    def __init__(self, client: Any, region: str) -> None:
        self._client = client
        self._region = region

    def _optional(self, operation: str, bucket: str) -> dict[str, Any]:
        try:
            response = getattr(self._client, operation)(Bucket=bucket)
            if not isinstance(response, dict):
                raise ValueError("invalid S3 response")
            return response
        except Exception as error:
            if error_code(error) in self._NOT_CONFIGURED.get(operation, set()):
                return {}
            raise

    @staticmethod
    def _region_name(value: Any) -> str:
        if value in (None, ""):
            return "us-east-1"
        if value == "EU":
            return "eu-west-1"
        return str(value)

    def collect(self) -> list[SnapshotResource]:
        operation = "list_buckets"
        try:
            response = self._client.list_buckets()
            resources: list[SnapshotResource] = []
            for bucket in response.get("Buckets", []):
                name = bucket.get("Name")
                if not isinstance(name, str) or not name:
                    raise ValueError("invalid S3 response")
                operation = "get_bucket_location"
                location = self._client.get_bucket_location(Bucket=name)
                region = self._region_name(location.get("LocationConstraint"))
                if region != self._region:
                    continue
                operation = "get_bucket_versioning"
                versioning = self._client.get_bucket_versioning(Bucket=name)
                operation = "get_bucket_encryption"
                encryption = self._optional(operation, name)
                operation = "get_public_access_block"
                public_access = self._optional(operation, name)
                operation = "get_bucket_tagging"
                tagging = self._optional(operation, name)
                properties: dict[str, Any] = {"Region": region}
                properties["Versioning"] = {
                    key: versioning[key] for key in ("Status", "MFADelete") if key in versioning
                }
                configuration = encryption.get("ServerSideEncryptionConfiguration", {})
                rules = configuration.get("Rules", []) if isinstance(configuration, dict) else []
                properties["EncryptionRules"] = normalize(rules, sort_lists=True)
                block = public_access.get("PublicAccessBlockConfiguration", {})
                properties["PublicAccessBlock"] = normalize(block) if isinstance(block, dict) else {}
                tags = tagging.get("TagSet", [])
                properties["Tags"] = normalize(tags, sort_lists=True)
                resources.append(SnapshotResource("AWS::S3::Bucket", name, properties))
            resources.sort(key=lambda resource: (resource.resource_type, resource.logical_name))
            return resources
        except Exception as error:
            log_api_failure(self.service, operation, error)
            return []
