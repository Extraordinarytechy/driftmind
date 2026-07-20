# AWSProvider Minimum IAM Permissions

`PROVIDER=aws` performs read-only inventory calls. It never creates, updates, or deletes observed resources. The Lambda execution role needs its existing runtime permissions plus the discovery actions below.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DriftMindReadOnlyDiscovery",
      "Effect": "Allow",
      "Action": [
        "sts:GetCallerIdentity",
        "lambda:ListFunctions",
        "s3:ListAllMyBuckets",
        "s3:GetBucketLocation",
        "s3:GetBucketVersioning",
        "s3:GetEncryptionConfiguration",
        "s3:GetBucketPublicAccessBlock",
        "s3:GetBucketTagging",
        "iam:ListRoles",
        "iam:ListAttachedRolePolicies",
        "iam:ListRolePolicies",
        "iam:GetRolePolicy",
        "dynamodb:ListTables",
        "dynamodb:DescribeTable",
        "cloudwatch:DescribeAlarms",
        "events:ListEventBuses",
        "events:ListRules",
        "sns:ListTopics",
        "sns:GetTopicAttributes",
        "sqs:ListQueues",
        "sqs:GetQueueAttributes"
      ],
      "Resource": "*"
    }
  ]
}
```

This is the minimum action set used by the eight collectors. Broad inventory operations require `Resource: "*"`; resource-level conditions may be added where AWS supports them. Keep the existing S3 snapshot/report, Bedrock, SES, and CloudWatch Logs permissions separately scoped to their configured resources.

STS supplies the account ID and the configured SDK Region supplies the Region, producing snapshot environments in the form `aws:<account-id>:<region>`. S3 bucket listing is global, but DriftMind retains only buckets whose location matches the configured Region. Collector failures are logged using service, operation, and exception type only; raw AWS responses and exception messages are not logged.