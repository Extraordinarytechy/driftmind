# AWS Services

DriftMind uses managed AWS services at narrow boundaries. This document distinguishes implemented application integrations from infrastructure that the repository does not provision.

## Amazon EventBridge
**Status:** Intended, not provisioned.
EventBridge is the planned recurring trigger for the EventBridge-compatible Lambda handler. Schedule expressions, retry policy, dead-letter behavior, and infrastructure as code remain deployment work.

## AWS Lambda
**Status:** Autonomous application path implemented.
The Python 3.12 handler coordinates snapshot collection and storage, previous-snapshot discovery, deterministic comparison, cost-aware decisions, conditional Bedrock/SES work, and report storage. It emits redacted lifecycle logs and preserves the original snapshot success fields while adding autonomous metadata. Memory, timeout, concurrency, ephemeral storage, and deployment configuration are not provisioned here.

## Amazon S3
**Status:** Snapshot, history, and report adapters implemented.
The application conditionally writes AES256-encrypted snapshots under `snapshots/` and schema `1.0` autonomous reports under `reports/`. History discovery paginates canonical snapshot keys and selects the latest key strictly older than the current snapshot; the comparator validates compatibility. Bucket creation, policies, public-access controls, versioning, lifecycle rules, and an explicit successful-baseline promotion marker remain external.

## Amazon Bedrock Runtime
**Status:** Drift-gated Converse integration implemented.
Bedrock receives only a bounded deterministic change report, never performs change detection, and is never invoked for baseline or healthy runs. The autonomous parser requires exact summary, explanation, impact, risk, and recommendation fields, with risk restricted to `Low`, `Medium`, `High`, or `Critical`. Model access, Region availability, guardrails, quotas, and pricing remain deployment concerns.

## Amazon Simple Email Service (SES)
**Status:** Drift-only delivery adapter implemented.
After successful drift analysis, SES receives an escaped UTF-8 multipart alert containing deterministic changes, risk, AI summary, impact, and recommendations. Baseline and healthy runs never invoke SES. Identity verification, sandbox exit, quotas, suppression handling, and retry/idempotency policy remain deployment concerns. S3 reports—not email—are the source of record.

## Amazon CloudWatch
**Status:** Lifecycle logging and read-only alarm collection implemented; custom observability not implemented.
When deployed, Lambda logs include baseline loading, comparison completion, change count, Bedrock invocation state, report storage, and SES delivery state without report bodies, model output, addresses, credentials, or raw provider messages. `AWSProvider` also discovers metric and composite alarm configuration through `DescribeAlarms`. Custom metrics, dashboards, managed alarms, correlation IDs, missing-run detection, and log-retention configuration are not supplied.

## Read-Only AWS Resource Discovery
**Status:** Eight service collectors implemented.
With `PROVIDER=aws`, DriftMind inventories Lambda functions, S3 buckets in the configured Region, IAM roles, DynamoDB tables, CloudWatch alarms, EventBridge rules, SNS topics, and SQS queues. Collectors paginate where supported, normalize stable configuration into the existing snapshot schema, sort deterministically, isolate service failures, and never make mutation calls. STS establishes the account identity used in the snapshot environment. See [AWS_PROVIDER_IAM.md](AWS_PROVIDER_IAM.md) for the minimum discovery permissions.

## Implemented Interaction Summary
1. An external invocation starts the Lambda handler; EventBridge is the intended unprovisioned trigger.
2. Lambda uses the configured `demo` or `aws` provider and stores the current snapshot in S3.
3. Lambda loads the latest older canonical snapshot from S3 and computes the deterministic diff.
4. Baseline and healthy runs store a report and stop without Bedrock or SES.
5. Drift runs send the bounded diff to Bedrock, validate the analysis, send an SES alert, and store delivery truth in the report.
6. CloudWatch can receive the handler's redacted logs when the function is deployed.

## Cross-Cutting Controls
IAM should grant the [minimum read-only discovery actions](AWS_PROVIDER_IAM.md), required S3 prefixes, selected Bedrock model access, configured SES identities, and logging actions. Service traffic uses TLS and S3 writes request encryption at rest. The watcher has no permission or code path to mutate observed infrastructure. No additional AWS service is required by the implemented workflow.
