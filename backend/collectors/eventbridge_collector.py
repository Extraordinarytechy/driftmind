"""Read-only Amazon EventBridge rule collector."""

from __future__ import annotations

from typing import Any

from collectors import log_api_failure, policy, selected
from models import SnapshotResource


class EventBridgeCollector:
    """Collect stable rules from every visible event bus."""

    service = "eventbridge"

    def __init__(self, client: Any) -> None:
        self._client = client

    def collect(self) -> list[SnapshotResource]:
        operation = "list_event_buses"
        try:
            resources: list[SnapshotResource] = []
            next_token: str | None = None
            while True:
                operation = "list_event_buses"
                request = {"NextToken": next_token} if next_token is not None else {}
                bus_page = self._client.list_event_buses(**request)
                if not isinstance(bus_page, dict):
                    raise ValueError("invalid EventBridge response")
                for bus in bus_page.get("EventBuses", []):
                    bus_name = bus.get("Name")
                    if not isinstance(bus_name, str) or not bus_name:
                        raise ValueError("invalid EventBridge response")
                    operation = "list_rules"
                    rule_pages = self._client.get_paginator(operation).paginate(EventBusName=bus_name)
                    for rule_page in rule_pages:
                        for rule in rule_page.get("Rules", []):
                            name = rule.get("Name")
                            if not isinstance(name, str) or not name:
                                raise ValueError("invalid EventBridge rule")
                            properties = selected(
                                rule,
                                ("Arn", "Description", "ScheduleExpression", "State", "ManagedBy", "RoleArn"),
                            )
                            properties["EventBusName"] = bus_name
                            if "EventPattern" in rule:
                                properties["EventPattern"] = policy(rule["EventPattern"])
                            resources.append(
                                SnapshotResource("AWS::Events::Rule", f"{bus_name}/{name}", properties)
                            )
                token = bus_page.get("NextToken")
                if token is None:
                    break
                if not isinstance(token, str) or not token:
                    raise ValueError("invalid EventBridge pagination token")
                next_token = token
            resources.sort(key=lambda resource: (resource.resource_type, resource.logical_name))
            return resources
        except Exception as error:
            log_api_failure(self.service, operation, error)
            return []
