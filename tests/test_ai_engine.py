"""Unit tests for the Phase 4 Amazon Bedrock Intelligence Engine."""

from __future__ import annotations

import importlib
import json
import unittest
from unittest.mock import Mock

_diff_models = importlib.import_module("lambda.diff.models")
_ai_client = importlib.import_module("lambda.ai.client")
_ai_models = importlib.import_module("lambda.ai.models")
_ai_parser = importlib.import_module("lambda.ai.parser")
_ai_prompt = importlib.import_module("lambda.ai.prompt")
_ai_service = importlib.import_module("lambda.ai.service")

Change = _diff_models.Change
ChangeReport = _diff_models.ChangeReport
ChangeSummary = _diff_models.ChangeSummary
BedrockClient = _ai_client.BedrockClient
BedrockInvocationError = _ai_client.BedrockInvocationError
BedrockResponse = _ai_client.BedrockResponse
ValidationError = _ai_models.ValidationError
parse_executive_analysis = _ai_parser.parse_executive_analysis
build_prompt = _ai_prompt.build_prompt
IntelligenceService = _ai_service.IntelligenceService

BEDROCK_ENV = {
    "AWS_REGION": "us-east-1",
    "BEDROCK_MODEL_ID": "unit-test-model",
    "BEDROCK_TEMPERATURE": "0.2",
    "BEDROCK_MAX_TOKENS": "512",
}

VALID_ANALYSIS = {
    "summary": "One EC2 instance type changed.",
    "security_impact": "No security-related field changed.",
    "operational_impact": "The instance capacity changed.",
    "cost_impact": "The report contains no pricing data.",
    "recommendations": ["Review change CHG-0001."],
}


def make_report() -> object:
    change = Change(
        change_id="CHG-0001",
        change_type="modified",
        resource_type="AWS::EC2::Instance",
        logical_name="web",
        field="instance_type",
        old="t3.micro",
        new="t3.medium",
    )
    return ChangeReport(
        summary=ChangeSummary(total_changes=1, added=0, removed=0, modified=1),
        changes=(change,),
    )


class PromptBuilderTests(unittest.TestCase):
    def test_prompt_generation_is_deterministic_and_grounded(self) -> None:
        report = make_report()

        first = build_prompt(report)
        second = build_prompt(report)

        self.assertEqual(first, second)
        self.assertIn("You are an Infrastructure Intelligence Analyst.", first)
        self.assertIn("Analyze ONLY the supplied infrastructure change report.", first)
        self.assertIn("Do NOT invent infrastructure.", first)
        self.assertIn("Do NOT speculate.", first)
        self.assertIn("Do NOT hallucinate missing resources.", first)
        self.assertIn("Base every conclusion on the provided report.", first)
        self.assertIn("No Markdown.", first)
        self.assertIn("No prose outside JSON.", first)
        self.assertIn('"change_id":"CHG-0001"', first)
        self.assertIn('"security_impact":"..."', first)


class AnalysisParserTests(unittest.TestCase):
    def test_successful_parsing_returns_typed_model(self) -> None:
        analysis = parse_executive_analysis(json.dumps(VALID_ANALYSIS))

        self.assertEqual(analysis.to_dict(), VALID_ANALYSIS)
        self.assertIsInstance(analysis.recommendations[0], _ai_models.Recommendation)

    def test_malformed_json_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValidationError, "not valid JSON"):
            parse_executive_analysis("{not-json}")

    def test_missing_fields_are_rejected(self) -> None:
        incomplete = dict(VALID_ANALYSIS)
        del incomplete["cost_impact"]

        with self.assertRaisesRegex(ValidationError, "missing"):
            parse_executive_analysis(json.dumps(incomplete))

    def test_unexpected_fields_are_rejected(self) -> None:
        extended = {**VALID_ANALYSIS, "confidence": "high"}

        with self.assertRaisesRegex(ValidationError, "unexpected"):
            parse_executive_analysis(json.dumps(extended))


class BedrockClientTests(unittest.TestCase):
    def test_client_invokes_mocked_bedrock_and_returns_structured_response(self) -> None:
        runtime_client = Mock()
        runtime_client.converse.return_value = {
            "output": {
                "message": {"content": [{"text": json.dumps(VALID_ANALYSIS)}]}
            },
            "stopReason": "end_turn",
            "ResponseMetadata": {"RequestId": "request-123"},
        }
        client = BedrockClient(environ=BEDROCK_ENV, runtime_client=runtime_client)

        response = client.invoke("deterministic prompt")

        self.assertEqual(response.text, json.dumps(VALID_ANALYSIS))
        self.assertEqual(response.request_id, "request-123")
        self.assertEqual(response.stop_reason, "end_turn")
        invocation = runtime_client.converse.call_args.kwargs
        self.assertEqual(invocation["modelId"], "unit-test-model")
        self.assertEqual(
            invocation["inferenceConfig"],
            {"temperature": 0.2, "maxTokens": 512},
        )
        self.assertEqual(
            invocation["messages"],
            [{"role": "user", "content": [{"text": "deterministic prompt"}]}],
        )

    def test_model_failures_are_wrapped_without_credential_details(self) -> None:
        runtime_client = Mock()
        runtime_client.converse.side_effect = RuntimeError(
            "internal failure with secret material"
        )
        client = BedrockClient(environ=BEDROCK_ENV, runtime_client=runtime_client)

        with self.assertRaisesRegex(
            BedrockInvocationError, "Bedrock model invocation failed"
        ) as raised:
            client.invoke("prompt")

        self.assertNotIn("secret material", str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)


class IntelligenceServiceTests(unittest.TestCase):
    def test_service_orchestrates_prompt_invocation_and_parsing(self) -> None:
        client = Mock()
        client.invoke.return_value = BedrockResponse(
            text=json.dumps(VALID_ANALYSIS),
            request_id="request-123",
            stop_reason="end_turn",
        )
        service = IntelligenceService(client)

        analysis = service.analyze(make_report())

        self.assertEqual(analysis.to_dict(), VALID_ANALYSIS)
        client.invoke.assert_called_once()
        prompt = client.invoke.call_args.args[0]
        self.assertIn('"change_id":"CHG-0001"', prompt)


if __name__ == "__main__":
    unittest.main()
