"""End-to-end unit tests for the autonomous DriftMind pipeline."""

from __future__ import annotations

import importlib
import json
import unittest
from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from unittest.mock import Mock

from models import SCHEMA_VERSION, Snapshot, SnapshotResource
from storage import build_snapshot_key, serialize_snapshot

_app = importlib.import_module("lambda.app")
_drift_ai = importlib.import_module("lambda.ai.drift")
_s3_loader = importlib.import_module("lambda.diff.s3_loader")
_storage = importlib.import_module("lambda.agent.storage")
_agent_models = importlib.import_module("lambda.agent.models")
_diff_models = importlib.import_module("lambda.diff.models")

FIXED_TIME = datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc)
FULL_ENV = {
    "AWS_REGION": "us-east-1",
    "SNAPSHOT_BUCKET": "unit-test-bucket",
    "PROVIDER": "demo",
    "BEDROCK_MODEL_ID": "unit-test-model",
    "BEDROCK_TEMPERATURE": "0.0",
    "BEDROCK_MAX_TOKENS": "512",
    "SES_SENDER": "sender@example.com",
    "SES_RECIPIENT": "recipient@example.com",
}
VALID_DRIFT_ANALYSIS = {
    "executive_summary": "Three deterministic infrastructure changes were detected.",
    "change_explanation": "A security group was added, a bucket was removed, and an instance changed.",
    "potential_impact": "Capacity and access paths should be reviewed.",
    "risk_level": "Medium",
    "recommendations": ["Review CHG-0001 through CHG-0003."],
}


def resource(resource_type: str, logical_name: str, **properties: Any) -> SnapshotResource:
    return SnapshotResource(resource_type, logical_name, properties)


def snapshot(generated_at: str, resources: list[SnapshotResource]) -> Snapshot:
    value = Snapshot(
        schema_version=SCHEMA_VERSION,
        generated_at=generated_at,
        provider="demo",
        environment="demo",
        resources=resources,
    )
    value.validate()
    return value


class StaticCollector:
    def __init__(self, value: Snapshot) -> None:
        self._value = value

    def collect(self) -> Snapshot:
        return self._value


class FakeS3Client:
    """Small in-memory S3 double supporting put, paginated list, and get."""

    def __init__(self, page_size: int = 1000) -> None:
        self.objects: dict[str, bytes] = {}
        self.put_calls: list[dict[str, Any]] = []
        self.page_size = page_size

    def seed_snapshot(self, value: Snapshot) -> str:
        key = build_snapshot_key(value)
        self.objects[key] = serialize_snapshot(value).encode("utf-8")
        return key

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        key = kwargs["Key"]
        if kwargs.get("IfNoneMatch") == "*" and key in self.objects:
            raise RuntimeError("conditional write failed")
        body = kwargs["Body"]
        self.objects[key] = body if isinstance(body, bytes) else bytes(body)
        self.put_calls.append(kwargs)
        return {"ETag": "unit-test"}

    def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]:
        prefix = kwargs.get("Prefix", "")
        keys = sorted(key for key in self.objects if key.startswith(prefix))
        start = int(kwargs.get("ContinuationToken", "0"))
        page = keys[start : start + self.page_size]
        next_index = start + len(page)
        response: dict[str, Any] = {
            "Contents": [{"Key": key} for key in page],
            "IsTruncated": next_index < len(keys),
        }
        if response["IsTruncated"]:
            response["NextContinuationToken"] = str(next_index)
        return response

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        return {"Body": BytesIO(self.objects[kwargs["Key"]])}


def bedrock_client() -> Mock:
    client = Mock()
    client.converse.return_value = {
        "output": {
            "message": {
                "content": [{"text": json.dumps(VALID_DRIFT_ANALYSIS)}]
            }
        },
        "stopReason": "end_turn",
        "ResponseMetadata": {"RequestId": "request-123"},
    }
    return client


def ses_client() -> Mock:
    client = Mock()
    client.send_raw_email.return_value = {"MessageId": "message-123"}
    return client


def report_documents(client: FakeS3Client) -> list[dict[str, Any]]:
    keys = sorted(
        key
        for key in client.objects
        if key.startswith("reports/") and key != "reports/latest.json"
    )
    return [json.loads(client.objects[key]) for key in keys]


class AutonomousPipelineTests(unittest.TestCase):
    def test_no_previous_snapshot_creates_baseline_without_bedrock_or_ses(self) -> None:
        current = snapshot("2026-07-20T12:00:00.000000Z", [])
        s3 = FakeS3Client()
        bedrock = bedrock_client()
        ses = ses_client()

        with self.assertLogs("lambda.agent.service", level="INFO") as captured:
            result = _app.run_snapshot_pipeline(
                environ=FULL_ENV,
                s3_client=s3,
                collector=StaticCollector(current),
                bedrock_runtime_client=bedrock,
                ses_client=ses,
            )

        self.assertEqual(result["pipeline_status"], "BASELINE_CREATED")
        self.assertFalse(result["changes_detected"])
        self.assertFalse(result["bedrock_invoked"])
        self.assertFalse(result["ses_sent"])
        bedrock.converse.assert_not_called()
        ses.send_raw_email.assert_not_called()
        reports = report_documents(s3)
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["status"], "BASELINE_CREATED")
        self.assertEqual(reports[0]["summary"], "Initial infrastructure baseline created.")
        self.assertFalse(reports[0]["bedrock_invoked"])
        logs = "\n".join(captured.output)
        self.assertIn("Loading previous snapshot", logs)
        self.assertIn("Snapshot comparison completed", logs)
        self.assertIn("Changes detected: 0", logs)
        self.assertIn("Bedrock invoked: NO", logs)
        self.assertIn("Report stored", logs)
        self.assertIn("SES sent: NO", logs)

    def test_identical_snapshots_generate_healthy_report_and_skip_costly_services(self) -> None:
        resources = [resource("AWS::S3::Bucket", "artifacts", versioning=True)]
        previous = snapshot("2026-07-19T12:00:00.000000Z", resources)
        current = snapshot(
            "2026-07-20T12:00:00.000000Z",
            [resource("AWS::S3::Bucket", "artifacts", versioning=True)],
        )
        s3 = FakeS3Client()
        previous_key = s3.seed_snapshot(previous)
        bedrock = bedrock_client()
        ses = ses_client()

        result = _app.run_snapshot_pipeline(
            environ=FULL_ENV,
            s3_client=s3,
            collector=StaticCollector(current),
            bedrock_runtime_client=bedrock,
            ses_client=ses,
        )

        self.assertEqual(result["pipeline_status"], "HEALTHY")
        self.assertEqual(result["change_summary"]["total_changes"], 0)
        bedrock.converse.assert_not_called()
        ses.send_raw_email.assert_not_called()
        report = report_documents(s3)[0]
        self.assertEqual(report["summary"], "Infrastructure Healthy. No drift detected.")
        self.assertEqual(report["snapshots"]["previous"], previous_key)
        self.assertIsNone(report["risk"])
        self.assertEqual(report["recommendations"], [])

    def test_drift_executes_bedrock_sends_ses_and_stores_frontend_report(self) -> None:
        previous = snapshot(
            "2026-07-19T12:00:00.000000Z",
            [
                resource("AWS::EC2::Instance", "web", instance_type="t3.micro"),
                resource("AWS::S3::Bucket", "removed", versioning=False),
            ],
        )
        current = snapshot(
            "2026-07-20T12:00:00.000000Z",
            [
                resource("AWS::EC2::Instance", "web", instance_type="t3.medium"),
                resource("AWS::EC2::SecurityGroup", "added", ingress=[]),
            ],
        )
        s3 = FakeS3Client()
        s3.seed_snapshot(previous)
        bedrock = bedrock_client()
        ses = ses_client()

        result = _app.run_snapshot_pipeline(
            environ=FULL_ENV,
            s3_client=s3,
            collector=StaticCollector(current),
            bedrock_runtime_client=bedrock,
            ses_client=ses,
        )

        self.assertEqual(result["pipeline_status"], "DRIFT_DETECTED")
        self.assertTrue(result["changes_detected"])
        self.assertTrue(result["bedrock_invoked"])
        self.assertTrue(result["ses_sent"])
        self.assertEqual(
            result["change_summary"],
            {"total_changes": 3, "added": 1, "removed": 1, "modified": 1},
        )
        bedrock.converse.assert_called_once()
        ses.send_raw_email.assert_called_once()
        report = report_documents(s3)[0]
        self.assertEqual(report["status"], "DRIFT_DETECTED")
        self.assertEqual(report["resources_scanned"], 2)
        self.assertEqual(len(report["added"]), 1)
        self.assertEqual(len(report["removed"]), 1)
        self.assertEqual(len(report["modified"]), 1)
        self.assertEqual(report["risk"], "Medium")
        self.assertEqual(report["ai_summary"], VALID_DRIFT_ANALYSIS["executive_summary"])
        self.assertEqual(report["recommendations"], VALID_DRIFT_ANALYSIS["recommendations"])
        self.assertTrue(report["ses_sent"])
        self.assertEqual(report["ses_message_id"], "message-123")
        self.assertEqual(
            [event["stage"] for event in report["activity_timeline"]],
            [
                "SNAPSHOT_COLLECTED",
                "SNAPSHOT_STORED",
                "PREVIOUS_SNAPSHOT_LOADED",
                "SNAPSHOT_COMPARISON",
                "BEDROCK_ANALYSIS",
                "SES_NOTIFICATION",
                "REPORT_STORED",
            ],
        )

    def test_latest_previous_snapshot_is_selected_across_paginated_listing(self) -> None:
        older = snapshot("2026-07-18T12:00:00.000000Z", [])
        latest = snapshot("2026-07-19T12:00:00.000000Z", [])
        current = snapshot("2026-07-20T12:00:00.000000Z", [])
        s3 = FakeS3Client(page_size=1)
        s3.seed_snapshot(older)
        latest_key = s3.seed_snapshot(latest)
        current_key = s3.seed_snapshot(current)
        s3.objects["snapshots/not-a-canonical-key.json"] = b"{}"

        loaded = _s3_loader.S3SnapshotHistory(
            "unit-test-bucket", s3
        ).load_latest_before(current_key)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.key, latest_key)
        self.assertEqual(loaded.snapshot.to_dict(), latest.to_dict())

    def test_bedrock_failure_stores_drift_evidence_and_skips_ses(self) -> None:
        previous = snapshot("2026-07-19T12:00:00.000000Z", [])
        current = snapshot(
            "2026-07-20T12:00:00.000000Z",
            [resource("AWS::S3::Bucket", "added", versioning=True)],
        )
        s3 = FakeS3Client()
        s3.seed_snapshot(previous)
        bedrock = Mock()
        bedrock.converse.side_effect = RuntimeError("raw provider detail")
        ses = ses_client()

        with self.assertRaisesRegex(RuntimeError, "Bedrock model invocation failed"):
            _app.run_snapshot_pipeline(
                environ=FULL_ENV,
                s3_client=s3,
                collector=StaticCollector(current),
                bedrock_runtime_client=bedrock,
                ses_client=ses,
            )

        ses.send_raw_email.assert_not_called()
        report = report_documents(s3)[0]
        self.assertTrue(report["changes_detected"])
        self.assertTrue(report["bedrock_invoked"])
        self.assertIsNone(report["ai_summary"])
        self.assertFalse(report["ses_sent"])
        self.assertEqual(report["activity_timeline"][-3]["status"], "FAILED")

    def test_ses_failure_stores_analyzed_report_without_success_flag(self) -> None:
        previous = snapshot("2026-07-19T12:00:00.000000Z", [])
        current = snapshot(
            "2026-07-20T12:00:00.000000Z",
            [resource("AWS::S3::Bucket", "added", versioning=True)],
        )
        s3 = FakeS3Client()
        s3.seed_snapshot(previous)
        bedrock = bedrock_client()
        ses = Mock()
        ses.send_raw_email.side_effect = RuntimeError("raw provider detail")

        with self.assertRaisesRegex(RuntimeError, "SES notification delivery failed"):
            _app.run_snapshot_pipeline(
                environ=FULL_ENV,
                s3_client=s3,
                collector=StaticCollector(current),
                bedrock_runtime_client=bedrock,
                ses_client=ses,
            )

        report = report_documents(s3)[0]
        self.assertEqual(report["risk"], "Medium")
        self.assertFalse(report["ses_sent"])
        self.assertEqual(report["activity_timeline"][-2]["status"], "FAILED")


    def test_unstructured_bedrock_response_uses_fallback_and_completes_pipeline(self) -> None:
        previous = snapshot("2026-07-19T12:00:00.000000Z", [])
        current = snapshot(
            "2026-07-20T12:00:00.000000Z",
            [resource("AWS::S3::Bucket", "added", versioning=True)],
        )
        s3 = FakeS3Client()
        s3.seed_snapshot(previous)
        model_text = "The model returned an unstructured assessment."
        bedrock = bedrock_client()
        bedrock.converse.return_value["output"]["message"]["content"] = [
            {"text": model_text}
        ]
        ses = ses_client()

        with self.assertLogs("lambda.ai.drift", level="INFO") as captured:
            result = _app.run_snapshot_pipeline(
                environ=FULL_ENV,
                s3_client=s3,
                collector=StaticCollector(current),
                bedrock_runtime_client=bedrock,
                ses_client=ses,
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["pipeline_status"], "DRIFT_DETECTED")
        self.assertTrue(result["bedrock_invoked"])
        self.assertTrue(result["ses_sent"])
        bedrock.converse.assert_called_once()
        ses.send_raw_email.assert_called_once()
        report = report_documents(s3)[0]
        self.assertEqual(report["risk"], "UNKNOWN")
        self.assertEqual(report["summary"], model_text)
        self.assertEqual(report["ai_summary"], model_text)
        self.assertEqual(report["recommendations"], ["Manual review recommended."])
        self.assertTrue(report["ses_sent"])
        logs = "\n".join(captured.output)
        self.assertIn("request_id=request-123", logs)
        self.assertIn("stop_reason=end_turn", logs)
        self.assertIn(f"response_chars={len(model_text)}", logs)
        self.assertIn(f"model_text={model_text}", logs)

    def test_drift_then_two_healthy_runs_reuse_last_drift_in_latest(self) -> None:
        s3 = FakeS3Client()
        s3.seed_snapshot(
            snapshot(
                "2026-07-20T06:00:00.000000Z",
                [resource("AWS::Lambda::Function", "web", memory=128)],
            )
        )
        bedrock = bedrock_client()
        ses = ses_client()

        drift = snapshot(
            "2026-07-20T12:00:00.000000Z",
            [resource("AWS::Lambda::Function", "web", memory=256)],
        )
        healthy_first = snapshot(
            "2026-07-20T18:00:00.000000Z",
            [resource("AWS::Lambda::Function", "web", memory=256)],
        )
        healthy_second = snapshot(
            "2026-07-21T00:00:00.000000Z",
            [resource("AWS::Lambda::Function", "web", memory=256)],
        )

        def run(current: Snapshot) -> dict[str, Any]:
            return _app.run_snapshot_pipeline(
                environ=FULL_ENV,
                s3_client=s3,
                collector=StaticCollector(current),
                bedrock_runtime_client=bedrock,
                ses_client=ses,
            )

        result_drift = run(drift)
        latest_drift = json.loads(s3.objects["reports/latest.json"])
        result_healthy_1 = run(healthy_first)
        latest_healthy_1 = json.loads(s3.objects["reports/latest.json"])
        result_healthy_2 = run(healthy_second)
        latest_healthy_2 = json.loads(s3.objects["reports/latest.json"])

        # Pipeline decisions: one drift, then two healthy runs.
        self.assertEqual(result_drift["pipeline_status"], "DRIFT_DETECTED")
        self.assertEqual(result_healthy_1["pipeline_status"], "HEALTHY")
        self.assertEqual(result_healthy_2["pipeline_status"], "HEALTHY")

        # Bedrock and SES invoked exactly once, only for the drift run.
        self.assertEqual(bedrock.converse.call_count, 1)
        self.assertEqual(ses.send_raw_email.call_count, 1)

        # analysis_source transitions generated -> last_drift -> last_drift.
        self.assertEqual(latest_drift["analysis_source"], "generated")
        self.assertEqual(latest_healthy_1["analysis_source"], "last_drift")
        self.assertEqual(latest_healthy_2["analysis_source"], "last_drift")

        # last_drift_analysis persists unchanged across healthy runs.
        drift_analysis = latest_drift["last_drift_analysis"]
        self.assertIsNotNone(drift_analysis)
        self.assertEqual(drift_analysis["risk_level"], "Medium")
        self.assertEqual(latest_healthy_1["last_drift_analysis"], drift_analysis)
        self.assertEqual(latest_healthy_2["last_drift_analysis"], drift_analysis)

        # last_drift_run_time stays pinned to the drift run.
        self.assertEqual(latest_drift["last_drift_run_time"], "2026-07-20T12:00:00.000000Z")
        self.assertEqual(latest_healthy_1["last_drift_run_time"], "2026-07-20T12:00:00.000000Z")
        self.assertEqual(latest_healthy_2["last_drift_run_time"], "2026-07-20T12:00:00.000000Z")

        # latestScan (run_time) advances on every execution.
        self.assertEqual(latest_drift["run_time"], "2026-07-20T12:00:00.000000Z")
        self.assertEqual(latest_healthy_1["run_time"], "2026-07-20T18:00:00.000000Z")
        self.assertEqual(latest_healthy_2["run_time"], "2026-07-21T00:00:00.000000Z")

        # Healthy latest reports carry no current-scan analysis.
        self.assertIsNone(latest_healthy_1["analysis"])
        self.assertIsNone(latest_healthy_2["analysis"])

        # Historical reports remain unenriched and schema-consistent.
        reports = report_documents(s3)
        self.assertEqual(len(reports), 3)
        self.assertEqual(reports[0]["status"], "DRIFT_DETECTED")
        self.assertIsNotNone(reports[0]["analysis"])
        self.assertNotIn("analysis_source", reports[0])
        self.assertNotIn("last_drift_analysis", reports[0])
        self.assertEqual(reports[1]["status"], "HEALTHY")
        self.assertIsNone(reports[1]["analysis"])
        self.assertNotIn("analysis_source", reports[1])
        self.assertEqual(reports[2]["status"], "HEALTHY")
        self.assertIsNone(reports[2]["analysis"])
        self.assertNotIn("analysis_source", reports[2])


class DriftAnalysisContractTests(unittest.TestCase):
    def assert_fallback(
        self, analysis: Any, expected_summary: str
    ) -> None:
        analysis.validate()
        self.assertEqual(analysis.executive_summary, expected_summary)
        self.assertEqual(analysis.risk_level, "UNKNOWN")
        self.assertEqual(analysis.recommendations, ("Manual review recommended.",))
        self.assertTrue(analysis.change_explanation)
        self.assertTrue(analysis.potential_impact)

    def test_parses_valid_json(self) -> None:
        analysis = _drift_ai.parse_drift_analysis(json.dumps(VALID_DRIFT_ANALYSIS))

        self.assertEqual(analysis.to_dict(), VALID_DRIFT_ANALYSIS)

    def test_parses_valid_json_inside_json_fence_with_surrounding_whitespace(self) -> None:
        payload = f"  \n```json\n{json.dumps(VALID_DRIFT_ANALYSIS)}\n```\n  "

        analysis = _drift_ai.parse_drift_analysis(payload)

        self.assertEqual(analysis.to_dict(), VALID_DRIFT_ANALYSIS)

    def test_plain_text_returns_truncated_fallback_without_exception(self) -> None:
        payload = "  " + ("unstructured response " * 40) + "  "

        analysis = _drift_ai.parse_drift_analysis(payload)

        self.assert_fallback(analysis, payload.strip()[:500])
        self.assertEqual(len(analysis.executive_summary), 500)

    def test_malformed_json_returns_fallback_with_json_decode_diagnostics(self) -> None:
        payload = '{"executive_summary": "broken"'

        with self.assertLogs("lambda.ai.drift", level="ERROR") as captured:
            analysis = _drift_ai.parse_drift_analysis(payload)

        self.assert_fallback(analysis, payload)
        logs = "\n".join(captured.output)
        self.assertIn("JSONDecodeError", logs)
        self.assertIn("Expecting ',' delimiter", logs)
        self.assertIn(f"model_text={payload}", logs)

    def test_schema_validation_failure_returns_fallback_with_diagnostics(self) -> None:
        payload = json.dumps({**VALID_DRIFT_ANALYSIS, "executive_summary": ""})

        with self.assertLogs("lambda.ai.drift", level="ERROR") as captured:
            analysis = _drift_ai.parse_drift_analysis(payload)

        self.assert_fallback(analysis, payload)
        logs = "\n".join(captured.output)
        self.assertIn("executive_summary must be a non-empty string", logs)
        self.assertIn(f"model_text={payload}", logs)
        self.assertIn("Traceback", logs)

    def test_invalid_model_risk_returns_fallback_instead_of_raising(self) -> None:
        payload = json.dumps({**VALID_DRIFT_ANALYSIS, "risk_level": "Severe"})

        with self.assertLogs("lambda.ai.drift", level="ERROR") as captured:
            analysis = _drift_ai.parse_drift_analysis(payload)

        self.assert_fallback(analysis, payload)
        self.assertIn(
            "risk_level must be Low, Medium, High, or Critical",
            "\n".join(captured.output),
        )


class LatestReportEnrichmentTests(unittest.TestCase):
    def _healthy_report(self) -> Any:
        empty = _diff_models.ChangeReport(
            summary=_diff_models.ChangeSummary(
                total_changes=0, added=0, removed=0, modified=0
            ),
            changes=(),
        )
        report = _agent_models.AutonomousReport(
            run_time="2026-07-20T12:00:00.000000Z",
            status="HEALTHY",
            resources_scanned=1,
            changes_detected=False,
            bedrock_invoked=False,
            summary="Infrastructure Healthy. No drift detected.",
            change_report=empty,
            current_snapshot_key="snapshots/2026/07/20/snapshot-20260720T120000000000Z.json",
            previous_snapshot_key="snapshots/2026/07/19/snapshot-20260719T120000000000Z.json",
            analysis=None,
        )
        report.validate()
        return report

    def test_generated_source_when_current_report_has_analysis(self) -> None:
        current = {"run_time": "2026-07-20T12:00:00Z", "analysis": {"risk_level": "High"}}

        result = _storage.build_latest_report_payload(current, None)

        self.assertEqual(result["analysis_source"], "generated")
        self.assertEqual(result["last_drift_analysis"], {"risk_level": "High"})
        self.assertEqual(result["last_drift_run_time"], "2026-07-20T12:00:00Z")

    def test_none_source_when_no_analysis_and_no_prior(self) -> None:
        current = {"run_time": "2026-07-20T12:00:00Z", "analysis": None}

        result = _storage.build_latest_report_payload(current, None)

        self.assertEqual(result["analysis_source"], "none")
        self.assertIsNone(result["last_drift_analysis"])
        self.assertIsNone(result["last_drift_run_time"])

    def test_reuses_prior_drift_analysis_when_healthy(self) -> None:
        current = {"run_time": "2026-07-20T12:00:00Z", "analysis": None}
        previous_latest = {
            "run_time": "2026-07-19T12:00:00Z",
            "analysis": {"risk_level": "Medium"},
        }

        result = _storage.build_latest_report_payload(current, previous_latest)

        self.assertEqual(result["analysis_source"], "last_drift")
        self.assertEqual(result["last_drift_analysis"], {"risk_level": "Medium"})
        self.assertEqual(result["last_drift_run_time"], "2026-07-19T12:00:00Z")

    def test_propagates_prior_last_drift_across_consecutive_healthy_runs(self) -> None:
        current = {"run_time": "2026-07-20T12:00:00Z", "analysis": None}
        previous_latest = {
            "run_time": "2026-07-19T18:00:00Z",
            "analysis": None,
            "analysis_source": "last_drift",
            "last_drift_analysis": {"risk_level": "Critical"},
            "last_drift_run_time": "2026-07-18T09:00:00Z",
        }

        result = _storage.build_latest_report_payload(current, previous_latest)

        self.assertEqual(result["analysis_source"], "last_drift")
        self.assertEqual(result["last_drift_analysis"], {"risk_level": "Critical"})
        self.assertEqual(result["last_drift_run_time"], "2026-07-18T09:00:00Z")

    def test_store_enriches_latest_and_leaves_historical_unchanged(self) -> None:
        s3 = FakeS3Client()
        drift_analysis = {
            "executive_summary": "Prior drift analysis.",
            "change_explanation": "A prior change was explained.",
            "potential_impact": "Prior impact.",
            "risk_level": "Medium",
            "recommendations": ["Review the prior change."],
        }
        s3.objects["reports/latest.json"] = json.dumps(
            {"run_time": "2026-07-19T12:00:00.000000Z", "analysis": drift_analysis}
        ).encode("utf-8")

        storage = _storage.ReportStorage("unit-test-bucket", s3)
        historical_key = storage.store(self._healthy_report())

        historical_document = json.loads(s3.objects[historical_key])
        latest_document = json.loads(s3.objects["reports/latest.json"])
        self.assertIsNone(historical_document["analysis"])
        self.assertNotIn("analysis_source", historical_document)
        self.assertEqual(latest_document["analysis_source"], "last_drift")
        self.assertEqual(latest_document["last_drift_analysis"], drift_analysis)
        self.assertIsNone(latest_document["analysis"])


if __name__ == "__main__":
    unittest.main()
