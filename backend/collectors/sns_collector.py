"""Read-only Amazon SNS topic collector."""

from __future__ import annotations

from typing import Any

from collectors import log_api_failure, policy
from models import SnapshotResource


class SNSCollector:
    """Collect stable SNS topic configuration."""

    service = "sns"
    _STRING_FIELDS = (
        "DisplayName", "KmsMasterKeyId", "FifoTopic", "ContentBasedDeduplication",
        "SignatureVersion", "TracingConfig",
    )

    def __init__(self, client: Any) -> None:
        self._client = client

    def collect(self) -> list[SnapshotResource]:
        operation = "list_topics"
        try:
            pages = self._client.get_paginator(operation).paginate()
            resources: list[SnapshotResource] = []
            for page in pages:
                for topic in page.get("Topics", []):
                    arn = topic.get("TopicArn")
                    if not isinstance(arn, str) or not arn:
                        raise ValueError("invalid SNS response")
                    operation = "get_topic_attributes"
                    response = self._client.get_topic_attributes(TopicArn=arn)
                    attributes = response.get("Attributes", {})
                    if not isinstance(attributes, dict):
                        raise ValueError("invalid SNS attributes")
                    properties = {field: attributes[field] for field in self._STRING_FIELDS if field in attributes}
                    properties["TopicArn"] = arn
                    for field in ("Policy", "DeliveryPolicy"):
                        if field in attributes:
                            properties[field] = policy(attributes[field])
                    resources.append(SnapshotResource("AWS::SNS::Topic", arn, properties))
            resources.sort(key=lambda resource: (resource.resource_type, resource.logical_name))
            return resources
        except Exception as error:
            log_api_failure(self.service, operation, error)
            return []
