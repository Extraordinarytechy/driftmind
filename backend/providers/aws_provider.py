"""Production read-only AWS infrastructure provider."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from typing import Any

from collectors.cloudwatch_collector import CloudWatchAlarmCollector
from collectors.dynamodb_collector import DynamoDBCollector
from collectors.eventbridge_collector import EventBridgeCollector
from collectors.iam_collector import IAMCollector
from collectors.lambda_collector import LambdaCollector
from collectors.s3_collector import S3Collector
from collectors.sns_collector import SNSCollector
from collectors.sqs_collector import SQSCollector
from logger import get_logger
from models import SnapshotResource
from providers.base import InfrastructureProvider

LOGGER = get_logger(__name__)


class AWSIdentityError(RuntimeError):
    """Raised when the AWS account and region cannot be safely identified."""


class AWSProvider(InfrastructureProvider):
    """Orchestrate independent read-only collectors through one lazy session."""

    def __init__(
        self,
        session: Any | None = None,
        clients: Mapping[str, Any] | None = None,
        collector_factories: Sequence[tuple[str, Any]] | None = None,
    ) -> None:
        self._session = session
        self._clients = dict(clients or {})
        self._environment: str | None = None
        self._identity_error: AWSIdentityError | None = None
        self._collector_factories = tuple(collector_factories) if collector_factories is not None else (
            ("lambda", LambdaCollector),
            ("s3", S3Collector),
            ("iam", IAMCollector),
            ("dynamodb", DynamoDBCollector),
            ("cloudwatch", CloudWatchAlarmCollector),
            ("events", EventBridgeCollector),
            ("sns", SNSCollector),
            ("sqs", SQSCollector),
        )

    @property
    def name(self) -> str:
        return "aws"

    def _get_session(self) -> Any:
        if self._session is None:
            import boto3

            self._session = boto3.Session()
        return self._session

    @property
    def region(self) -> str:
        configured = os.environ.get("AWS_REGION", "").strip()
        region = configured or str(getattr(self._get_session(), "region_name", "") or "").strip()
        if not region or re.fullmatch(r"[A-Za-z0-9-]+", region) is None:
            error = AWSIdentityError("AWS identity could not be established")
            LOGGER.error(
                "AWS identity failed service=sts operation=get_caller_identity error_type=%s",
                type(error).__name__,
            )
            raise error
        return region

    def _client(self, service: str) -> Any:
        if service not in self._clients:
            self._clients[service] = self._get_session().client(service, region_name=self.region)
        return self._clients[service]

    @property
    def environment(self) -> str:
        if self._environment is not None:
            return self._environment
        if self._identity_error is not None:
            raise self._identity_error
        try:
            region = self.region
            response = self._client("sts").get_caller_identity()
            account = response.get("Account") if isinstance(response, dict) else None
            if not isinstance(account, str) or re.fullmatch(r"[0-9]{12}", account) is None:
                raise ValueError("invalid identity response")
            self._environment = f"aws:{account}:{region}"
            return self._environment
        except Exception as error:
            if isinstance(error, AWSIdentityError):
                identity_error = error
            else:
                identity_error = AWSIdentityError("AWS identity could not be established")
                LOGGER.error(
                    "AWS identity failed service=sts operation=get_caller_identity error_type=%s",
                    type(error).__name__,
                )
            self._identity_error = identity_error
            if identity_error is error:
                raise identity_error
            raise identity_error from error

    def collect_resources(self) -> Sequence[SnapshotResource]:
        self.environment
        resources: list[SnapshotResource] = []
        for service, factory in self._collector_factories:
            try:
                client = self._client(service)
                collector = factory(client, self.region) if service == "s3" else factory(client)
                collected = list(collector.collect())
                for resource in collected:
                    if not isinstance(resource, SnapshotResource):
                        raise TypeError("collector returned invalid resource")
                    resource.validate()
                resources.extend(collected)
            except Exception as error:
                LOGGER.error(
                    "AWS collector failed service=%s operation=collect error_type=%s",
                    service,
                    type(error).__name__,
                )
        resources.sort(key=lambda resource: (resource.resource_type, resource.logical_name))
        return resources
