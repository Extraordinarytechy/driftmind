"""Read-only Amazon CloudWatch alarm collector."""

from __future__ import annotations

from typing import Any

from collectors import log_api_failure, normalize, selected
from models import SnapshotResource


class CloudWatchAlarmCollector:
    """Collect stable metric and composite alarm configuration."""

    service = "cloudwatch"
    _ACTIONS = ("OKActions", "AlarmActions", "InsufficientDataActions")

    def __init__(self, client: Any) -> None:
        self._client = client

    def _properties(self, alarm: dict[str, Any], composite: bool) -> dict[str, Any]:
        common = selected(alarm, ("AlarmArn", "AlarmDescription", "ActionsEnabled"))
        for field in self._ACTIONS:
            if field in alarm:
                common[field] = sorted(str(item) for item in alarm[field])
        if composite:
            common.update(selected(alarm, ("AlarmRule", "ActionsSuppressor", "ActionsSuppressorWaitPeriod", "ActionsSuppressorExtensionPeriod")))
            return common
        common.update(selected(alarm, (
            "MetricName", "Namespace", "Statistic", "ExtendedStatistic", "Period", "Unit",
            "EvaluationPeriods", "DatapointsToAlarm", "Threshold", "ComparisonOperator",
            "TreatMissingData", "EvaluateLowSampleCountPercentile", "ThresholdMetricId",
        )))
        if "Dimensions" in alarm:
            common["Dimensions"] = normalize(alarm["Dimensions"], sort_lists=True)
        if "Metrics" in alarm:
            common["Metrics"] = normalize(alarm["Metrics"], sort_lists=True)
        return common

    def collect(self) -> list[SnapshotResource]:
        try:
            pages = self._client.get_paginator("describe_alarms").paginate()
            resources: list[SnapshotResource] = []
            for page in pages:
                for key, resource_type, composite in (
                    ("MetricAlarms", "AWS::CloudWatch::Alarm", False),
                    ("CompositeAlarms", "AWS::CloudWatch::CompositeAlarm", True),
                ):
                    for alarm in page.get(key, []):
                        name = alarm.get("AlarmName")
                        if not isinstance(name, str) or not name:
                            raise ValueError("invalid CloudWatch response")
                        resources.append(SnapshotResource(resource_type, name, self._properties(alarm, composite)))
            resources.sort(key=lambda resource: (resource.resource_type, resource.logical_name))
            return resources
        except Exception as error:
            log_api_failure(self.service, "describe_alarms", error)
            return []
