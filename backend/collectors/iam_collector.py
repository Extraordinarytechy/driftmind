"""Read-only AWS IAM role collector."""

from __future__ import annotations

from typing import Any

from collectors import log_api_failure, normalize, policy, selected
from models import SnapshotResource


class IAMCollector:
    """Collect stable IAM role trust and policy configuration."""

    service = "iam"

    def __init__(self, client: Any) -> None:
        self._client = client

    def collect(self) -> list[SnapshotResource]:
        operation = "list_roles"
        try:
            pages = self._client.get_paginator("list_roles").paginate()
            resources: list[SnapshotResource] = []
            for page in pages:
                for role in page.get("Roles", []):
                    name = role.get("RoleName")
                    if not isinstance(name, str) or not name:
                        raise ValueError("invalid IAM response")
                    properties = selected(role, ("Path", "Arn", "Description", "MaxSessionDuration"))
                    if "AssumeRolePolicyDocument" in role:
                        properties["AssumeRolePolicyDocument"] = policy(role["AssumeRolePolicyDocument"])
                    if "PermissionsBoundary" in role:
                        properties["PermissionsBoundary"] = normalize(role["PermissionsBoundary"])
                    if "Tags" in role:
                        properties["Tags"] = normalize(role["Tags"], sort_lists=True)
                    operation = "list_attached_role_policies"
                    attached_pages = self._client.get_paginator(operation).paginate(RoleName=name)
                    attached = [
                        selected(item, ("PolicyName", "PolicyArn"))
                        for attached_page in attached_pages
                        for item in attached_page.get("AttachedPolicies", [])
                    ]
                    properties["AttachedPolicies"] = sorted(
                        attached, key=lambda item: (str(item.get("PolicyName", "")), str(item.get("PolicyArn", "")))
                    )
                    operation = "list_role_policies"
                    inline_pages = self._client.get_paginator(operation).paginate(RoleName=name)
                    policy_names = sorted(
                        str(policy_name)
                        for inline_page in inline_pages
                        for policy_name in inline_page.get("PolicyNames", [])
                    )
                    inline = []
                    for policy_name in policy_names:
                        operation = "get_role_policy"
                        document = self._client.get_role_policy(RoleName=name, PolicyName=policy_name)
                        inline.append({
                            "PolicyName": policy_name,
                            "PolicyDocument": policy(document.get("PolicyDocument", {})),
                        })
                    properties["InlinePolicies"] = inline
                    resources.append(SnapshotResource("AWS::IAM::Role", name, properties))
            resources.sort(key=lambda resource: (resource.resource_type, resource.logical_name))
            return resources
        except Exception as error:
            log_api_failure(self.service, operation, error)
            return []
