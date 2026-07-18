# DriftMind Architecture

## Architectural Intent

DriftMind is a scheduled, evidence-driven infrastructure intelligence workflow. It separates deterministic state collection and comparison from probabilistic language-model analysis. This boundary allows every generated statement to be traced back to a stored snapshot and explicit diff.

The initial deployment targets one configured AWS account and Region. Resource coverage will expand incrementally behind versioned schemas and stable resource identity rules.

## System Context

- **Operator:** Configures scope, schedule, report recipients, and supported resource types.
- **AWS account:** Provides read-only resource metadata and hosts the managed workflow services.
- **Email recipient:** Receives an executive summary and follows links or identifiers for deeper review.
- **DriftMind:** Observes and explains; it does not mutate infrastructure.

## Components

### Scheduler

Amazon EventBridge starts each run using a configured schedule. The event carries only invocation metadata. Concurrency controls prevent overlapping runs from racing to select or promote a baseline.

### Workflow Runtime

AWS Lambda runs Python 3.12 and coordinates the workflow through `boto3`. Logical modules will isolate configuration, collectors, normalization, storage, comparison, Bedrock interaction, report formatting, and delivery even if the first deployment uses one function.

### Snapshot Store

Amazon S3 stores immutable JSON snapshots. The Phase 2 storage adapter writes UTF-8 JSON with AES256 server-side encryption and `If-None-Match: *`, preventing an existing key from being silently overwritten. The bucket and Region come exclusively from `SNAPSHOT_BUCKET` and `AWS_REGION`.

### Diff Engine

The implemented Phase 3 engine is a pure, deterministic Python component. It compares resources by the case-sensitive identity `(resource_type, logical_name)`, emits one entry for each added or removed resource, and recursively compares every property of identities present in both snapshots. Dictionary properties produce dotted field paths; lists are ordered values and are reported as one field when changed. Unchanged resources and properties are omitted.

### Intelligence Layer

The implemented Phase 4 intelligence service accepts only a validated Phase 3 `ChangeReport`. Its version `1.0` deterministic prompt identifies DriftMind and the Infrastructure Intelligence Analyst role, includes the complete canonical diff as delimited data, and instructs the model to avoid invented infrastructure, speculation, and unsupported conclusions. Reports larger than 100,000 UTF-8 bytes are rejected rather than truncated into inconsistent evidence.

The Bedrock wrapper uses the Runtime Converse API. `AWS_REGION` and `BEDROCK_MODEL_ID` are required environment variables; `BEDROCK_TEMPERATURE` and `BEDROCK_MAX_TOKENS` are optional validated settings. The wrapper logs model ID, prompt size, request ID, stop reason, and error type, but never logs prompt content, model output, AWS credentials, or provider exception details.

Model output must be strict JSON with exactly `summary`, `security_impact`, `operational_impact`, `cost_impact`, and `recommendations`. The parser rejects malformed or nonstandard JSON, duplicate/missing/extra fields, invalid scalar types, and invalid recommendation entries, then returns a typed `ExecutiveAnalysis`. Prompt grounding reduces unsupported claims; structural validation does not independently prove model claims.

### Report Delivery

The reporting component combines deterministic counts with validated Bedrock analysis and sends a plain, accessible executive summary through Amazon SES. Delivery status is recorded against the run identifier. Recipient configuration remains external to source control.

### Observability

Amazon CloudWatch receives structured logs, service metrics, and alarms. Logs correlate events by run identifier while excluding secrets and unnecessary resource data. Metrics cover run success, duration, resources observed, changes detected, Bedrock failures, and email-delivery failures.

## Implemented Phase 2 Data Flow

1. The Lambda handler loads `SNAPSHOT_BUCKET`, `AWS_REGION`, and `PROVIDER` from environment variables.
2. The collector loads the configured provider. Phase 2 supports only `demo` execution.
3. `DemoProvider` returns deterministic normalized models for an EC2 instance, security group, and S3 bucket without AWS API calls.
4. The collector creates a UTC timestamped schema `1.0` snapshot and validates its fields, resource identities, and JSON-compatible properties.
5. The serializer emits deterministic UTF-8 JSON.
6. The storage adapter conditionally uploads the object to `snapshots/YYYY/MM/DD/snapshot-<timestamp>.json`.
7. The handler returns a structured result containing snapshot identity, resource count, and S3 location. Failures are logged and returned as structured errors.

## Implemented Phase 3 Data Flow

1. The local loader reads the previous and current UTF-8 JSON files.
2. It requires the exact Phase 2 snapshot and resource fields, reconstructs the existing dataclass models, and validates both snapshots.
3. The comparator requires matching `schema_version`, `provider`, and `environment` values.
4. It indexes resources by `(resource_type, logical_name)` and detects additions and removals.
5. It recursively compares properties for shared resource identities and ignores unchanged values.
6. It orders added entries first, removed entries second, and modified entries last; each category is ordered by resource identity and modified field path.
7. Stable sequential IDs are assigned as `CHG-0001`, `CHG-0002`, and so on.
8. The report serializer emits deterministic UTF-8 JSON containing no natural-language summary.

Phase 3 loads explicit local files only. It does not scan S3 history or choose a previous snapshot.

## Implemented Phase 4 Data Flow

1. `IntelligenceService` receives and validates a Phase 3 change report.
2. The prompt builder serializes the report deterministically, applies the fixed byte bound, and creates the grounded versioned prompt.
3. `BedrockClient` loads model configuration from environment variables and invokes the model through `bedrock-runtime.converse`.
4. The client extracts model text and returns structured invocation metadata without exposing credentials or raw provider errors.
5. The parser requires strict JSON and validates the exact executive-analysis schema.
6. The service returns a typed `ExecutiveAnalysis` containing four impact strings and typed recommendations.

Phase 4 does not send notifications, score risk, select models automatically, or alter deterministic diff evidence.

## End-to-End Data Flow

1. EventBridge invokes Lambda with schedule and invocation metadata.
2. Lambda validates configuration and acquires run context.
3. Collectors query allow-listed AWS APIs with paginated, read-only `boto3` calls.
4. The workflow normalizes responses, validates completeness, and writes the candidate snapshot to S3.
5. Lambda locates the latest compatible complete baseline in S3.
6. The diff engine produces a canonical change set or identifies a first/no-change run.
7. For eligible changes, Lambda sends the bounded diff to Bedrock and validates the response.
8. The report formatter combines deterministic evidence with the labeled model analysis.
9. SES sends the report to configured verified recipients.
10. Lambda records delivery and final run status; CloudWatch metrics and alarms reflect the outcome.
11. The complete current snapshot is available as a baseline for the next run.

## Artifact and Contract Design

The implemented schema `1.0` snapshot contains exactly five top-level fields: `schema_version`, `generated_at`, `provider`, `environment`, and `resources`. Each resource contains `resource_type`, `logical_name`, and `properties`. Resource identity is the pair of type and logical name; duplicate identities are invalid. Resources and nested property keys are serialized in canonical order.

`generated_at` is a timezone-aware UTC ISO 8601 timestamp. The same timestamp determines the immutable object key: `snapshots/YYYY/MM/DD/snapshot-<timestamp>.json`.

The Phase 3 report contains exactly `summary` and `changes`. `summary` contains numeric `total_changes`, `added`, `removed`, and `modified` counts; modified counts property-level entries. Every change contains exactly `change_id`, `change_type`, `resource_type`, `logical_name`, `field`, `old`, and `new`. Added resources use `old: null`, removed resources use `new: null`, and both use `field: null`; their non-null side contains the complete properties object. Modified entries contain a dotted property path and the field's before/after values. An unchanged comparison has zero counts and an empty `changes` array.

## Failure and Consistency Model

- Configuration or schema errors fail fast before model invocation or email delivery.
- AWS API throttling and transient service faults receive bounded retries with jitter.
- Access denial and unsupported-resource responses are explicit collection failures, not empty resource sets.
- A partial collection may be retained for diagnostics but cannot replace the valid baseline.
- S3 writes use unique run keys; baseline discovery considers only complete compatible artifacts.
- First runs establish a baseline and never fabricate a change report.
- Bedrock failure does not alter deterministic diff evidence; a labeled fallback report may be sent.
- SES failure is tracked separately from analysis success to support safe retry without recomputation.
- Correlation identifiers make repeated or retried invocations traceable, and idempotency controls prevent duplicate promotion and delivery.

## Security and Privacy

The Lambda execution role follows least privilege for observed APIs, S3 prefixes, the selected Bedrock model, SES identities, and CloudWatch. DriftMind is read-only with respect to observed infrastructure. S3 block-public-access and encryption are expected defaults; all service calls use TLS. Logs and model inputs exclude credentials, secrets, and unnecessary resource attributes. Configuration values and recipient addresses are not committed to the repository.

## Scalability and Cost Boundaries

Collection scope and schedule frequency are configuration boundaries. Pagination, resource caps, diff-size limits, and model token budgets keep work bounded. S3 lifecycle rules control retention costs. Reserved concurrency can prevent overlapping executions and runaway invocation. If broader multi-account collection exceeds Lambda duration or payload constraints, a future architecture can introduce distributed orchestration without changing snapshot and diff contracts.

## Deployment Boundaries

This phase defines architecture only and creates no AWS resources. A later phase will select and document infrastructure as code, deployment Regions, supported resource types, IAM policies, model configuration, SES identity requirements, retention periods, alarms, and cost estimates.

## Future Architecture Diagram

> **Diagram placeholder:** Add the final architecture diagram here after the AWS resources, trust boundaries, data paths, failure paths, and deployment topology have been implemented and verified. Do not use a speculative diagram as implementation evidence.

The final diagram should show the operator, EventBridge, Lambda logical modules, observed AWS APIs, S3 artifact boundaries, Bedrock request/response path, SES recipients, CloudWatch telemetry, IAM trust boundaries, encryption, and any dead-letter or retry mechanism selected during implementation.

## Future Evolution

Potential extensions include AWS Organizations-based multi-account collection, multiple Regions, additional collector plug-ins, historical trend analysis, deployment-event correlation, alternate notification channels, and human-approved remediation. Any write capability would require a separate threat model, explicit authorization, and independent safety controls.
