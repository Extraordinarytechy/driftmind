"""Unit tests for the Phase 2 infrastructure snapshot engine."""

from __future__ import annotations

import importlib
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from models import SCHEMA_VERSION, Snapshot, SnapshotResource, SnapshotValidationError
from providers.demo_provider import DemoProvider
from snapshot.collector import SnapshotCollector
from storage import (
    SnapshotStorage,
    SnapshotStorageError,
    build_snapshot_key,
    serialize_snapshot,
)

FIXED_TIME = datetime(2026, 7, 18, 12, 34, 56, 789000, tzinfo=timezone.utc)


def make_snapshot() -> Snapshot:
    return SnapshotCollector("demo", clock=lambda: FIXED_TIME).collect()


class SnapshotModelTests(unittest.TestCase):
    def test_snapshot_model_matches_versioned_contract(self) -> None:
        snapshot = make_snapshot()

        self.assertEqual(snapshot.schema_version, SCHEMA_VERSION)
        self.assertEqual(snapshot.generated_at, "2026-07-18T12:34:56.789000Z")
        self.assertEqual(snapshot.provider, "demo")
        self.assertEqual(snapshot.environment, "demo")
        self.assertEqual(len(snapshot.resources), 3)
        self.assertEqual(
            list(snapshot.to_dict()),
            ["schema_version", "generated_at", "provider", "environment", "resources"],
        )

    def test_snapshot_rejects_duplicate_resource_identity(self) -> None:
        resource = SnapshotResource("AWS::S3::Bucket", "duplicate", {})
        snapshot = Snapshot(
            schema_version=SCHEMA_VERSION,
            generated_at="2026-07-18T12:34:56.000000Z",
            provider="demo",
            environment="demo",
            resources=[resource, resource],
        )

        with self.assertRaises(SnapshotValidationError):
            snapshot.validate()

    def test_snapshot_rejects_non_utc_timestamp(self) -> None:
        snapshot = Snapshot(
            schema_version=SCHEMA_VERSION,
            generated_at="2026-07-18T12:34:56",
            provider="demo",
            environment="demo",
            resources=[],
        )

        with self.assertRaises(SnapshotValidationError):
            snapshot.validate()


class DemoProviderTests(unittest.TestCase):
    def test_demo_provider_is_deterministic(self) -> None:
        first = [resource.to_dict() for resource in DemoProvider().collect_resources()]
        second = [resource.to_dict() for resource in DemoProvider().collect_resources()]

        self.assertEqual(first, second)
        self.assertEqual(
            {resource["resource_type"] for resource in first},
            {"AWS::EC2::Instance", "AWS::EC2::SecurityGroup", "AWS::S3::Bucket"},
        )


class SnapshotCollectorTests(unittest.TestCase):
    def test_collector_loads_provider_and_returns_valid_snapshot(self) -> None:
        snapshot = make_snapshot()

        snapshot.validate()
        identities = [
            (resource["resource_type"], resource["logical_name"])
            for resource in snapshot.to_dict()["resources"]
        ]
        self.assertEqual(identities, sorted(identities))


class SerializationTests(unittest.TestCase):
    def test_serialization_is_valid_deterministic_json(self) -> None:
        snapshot = make_snapshot()

        first = serialize_snapshot(snapshot)
        second = serialize_snapshot(snapshot)
        document = json.loads(first)

        self.assertEqual(first, second)
        self.assertEqual(
            set(document),
            {"schema_version", "generated_at", "provider", "environment", "resources"},
        )
        self.assertEqual(document["schema_version"], "1.0")

    def test_snapshot_key_uses_required_date_and_timestamp(self) -> None:
        self.assertEqual(
            build_snapshot_key(make_snapshot()),
            "snapshots/2026/07/18/snapshot-20260718T123456789000Z.json",
        )


class SnapshotStorageTests(unittest.TestCase):
    def test_upload_uses_mock_s3_client(self) -> None:
        s3_client = Mock()
        storage = SnapshotStorage(
            bucket="unit-test-snapshots",
            region="us-east-1",
            s3_client=s3_client,
        )

        key = storage.upload(make_snapshot())

        self.assertEqual(
            key,
            "snapshots/2026/07/18/snapshot-20260718T123456789000Z.json",
        )
        upload = s3_client.put_object.call_args.kwargs
        self.assertEqual(upload["Bucket"], "unit-test-snapshots")
        self.assertEqual(upload["Key"], key)
        self.assertEqual(upload["ContentType"], "application/json")
        self.assertEqual(upload["ServerSideEncryption"], "AES256")
        self.assertEqual(upload["IfNoneMatch"], "*")
        self.assertEqual(json.loads(upload["Body"]), make_snapshot().to_dict())

    def test_upload_failure_is_generic_logged_and_preserves_cause(self) -> None:
        provider_message = "raw AWS response containing secret material"
        provider_error = RuntimeError(provider_message)
        s3_client = Mock()
        s3_client.put_object.side_effect = provider_error
        storage = SnapshotStorage(
            bucket="unit-test-snapshots",
            region="us-east-1",
            s3_client=s3_client,
        )

        with self.assertLogs("storage", level="ERROR") as captured:
            with self.assertRaisesRegex(
                SnapshotStorageError, "^Snapshot upload failed$"
            ) as raised:
                storage.upload(make_snapshot())

        self.assertIs(raised.exception.__cause__, provider_error)
        self.assertNotIn(provider_message, str(raised.exception))
        log_output = "\n".join(captured.output)
        self.assertIn("operation=put_object", log_output)
        self.assertIn("error_type=RuntimeError", log_output)
        self.assertIn(
            "snapshots/2026/07/18/snapshot-20260718T123456789000Z.json",
            log_output,
        )
        self.assertNotIn(provider_message, log_output)
        self.assertNotIn("unit-test-snapshots", log_output)
        self.assertNotIn("Traceback", log_output)


class LambdaPipelineTests(unittest.TestCase):
    def test_lambda_handler_executes_locally_with_mock_s3(self) -> None:
        app = importlib.import_module("lambda.app")
        mock_module = importlib.import_module("unittest.mock")
        s3_client = Mock()
        s3_client.list_objects_v2.return_value = {
            "Contents": [],
            "IsTruncated": False,
        }
        environment = {
            "SNAPSHOT_BUCKET": "local-snapshots",
            "AWS_REGION": "us-east-1",
            "PROVIDER": "demo",
        }

        with (
            mock_module.patch.dict("os.environ", environment, clear=True),
            mock_module.patch.object(
                app.SnapshotStorage,
                "_create_s3_client",
                return_value=s3_client,
            ),
        ):
            response = app.lambda_handler({}, None)

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["resource_count"], 3)
        self.assertEqual(response["s3"]["bucket"], "local-snapshots")
        self.assertEqual(response["pipeline_status"], "BASELINE_CREATED")
        self.assertFalse(response["bedrock_invoked"])
        self.assertFalse(response["ses_sent"])
        self.assertEqual(s3_client.put_object.call_count, 3)
        uploaded_keys = [
            call.kwargs["Key"] for call in s3_client.put_object.call_args_list
        ]
        self.assertTrue(uploaded_keys[0].startswith("snapshots/"))
        self.assertTrue(uploaded_keys[1].startswith("reports/2026/"))
        self.assertEqual(uploaded_keys[2], "reports/latest.json")
        historical = s3_client.put_object.call_args_list[1].kwargs
        latest = s3_client.put_object.call_args_list[2].kwargs
        self.assertEqual(latest["Body"], historical["Body"])
        self.assertNotIn("IfNoneMatch", latest)
        self.assertEqual(latest["CacheControl"], "no-cache, max-age=0")

    def test_latest_report_failure_does_not_fail_completed_pipeline(self) -> None:
        app = importlib.import_module("lambda.app")
        mock_module = importlib.import_module("unittest.mock")
        s3_client = Mock()
        s3_client.list_objects_v2.return_value = {
            "Contents": [],
            "IsTruncated": False,
        }
        s3_client.put_object.side_effect = [
            {"ETag": "snapshot"},
            {"ETag": "historical-report"},
            RuntimeError("raw latest write failure"),
        ]
        environment = {
            "SNAPSHOT_BUCKET": "local-snapshots",
            "AWS_REGION": "us-east-1",
            "PROVIDER": "demo",
        }

        with (
            mock_module.patch.dict("os.environ", environment, clear=True),
            mock_module.patch.object(
                app.SnapshotStorage,
                "_create_s3_client",
                return_value=s3_client,
            ),
            self.assertLogs("lambda.agent.storage", level="ERROR") as captured,
        ):
            response = app.lambda_handler({}, None)

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["pipeline_status"], "BASELINE_CREATED")
        self.assertEqual(s3_client.put_object.call_count, 3)
        log_output = "\n".join(captured.output)
        self.assertIn("Latest report update failed", log_output)
        self.assertNotIn("raw latest write failure", log_output)

    def test_lambda_handler_returns_structured_configuration_error(self) -> None:
        app = importlib.import_module("lambda.app")
        mock_module = importlib.import_module("unittest.mock")

        with mock_module.patch.dict("os.environ", {}, clear=True):
            response = app.lambda_handler({}, None)

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["error_type"], "ConfigurationError")
        self.assertEqual(response["message"], "Snapshot pipeline execution failed.")

    def test_lambda_handler_redacts_provider_message_and_logs_failure(self) -> None:
        app = importlib.import_module("lambda.app")
        mock_module = importlib.import_module("unittest.mock")
        provider_message = "raw provider response containing secret material"

        with (
            mock_module.patch.object(
                app,
                "run_snapshot_pipeline",
                side_effect=RuntimeError(provider_message),
            ),
            self.assertLogs("lambda.app", level="ERROR") as captured,
        ):
            response = app.lambda_handler({}, None)

        self.assertEqual(
            response,
            {
                "status": "error",
                "error_type": "RuntimeError",
                "message": "Snapshot pipeline execution failed.",
            },
        )
        self.assertNotIn(provider_message, str(response))
        log_output = "\n".join(captured.output)
        self.assertIn("operation=run_snapshot_pipeline", log_output)
        self.assertIn("error_type=RuntimeError", log_output)
        self.assertNotIn(provider_message, log_output)
        self.assertNotIn("Traceback", log_output)


if __name__ == "__main__":
    unittest.main()
