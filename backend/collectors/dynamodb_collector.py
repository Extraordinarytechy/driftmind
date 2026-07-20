"""Read-only Amazon DynamoDB table collector."""

from __future__ import annotations

from typing import Any

from collectors import log_api_failure, normalize, selected
from models import SnapshotResource


class DynamoDBCollector:
    """Collect stable DynamoDB table configuration."""

    service = "dynamodb"

    def __init__(self, client: Any) -> None:
        self._client = client

    @staticmethod
    def _index(index: dict[str, Any]) -> dict[str, Any]:
        result = selected(index, ("IndexName", "KeySchema", "Projection"))
        if "KeySchema" in result:
            result["KeySchema"] = normalize(result["KeySchema"], sort_lists=True)
        projection = result.get("Projection")
        if isinstance(projection, dict) and "NonKeyAttributes" in projection:
            projection["NonKeyAttributes"] = sorted(projection["NonKeyAttributes"])
        return result

    def collect(self) -> list[SnapshotResource]:
        operation = "list_tables"
        try:
            pages = self._client.get_paginator(operation).paginate()
            resources: list[SnapshotResource] = []
            for page in pages:
                for table_name in page.get("TableNames", []):
                    operation = "describe_table"
                    response = self._client.describe_table(TableName=table_name)
                    table = response.get("Table")
                    if not isinstance(table, dict):
                        raise ValueError("invalid DynamoDB response")
                    properties = selected(
                        table,
                        ("TableArn", "TableId", "DeletionProtectionEnabled", "MultiRegionConsistency"),
                    )
                    for field in ("AttributeDefinitions", "KeySchema"):
                        if field in table:
                            properties[field] = normalize(table[field], sort_lists=True)
                    billing = table.get("BillingModeSummary")
                    if isinstance(billing, dict) and "BillingMode" in billing:
                        properties["BillingMode"] = billing["BillingMode"]
                    for field in ("LocalSecondaryIndexes", "GlobalSecondaryIndexes"):
                        if field in table:
                            properties[field] = sorted(
                                (self._index(index) for index in table[field]),
                                key=lambda index: str(index.get("IndexName", "")),
                            )
                    sse = table.get("SSEDescription")
                    if isinstance(sse, dict):
                        properties["SSE"] = selected(sse, ("SSEType", "KMSMasterKeyArn"))
                    stream = table.get("StreamSpecification")
                    if isinstance(stream, dict):
                        properties["StreamSpecification"] = selected(stream, ("StreamEnabled", "StreamViewType"))
                    table_class = table.get("TableClassSummary")
                    if isinstance(table_class, dict) and "TableClass" in table_class:
                        properties["TableClass"] = table_class["TableClass"]
                    replicas = table.get("Replicas")
                    if isinstance(replicas, list):
                        stable = [selected(replica, ("RegionName", "KMSMasterKeyId")) for replica in replicas]
                        properties["Replicas"] = sorted(stable, key=lambda item: str(item.get("RegionName", "")))
                    resources.append(SnapshotResource("AWS::DynamoDB::Table", str(table_name), properties))
            resources.sort(key=lambda resource: (resource.resource_type, resource.logical_name))
            return resources
        except Exception as error:
            log_api_failure(self.service, operation, error)
            return []
