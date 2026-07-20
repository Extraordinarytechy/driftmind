# DriftMind Architecture

## Architectural Intent
DriftMind is an evidence-first infrastructure watcher. Deterministic Python code collects, validates, stores, and compares state before generative analysis is considered. The repository implements the autonomous Lambda processing path and read-only live AWS discovery; EventBridge scheduling and infrastructure as code remain separate deployment work.

## System Context
- **Operator:** Configures an existing bucket, model, SES identities, provider, and an external invocation schedule.
- **Observed environment:** Supplies normalized resource metadata through deterministic `DemoProvider` execution or read-only `AWSProvider` discovery in one account and Region.
- **Email recipient:** Receives an alert only when deterministic drift has valid Bedrock analysis.
- **Read-only consumer:** Reads generated objects under `reports/`; it never triggers scans.
- **DriftMind:** Observes and explains. It does not remediate infrastructure.

## Runtime and Components
### Trigger and workflow runtime
Amazon EventBridge is the intended recurring trigger but is not provisioned by this repository. `lambda.app.lambda_handler` is EventBridge-compatible because it does not depend on event contents. The Python 3.12 Lambda path is implemented and coordinates collection, S3 storage, history loading, comparison, decisions, conditional Bedrock/SES work, and report persistence.
### Snapshot engine, providers, and S3
The collector validates schema `1.0` snapshots. `DemoProvider` supplies fixed network-free resources; `AWSProvider` uses one boto3 session and isolated read-only collectors for Lambda, S3, IAM, DynamoDB, CloudWatch alarms, EventBridge rules, SNS, and SQS. STS-derived account and configured Region form the snapshot environment, and every collector normalizes into the same resource schema with deterministic ordering. The storage adapter writes canonical UTF-8 JSON under `snapshots/YYYY/MM/DD/snapshot-<timestamp>.json` using AES256 encryption and `If-None-Match: *`. Bucket creation, policies, versioning, lifecycle rules, and deployment limits are outside the repository.
### Previous-snapshot discovery
`S3SnapshotHistory` paginates `list_objects_v2` under `snapshots/`, ignores noncanonical keys, and loads the latest canonical key strictly older than the current snapshot. The existing local JSON loader remains available. The comparator—not the S3 listing—enforces schema, provider, and environment compatibility.
### Deterministic diff and decision engine
The pure comparator identifies added and removed resource identities and recursively modified properties. Dictionaries produce dotted paths, lists remain ordered values, and stable IDs follow canonical ordering. The decision engine returns `BASELINE_CREATED`, `HEALTHY`, or `DRIFT_DETECTED`; only the last state enables Bedrock and SES.
### Bedrock intelligence
The drift path submits only a validated, bounded `ChangeReport` through the Bedrock Runtime Converse API. Strict JSON parsing requires exactly `executive_summary`, `change_explanation`, `potential_impact`, `risk_level`, and `recommendations`; risk is one of `Low`, `Medium`, `High`, or `Critical`. Baseline and healthy runs never construct or invoke this service.
### Reports and SES
Every completed run writes an immutable schema `1.0` report under `reports/YYYY/MM/DD/report-<timestamp>.json`. This frontend contract contains run status, resource count, grouped drift evidence, risk, AI fields, recommendations, snapshot keys, SES state, and an activity timeline. Drift-only SES alerts include deterministic changes, risk, AI summary, explanation, impact, and recommendations in escaped HTML and matching plain text.
### Observability
The workflow emits redacted lifecycle logs for previous-snapshot loading, comparison, change count, Bedrock invocation, report storage, and SES delivery. Lambda logs can flow to CloudWatch when deployed. Custom metrics, dashboards, alarms, run correlation IDs, and per-stage duration telemetry are not implemented.

## Implemented Data Flow
1. Lambda loads snapshot configuration and collects a validated current snapshot.
2. The current snapshot is conditionally stored at its existing canonical S3 key.
3. The workflow paginates S3 history and loads the latest older canonical snapshot, if any.
4. No prior snapshot creates `BASELINE_CREATED`; otherwise the deterministic comparator produces a `ChangeReport` and the decision engine selects `HEALTHY` or `DRIFT_DETECTED`.
5. Baseline and healthy runs skip Bedrock and SES and store a report.
6. Drift runs invoke Bedrock, validate the risk analysis, send one SES alert, and then store the final delivery state.
7. Bedrock or SES failure writes available drift evidence to a report before the error is re-raised to the Lambda boundary.
8. Successful responses preserve snapshot identity, resource count, and S3 location while adding pipeline status, change summary, Bedrock/SES flags, and report location.

## Contracts and Consistency
Snapshots, diffs, analyses, notifications, and reports use validated typed models. S3 keys and JSON serialization are deterministic; object creation is conditional. Reports under `reports/` are the source of truth for future read-only dashboards. The current snapshot can become the next older candidate even if a later Bedrock or SES stage failed; there is no separate completion marker or baseline-promotion state.

## Failure, Security, and Cost Boundaries
Configuration and schema errors fail closed. Provider messages are redacted from logs and public Lambda responses. Bedrock failures preserve deterministic drift evidence and skip SES; SES failures preserve validated analysis with `ses_sent: false`. Explicit retries, persistent delivery idempotency, concurrency control, fallback email, and retry queues are not implemented. Cost is bounded by always comparing locally and invoking Bedrock and SES only for detected drift.

## Deployment Boundaries
The repository supplies application code, read-only live collectors, unit tests, and a reproducible ZIP assembly process for `lambda.app.lambda_handler`. It does not provision EventBridge, S3, IAM, Lambda settings, Bedrock access, SES identities, or CloudWatch alarms. The intended topology is shown in [driftmind-architecture.svg](driftmind-architecture.svg) and [driftmind-architecture.png](driftmind-architecture.png); labels distinguish implemented processing from unprovisioned infrastructure.
