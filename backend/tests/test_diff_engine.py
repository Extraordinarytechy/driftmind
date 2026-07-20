"""Comprehensive unit tests for the Phase 3 infrastructure diff engine."""

from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from models import SCHEMA_VERSION, Snapshot, SnapshotResource
from storage import serialize_snapshot

_comparator = importlib.import_module("lambda.diff.comparator")
_loader = importlib.import_module("lambda.diff.loader")
_report = importlib.import_module("lambda.diff.report")

compare_snapshots = _comparator.compare_snapshots
SnapshotCompatibilityError = _comparator.SnapshotCompatibilityError
LocalSnapshotLoader = _loader.LocalSnapshotLoader
SnapshotLoadError = _loader.SnapshotLoadError
serialize_change_report = _report.serialize_change_report


def resource(
    resource_type: str,
    logical_name: str,
    **properties: Any,
) -> SnapshotResource:
    return SnapshotResource(resource_type, logical_name, properties)


def snapshot(
    resources: list[SnapshotResource],
    generated_at: str = "2026-07-18T12:00:00.000000Z",
    provider: str = "demo",
    environment: str = "demo",
) -> Snapshot:
    result = Snapshot(
        schema_version=SCHEMA_VERSION,
        generated_at=generated_at,
        provider=provider,
        environment=environment,
        resources=resources,
    )
    result.validate()
    return result


class DiffEngineTests(unittest.TestCase):
    def test_detects_added_resource(self) -> None:
        current = snapshot(
            [resource("AWS::S3::Bucket", "artifacts", versioning=True)]
        )

        report = compare_snapshots(snapshot([]), current)

        self.assertEqual(report.summary.to_dict(), {
            "total_changes": 1, "added": 1, "removed": 0, "modified": 0
        })
        self.assertEqual(report.changes[0].to_dict(), {
            "change_id": "CHG-0001",
            "change_type": "added",
            "resource_type": "AWS::S3::Bucket",
            "logical_name": "artifacts",
            "field": None,
            "old": None,
            "new": {"versioning": True},
        })

    def test_detects_removed_resource(self) -> None:
        previous = snapshot(
            [resource("AWS::EC2::SecurityGroup", "web-sg", ingress=[])]
        )

        report = compare_snapshots(previous, snapshot([]))

        self.assertEqual(report.summary.removed, 1)
        self.assertEqual(report.changes[0].change_id, "CHG-0001")
        self.assertEqual(report.changes[0].change_type, "removed")
        self.assertIsNone(report.changes[0].field)
        self.assertEqual(report.changes[0].old, {"ingress": []})
        self.assertIsNone(report.changes[0].new)

    def test_detects_modified_property_and_ignores_unchanged_fields(self) -> None:
        previous = snapshot(
            [resource("AWS::EC2::Instance", "web", instance_type="t3.micro", state="running")]
        )
        current = snapshot(
            [resource("AWS::EC2::Instance", "web", instance_type="t3.medium", state="running")]
        )

        report = compare_snapshots(previous, current)

        self.assertEqual(report.summary.modified, 1)
        self.assertEqual(report.changes[0].field, "instance_type")
        self.assertEqual(report.changes[0].old, "t3.micro")
        self.assertEqual(report.changes[0].new, "t3.medium")

    def test_no_changes_returns_empty_report(self) -> None:
        resources = [resource("AWS::S3::Bucket", "artifacts", versioning=True)]
        previous = snapshot(resources)
        current = snapshot(
            [resource("AWS::S3::Bucket", "artifacts", versioning=True)],
            generated_at="2026-07-19T12:00:00.000000Z",
        )

        report = compare_snapshots(previous, current)

        self.assertEqual(report.summary.to_dict(), {
            "total_changes": 0, "added": 0, "removed": 0, "modified": 0
        })
        self.assertEqual(report.changes, ())

    def test_multiple_changes_have_stable_order_and_ids(self) -> None:
        previous = snapshot([
            resource("AWS::EC2::Instance", "web", instance_type="t3.micro", tags={"Tier": "web"}),
            resource("AWS::S3::Bucket", "removed-bucket", versioning=False),
        ])
        current = snapshot([
            resource("AWS::EC2::SecurityGroup", "added-sg", ingress=[]),
            resource("AWS::EC2::Instance", "web", instance_type="t3.medium", tags={"Tier": "frontend"}),
        ])

        first = compare_snapshots(previous, current)
        second = compare_snapshots(previous, current)

        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.summary.to_dict(), {
            "total_changes": 4, "added": 1, "removed": 1, "modified": 2
        })
        self.assertEqual(
            [(change.change_id, change.change_type, change.field) for change in first.changes],
            [
                ("CHG-0001", "added", None),
                ("CHG-0002", "removed", None),
                ("CHG-0003", "modified", "instance_type"),
                ("CHG-0004", "modified", "tags.Tier"),
            ],
        )

    def test_list_order_is_compared_as_a_property_value(self) -> None:
        previous = snapshot([
            resource("AWS::EC2::SecurityGroup", "web", ports=[80, 443])
        ])
        current = snapshot([
            resource("AWS::EC2::SecurityGroup", "web", ports=[443, 80])
        ])

        report = compare_snapshots(previous, current)

        self.assertEqual(report.summary.modified, 1)
        self.assertEqual(report.changes[0].field, "ports")

    def test_rejects_incompatible_snapshots(self) -> None:
        with self.assertRaises(SnapshotCompatibilityError):
            compare_snapshots(snapshot([], provider="demo"), snapshot([], provider="aws"))


class LocalSnapshotLoaderTests(unittest.TestCase):
    def test_loads_previous_and_current_local_json(self) -> None:
        previous = snapshot([])
        current = snapshot(
            [resource("AWS::S3::Bucket", "artifacts", versioning=True)],
            generated_at="2026-07-19T12:00:00.000000Z",
        )
        with tempfile.TemporaryDirectory() as directory:
            previous_path = Path(directory) / "previous.json"
            current_path = Path(directory) / "current.json"
            previous_path.write_text(serialize_snapshot(previous), encoding="utf-8")
            current_path.write_text(serialize_snapshot(current), encoding="utf-8")

            loaded_previous, loaded_current = LocalSnapshotLoader().load_pair(
                previous_path, current_path
            )

        self.assertEqual(loaded_previous.to_dict(), previous.to_dict())
        self.assertEqual(loaded_current.to_dict(), current.to_dict())

    def test_rejects_unknown_snapshot_fields(self) -> None:
        document = snapshot([]).to_dict()
        document["unexpected"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps(document), encoding="utf-8")

            with self.assertRaises(SnapshotLoadError):
                LocalSnapshotLoader().load(path)


class ChangeReportTests(unittest.TestCase):
    def test_report_json_is_deterministic_and_has_exact_top_level_fields(self) -> None:
        previous = snapshot([])
        current = snapshot([resource("AWS::S3::Bucket", "artifacts", versioning=True)])
        report = compare_snapshots(previous, current)

        first = serialize_change_report(report)
        second = serialize_change_report(report)
        document = json.loads(first)

        self.assertEqual(first, second)
        self.assertEqual(list(document), ["summary", "changes"])
        self.assertEqual(
            list(document["changes"][0]),
            [
                "change_id",
                "change_type",
                "resource_type",
                "logical_name",
                "field",
                "old",
                "new",
            ],
        )


if __name__ == "__main__":
    unittest.main()
