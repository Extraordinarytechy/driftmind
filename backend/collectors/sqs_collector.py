"""Read-only Amazon SQS queue collector."""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote, urlparse

from collectors import log_api_failure, policy
from models import SnapshotResource


class SQSCollector:
    """Collect stable SQS queue configuration."""

    service = "sqs"
    _FIELDS = (
        "QueueArn", "VisibilityTimeout", "MaximumMessageSize", "MessageRetentionPeriod",
        "DelaySeconds", "ReceiveMessageWaitTimeSeconds", "KmsMasterKeyId",
        "KmsDataKeyReusePeriodSeconds", "SqsManagedSseEnabled", "FifoQueue",
        "ContentBasedDeduplication", "DeduplicationScope", "FifoThroughputLimit",
    )

    def __init__(self, client: Any) -> None:
        self._client = client

    def collect(self) -> list[SnapshotResource]:
        operation = "list_queues"
        try:
            pages = self._client.get_paginator(operation).paginate()
            resources: list[SnapshotResource] = []
            for page in pages:
                for queue_url in page.get("QueueUrls", []):
                    operation = "get_queue_attributes"
                    response = self._client.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["All"])
                    attributes = response.get("Attributes", {})
                    if not isinstance(attributes, dict):
                        raise ValueError("invalid SQS attributes")
                    properties = {field: attributes[field] for field in self._FIELDS if field in attributes}
                    for field in ("Policy", "RedrivePolicy", "RedriveAllowPolicy"):
                        if field in attributes:
                            properties[field] = policy(attributes[field])
                    name = unquote(urlparse(str(queue_url)).path.rstrip("/").split("/")[-1])
                    if not name:
                        raise ValueError("invalid SQS response")
                    resources.append(SnapshotResource("AWS::SQS::Queue", name, properties))
            resources.sort(key=lambda resource: (resource.resource_type, resource.logical_name))
            return resources
        except Exception as error:
            log_api_failure(self.service, operation, error)
            return []
