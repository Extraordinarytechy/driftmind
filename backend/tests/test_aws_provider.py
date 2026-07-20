"""Unit tests for the production read-only AWS provider and collectors."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, patch

from collectors.cloudwatch_collector import CloudWatchAlarmCollector
from collectors.dynamodb_collector import DynamoDBCollector
from collectors.eventbridge_collector import EventBridgeCollector
from collectors.iam_collector import IAMCollector
from collectors.lambda_collector import LambdaCollector
from collectors.s3_collector import S3Collector
from collectors.sns_collector import SNSCollector
from collectors.sqs_collector import SQSCollector
from models import SnapshotResource
from providers.aws_provider import AWSIdentityError, AWSProvider
from providers.demo_provider import DemoProvider
from snapshot.collector import load_provider


class Pages:
    def __init__(self, pages):
        self._pages = pages

    def paginate(self, **kwargs):
        return iter(self._pages)


class AWSCollectorTests(unittest.TestCase):
    def assert_valid(self, resources, resource_type):
        self.assertTrue(resources)
        for resource in resources:
            resource.validate()
            self.assertEqual(resource.resource_type, resource_type)

    def test_lambda_collector_success_and_environment_redaction(self):
        client = Mock()
        client.get_paginator.return_value = Pages([
            {"Functions": [{"FunctionName": "worker-two", "PackageType": "Zip"}]},
            {"Functions": [{
                "FunctionName": "worker", "Runtime": "python3.12", "MemorySize": 256,
                "LastModified": datetime.now(timezone.utc), "CodeSize": Decimal("10"),
                "Architectures": ["x86_64"],
                "EphemeralStorage": {"Size": 1024},
                "Layers": [
                    {"Arn": "arn:layer:z", "CodeSize": 20},
                    {"Arn": "arn:layer:a", "CodeSize": 10},
                ],
                "SnapStart": {"ApplyOn": "PublishedVersions", "OptimizationStatus": "On"},
                "Environment": {"Variables": {"SECRET": "not-collected", "MODE": "prod"}},
            }]},
        ])
        resources = LambdaCollector(client).collect()
        self.assert_valid(resources, "AWS::Lambda::Function")
        self.assertEqual([resource.logical_name for resource in resources], ["worker", "worker-two"])
        self.assertEqual(resources[0].properties["EnvironmentKeys"], ["MODE", "SECRET"])
        self.assertEqual(resources[0].properties["MemorySize"], 256)
        self.assertEqual(resources[0].properties["EphemeralStorage"], {"Size": 1024})
        self.assertEqual(resources[0].properties["Layers"], ["arn:layer:a", "arn:layer:z"])
        self.assertEqual(resources[0].properties["SnapStart"], {"ApplyOn": "PublishedVersions"})
        self.assertNotIn("not-collected", str(resources[0].to_dict()))
        self.assertNotIn("CodeSize", str(resources[0].to_dict()))
        self.assertNotIn("LastModified", resources[0].properties)
        self.assertEqual(len(resources), 2)

    def test_s3_collector_success_region_filter_and_configuration(self):
        client = Mock()
        client.list_buckets.return_value = {"Buckets": [{"Name": "west"}, {"Name": "east"}]}
        client.get_bucket_location.side_effect = [
            {"LocationConstraint": "us-west-2"}, {"LocationConstraint": None}
        ]
        client.get_bucket_versioning.return_value = {"Status": "Enabled", "ResponseMetadata": {}}
        client.get_bucket_encryption.return_value = {
            "ServerSideEncryptionConfiguration": {"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}
        }
        client.get_public_access_block.return_value = {
            "PublicAccessBlockConfiguration": {"BlockPublicAcls": True}
        }
        client.get_bucket_tagging.return_value = {"TagSet": [{"Key": "b", "Value": "2"}, {"Key": "a", "Value": "1"}]}
        resources = S3Collector(client, "us-east-1").collect()
        self.assert_valid(resources, "AWS::S3::Bucket")
        self.assertEqual(resources[0].logical_name, "east")
        self.assertEqual(resources[0].properties["Tags"][0]["Key"], "a")
        client.get_bucket_versioning.assert_called_once_with(Bucket="east")

    def test_iam_collector_success_with_paginated_policies(self):
        client = Mock()
        paginators = {
            "list_roles": Pages([{"Roles": [{
                "RoleName": "app", "Arn": "arn:role/app", "CreateDate": datetime.now(timezone.utc),
                "AssumeRolePolicyDocument": '{"Statement":[{"Action":["z","a"]}]}'
            }]}]),
            "list_attached_role_policies": Pages([
                {"AttachedPolicies": [{"PolicyName": "z", "PolicyArn": "arn:z"}]},
                {"AttachedPolicies": [{"PolicyName": "a", "PolicyArn": "arn:a"}]},
            ]),
            "list_role_policies": Pages([{"PolicyNames": ["inline"]}]),
        }
        client.get_paginator.side_effect = lambda name: paginators[name]
        client.get_role_policy.return_value = {"PolicyDocument": {"Statement": [{"Effect": "Allow"}]}}
        resources = IAMCollector(client).collect()
        self.assert_valid(resources, "AWS::IAM::Role")
        self.assertEqual([item["PolicyName"] for item in resources[0].properties["AttachedPolicies"]], ["a", "z"])
        self.assertNotIn("CreateDate", resources[0].properties)

    def test_dynamodb_collector_success_and_paginated_tables(self):
        client = Mock()
        client.get_paginator.return_value = Pages([{"TableNames": ["a"]}, {"TableNames": ["b"]}])
        client.describe_table.side_effect = [
            {"Table": {"TableName": "a", "TableArn": "arn:a", "ItemCount": 99,
                       "BillingModeSummary": {"BillingMode": "PAY_PER_REQUEST"}}},
            {"Table": {"TableName": "b", "TableArn": "arn:b", "TableSizeBytes": 123}},
        ]
        resources = DynamoDBCollector(client).collect()
        self.assert_valid(resources, "AWS::DynamoDB::Table")
        self.assertEqual([resource.logical_name for resource in resources], ["a", "b"])
        self.assertNotIn("ItemCount", resources[0].properties)
        self.assertNotIn("TableSizeBytes", resources[1].properties)

    def test_cloudwatch_collector_success_for_both_alarm_types(self):
        client = Mock()
        client.get_paginator.return_value = Pages([{
            "MetricAlarms": [{"AlarmName": "metric", "StateValue": "ALARM", "AlarmActions": ["z", "a"],
                              "Dimensions": [{"Name": "B", "Value": "2"}, {"Name": "A", "Value": "1"}]}],
            "CompositeAlarms": [{"AlarmName": "composite", "AlarmRule": "ALARM(metric)"}],
        }])
        resources = CloudWatchAlarmCollector(client).collect()
        self.assertEqual({resource.resource_type for resource in resources}, {
            "AWS::CloudWatch::Alarm", "AWS::CloudWatch::CompositeAlarm"
        })
        for resource in resources:
            resource.validate()
        metric = next(resource for resource in resources if resource.logical_name == "metric")
        self.assertEqual(metric.properties["AlarmActions"], ["a", "z"])
        self.assertNotIn("StateValue", metric.properties)

    def test_eventbridge_collector_success_and_paginated_buses_rules(self):
        client = Mock()
        client.list_event_buses.side_effect = [
            {"EventBuses": [{"Name": "default"}], "NextToken": "next-page"},
            {"EventBuses": [{"Name": "custom"}]},
        ]
        rule_pages = {
            "default": Pages([{"Rules": [{"Name": "daily", "EventPattern": '{"source":["z","a"]}'}]}]),
            "custom": Pages([{"Rules": []}]),
        }
        client.get_paginator.return_value = Mock(
            paginate=lambda **kwargs: rule_pages[kwargs["EventBusName"]].paginate()
        )
        resources = EventBridgeCollector(client).collect()
        self.assert_valid(resources, "AWS::Events::Rule")
        self.assertEqual(resources[0].logical_name, "default/daily")
        self.assertEqual(resources[0].properties["EventPattern"]["source"], ["a", "z"])
        self.assertEqual(client.list_event_buses.call_count, 2)
        client.list_event_buses.assert_any_call()
        client.list_event_buses.assert_any_call(NextToken="next-page")
        self.assertEqual(client.get_paginator.call_args_list[0].args, ("list_rules",))

    def test_sns_collector_success(self):
        client = Mock()
        client.get_paginator.return_value = Pages([{"Topics": [{"TopicArn": "arn:topic"}]}])
        client.get_topic_attributes.return_value = {"Attributes": {
            "DisplayName": "alerts", "SubscriptionsConfirmed": "25",
            "Policy": '{"Statement":[{"Action":["z","a"]}]}'
        }}
        resources = SNSCollector(client).collect()
        self.assert_valid(resources, "AWS::SNS::Topic")
        self.assertEqual(resources[0].logical_name, "arn:topic")
        self.assertNotIn("SubscriptionsConfirmed", resources[0].properties)

    def test_sqs_collector_success(self):
        client = Mock()
        client.get_paginator.return_value = Pages([{"QueueUrls": ["https://sqs.us-east-1.amazonaws.com/123/jobs.fifo"]}])
        client.get_queue_attributes.return_value = {"Attributes": {
            "QueueArn": "arn:queue", "ApproximateNumberOfMessages": "9",
            "RedrivePolicy": '{"maxReceiveCount":5,"deadLetterTargetArn":"arn:dlq"}'
        }}
        resources = SQSCollector(client).collect()
        self.assert_valid(resources, "AWS::SQS::Queue")
        self.assertEqual(resources[0].logical_name, "jobs.fifo")
        self.assertNotIn("ApproximateNumberOfMessages", resources[0].properties)

    def test_empty_account_and_api_failure_return_empty(self):
        empty_client = Mock()
        empty_client.get_paginator.return_value = Pages([{}, {"Functions": []}])
        self.assertEqual(LambdaCollector(empty_client).collect(), [])

        failed_client = Mock()
        failed_client.get_paginator.side_effect = RuntimeError("raw secret response")
        with self.assertLogs("collectors", level="ERROR") as logs:
            self.assertEqual(LambdaCollector(failed_client).collect(), [])
        output = "\n".join(logs.output)
        self.assertIn("service=lambda", output)
        self.assertIn("operation=list_functions", output)
        self.assertIn("error_type=RuntimeError", output)
        self.assertNotIn("raw secret response", output)

    def test_each_collector_sorts_resources_before_returning(self):
        cases = []

        s3 = Mock()
        s3.list_buckets.return_value = {"Buckets": [{"Name": "z"}, {"Name": "a"}]}
        s3.get_bucket_location.return_value = {"LocationConstraint": None}
        s3.get_bucket_versioning.return_value = {}
        s3.get_bucket_encryption.return_value = {}
        s3.get_public_access_block.return_value = {}
        s3.get_bucket_tagging.return_value = {}
        cases.append(("s3", S3Collector(s3, "us-east-1"), ["a", "z"]))

        iam = Mock()
        iam.get_paginator.side_effect = lambda operation: Pages([{
            "Roles": [{"RoleName": "z"}, {"RoleName": "a"}]
        }]) if operation == "list_roles" else Pages([{}])
        cases.append(("iam", IAMCollector(iam), ["a", "z"]))

        dynamodb = Mock()
        dynamodb.get_paginator.return_value = Pages([{"TableNames": ["z", "a"]}])
        dynamodb.describe_table.side_effect = lambda TableName: {"Table": {"TableName": TableName}}
        cases.append(("dynamodb", DynamoDBCollector(dynamodb), ["a", "z"]))

        cloudwatch = Mock()
        cloudwatch.get_paginator.return_value = Pages([{
            "MetricAlarms": [{"AlarmName": "z"}, {"AlarmName": "a"}]
        }])
        cases.append(("cloudwatch", CloudWatchAlarmCollector(cloudwatch), ["a", "z"]))

        events = Mock()
        events.list_event_buses.return_value = {
            "EventBuses": [{"Name": "z"}, {"Name": "a"}]
        }
        events.get_paginator.return_value = Pages([{"Rules": [{"Name": "rule"}]}])
        cases.append(("events", EventBridgeCollector(events), ["a/rule", "z/rule"]))

        sns = Mock()
        sns.get_paginator.return_value = Pages([{
            "Topics": [{"TopicArn": "arn:z"}, {"TopicArn": "arn:a"}]
        }])
        sns.get_topic_attributes.return_value = {"Attributes": {}}
        cases.append(("sns", SNSCollector(sns), ["arn:a", "arn:z"]))

        sqs = Mock()
        sqs.get_paginator.return_value = Pages([{
            "QueueUrls": ["https://sqs.example/123/z", "https://sqs.example/123/a"]
        }])
        sqs.get_queue_attributes.return_value = {"Attributes": {}}
        cases.append(("sqs", SQSCollector(sqs), ["a", "z"]))

        for service, collector, expected in cases:
            with self.subTest(service=service):
                self.assertEqual(
                    [resource.logical_name for resource in collector.collect()],
                    expected,
                )

    def test_every_collector_returns_empty_on_api_failure(self):
        factories = (
            ("lambda", lambda client: LambdaCollector(client)),
            ("s3", lambda client: S3Collector(client, "us-east-1")),
            ("iam", lambda client: IAMCollector(client)),
            ("dynamodb", lambda client: DynamoDBCollector(client)),
            ("cloudwatch", lambda client: CloudWatchAlarmCollector(client)),
            ("events", lambda client: EventBridgeCollector(client)),
            ("sns", lambda client: SNSCollector(client)),
            ("sqs", lambda client: SQSCollector(client)),
        )
        for service, factory in factories:
            with self.subTest(service=service):
                client = Mock()
                client.get_paginator.side_effect = RuntimeError("sensitive provider detail")
                client.list_buckets.side_effect = RuntimeError("sensitive provider detail")
                client.list_event_buses.side_effect = RuntimeError("sensitive provider detail")
                with self.assertLogs("collectors", level="ERROR") as logs:
                    self.assertEqual(factory(client).collect(), [])
                self.assertNotIn("sensitive provider detail", "\n".join(logs.output))


class AWSProviderTests(unittest.TestCase):
    def test_aggregation_partial_failure_stable_order_and_environment(self):
        sts = Mock()
        sts.get_caller_identity.return_value = {"Account": "123456789012"}

        class Good:
            def __init__(self, client):
                self.client = client

            def collect(self):
                return [SnapshotResource("Z::Type", "z", {}), SnapshotResource("A::Type", "b", {})]

        class Bad:
            def __init__(self, client):
                self.client = client

            def collect(self):
                raise RuntimeError("sensitive collection detail")

        clients = {"sts": sts, "good": Mock(), "bad": Mock()}
        with patch.dict("os.environ", {"AWS_REGION": "us-east-1"}, clear=True):
            provider = AWSProvider(clients=clients, collector_factories=(("good", Good), ("bad", Bad)))
            with self.assertLogs("providers.aws_provider", level="ERROR") as logs:
                resources = provider.collect_resources()
            self.assertEqual(provider.environment, "aws:123456789012:us-east-1")
        self.assertEqual([(item.resource_type, item.logical_name) for item in resources], [("A::Type", "b"), ("Z::Type", "z")])
        self.assertEqual(sts.get_caller_identity.call_count, 1)
        log_output = "\n".join(logs.output)
        self.assertIn("service=bad", log_output)
        self.assertNotIn("sensitive collection detail", log_output)

    def test_one_lazy_session_is_shared_across_clients(self):
        session = Mock(region_name="us-west-2")
        sts = Mock()
        sts.get_caller_identity.return_value = {"Account": "123456789012"}
        service_client = Mock()
        session.client.side_effect = lambda service, region_name: sts if service == "sts" else service_client
        provider = AWSProvider(session=session, collector_factories=())
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(provider.environment, "aws:123456789012:us-west-2")
            self.assertEqual(provider.environment, "aws:123456789012:us-west-2")
        self.assertEqual(session.client.call_count, 1)
        self.assertEqual(sts.get_caller_identity.call_count, 1)

    def test_identity_failure_is_sanitized_and_fails(self):
        sts = Mock()
        sts.get_caller_identity.side_effect = RuntimeError("credential material")
        with patch.dict("os.environ", {"AWS_REGION": "us-east-1"}, clear=True):
            provider = AWSProvider(clients={"sts": sts}, collector_factories=())
            with self.assertLogs("providers.aws_provider", level="ERROR") as logs:
                with self.assertRaisesRegex(AWSIdentityError, "^AWS identity could not be established$"):
                    provider.collect_resources()
        self.assertNotIn("credential material", "\n".join(logs.output))
        self.assertEqual(sts.get_caller_identity.call_count, 1)

    def test_load_provider_aws_is_network_free_and_demo_unchanged(self):
        with patch.dict("os.environ", {}, clear=True):
            provider = load_provider("aws")
        self.assertIsInstance(provider, AWSProvider)
        self.assertEqual(provider.name, "aws")
        first = [resource.to_dict() for resource in DemoProvider().collect_resources()]
        second = [resource.to_dict() for resource in DemoProvider().collect_resources()]
        self.assertEqual(first, second)
        self.assertEqual(len(first), 3)


if __name__ == "__main__":
    unittest.main()
