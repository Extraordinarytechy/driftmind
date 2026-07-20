"""Read-only AWS Lambda function collector."""

from __future__ import annotations

from typing import Any

from collectors import log_api_failure, normalize, selected
from models import SnapshotResource


class LambdaCollector:
    """Collect stable Lambda function configuration."""

    service = "lambda"

    def __init__(self, client: Any) -> None:
        self._client = client

    def collect(self) -> list[SnapshotResource]:
        try:
            pages = self._client.get_paginator("list_functions").paginate()
            resources: list[SnapshotResource] = []
            for page in pages:
                for function in page.get("Functions", []):
                    properties = selected(
                        function,
                        (
                            "FunctionArn", "Description", "Runtime", "Role", "Handler",
                            "MemorySize", "Timeout", "PackageType", "KMSKeyArn",
                            "CodeSigningConfigArn",
                        ),
                    )
                    for field in ("Architectures", "FileSystemConfigs"):
                        if field in function:
                            properties[field] = normalize(function[field], sort_lists=True)
                    layers = function.get("Layers")
                    if layers is not None:
                        if not isinstance(layers, list):
                            raise ValueError("invalid Lambda layers response")
                        layer_arns = []
                        for layer in layers:
                            arn = layer.get("Arn") if isinstance(layer, dict) else None
                            if not isinstance(arn, str) or not arn:
                                raise ValueError("invalid Lambda layer response")
                            layer_arns.append(arn)
                        properties["Layers"] = sorted(layer_arns)
                    for field in ("DeadLetterConfig", "TracingConfig", "LoggingConfig"):
                        if field in function:
                            properties[field] = normalize(function[field])
                    snap_start = function.get("SnapStart")
                    if isinstance(snap_start, dict):
                        properties["SnapStart"] = selected(snap_start, ("ApplyOn",))
                    ephemeral_storage = function.get("EphemeralStorage")
                    if isinstance(ephemeral_storage, dict):
                        properties["EphemeralStorage"] = selected(ephemeral_storage, ("Size",))
                    vpc = function.get("VpcConfig")
                    if isinstance(vpc, dict):
                        properties["VpcConfig"] = selected(
                            vpc,
                            ("VpcId", "SubnetIds", "SecurityGroupIds", "Ipv6AllowedForDualStack"),
                        )
                        for field in ("SubnetIds", "SecurityGroupIds"):
                            if field in properties["VpcConfig"]:
                                properties["VpcConfig"][field] = sorted(properties["VpcConfig"][field])
                    environment = function.get("Environment")
                    if isinstance(environment, dict) and isinstance(environment.get("Variables"), dict):
                        properties["EnvironmentKeys"] = sorted(str(key) for key in environment["Variables"])
                    name = function.get("FunctionName")
                    if not isinstance(name, str) or not name:
                        raise ValueError("invalid Lambda response")
                    resources.append(SnapshotResource("AWS::Lambda::Function", name, properties))
            resources.sort(key=lambda resource: (resource.resource_type, resource.logical_name))
            return resources
        except Exception as error:
            log_api_failure(self.service, "list_functions", error)
            return []
