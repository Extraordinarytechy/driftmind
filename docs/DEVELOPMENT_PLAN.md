# DriftMind Development Plan

Development is incremental. Each phase must preserve deterministic behavior, traceability, least-privilege access, and Python 3.12 compatibility. Application phases will use `boto3`; infrastructure-as-code choices are intentionally outside Phase 1.

## Phase 1 — Repository

**Goal:** Establish a stable, professional open-source project foundation.

**Inputs:** Product vision, challenge requirements, architectural assumptions, and coding standards.

**Outputs:** Agreed scope, architecture, service rationale, phased delivery plan, and article outline.

**Deliverables:**
- Repository structure and ignore rules
- README, Apache 2.0 license, and dependency manifest
- Project specification, development plan, AWS service rationale, and architecture document
- AWS Builder Center article skeleton
- Empty tracked directories for future code and artifacts

## Phase 2 — Infrastructure Snapshot Engine

**Status:** Completed.

**Goal:** Produce a deterministic, normalized, schema-validated snapshot and persist it to an externally provisioned S3 bucket.

**Inputs:** `SNAPSHOT_BUCKET`, `AWS_REGION`, and `PROVIDER` environment variables; schema version `1.0`; and the deterministic demo resource inventory.

**Outputs:** UTF-8 JSON containing exactly `schema_version`, `generated_at`, `provider`, `environment`, and `resources`, stored at `snapshots/YYYY/MM/DD/snapshot-<timestamp>.json`.

**Delivered:**
- Python 3.12 provider interface and deterministic `DemoProvider`
- Explicit unimplemented `AWSProvider` boundary with no AWS resource API calls
- Dataclass snapshot and resource models with UTC, identity, and JSON-value validation
- Canonical resource/property ordering and deterministic serialization
- Environment-only configuration and cohesive collector/storage boundaries
- S3 upload through `boto3`, AES256 server-side encryption, and conditional object creation
- Structured logging for provider loading, generation, validation, upload, and failures
- Unit coverage for models, provider behavior, collection, serialization, mocked S3 upload, and local pipeline execution

## Phase 3 — Diff Engine

**Goal:** Compare compatible snapshots and emit a deterministic, machine-readable change set.

**Inputs:** Current snapshot, latest valid baseline, identity rules, and ignored-field policy.

**Outputs:** Added, removed, and modified resources with before/after evidence and summary counts.

**Deliverables:**
- Baseline discovery and schema compatibility checks
- Pure comparison engine independent of Bedrock
- First-run and no-change behavior
- Size limits and deterministic diff serialization
- Focused tests for identity, ordering, and edge cases

## Phase 4 — Bedrock Intelligence

**Status:** Completed.

**Goal:** Turn a validated structured diff into a grounded, typed executive analysis through Amazon Bedrock.

**Inputs:** A validated Phase 3 `ChangeReport`; prompt version `1.0`; required `AWS_REGION` and `BEDROCK_MODEL_ID`; optional validated temperature and token settings; and the strict response schema.

**Outputs:** `ExecutiveAnalysis` with `summary`, `security_impact`, `operational_impact`, `cost_impact`, and typed `recommendations`.

**Delivered:**
- Deterministic prompt builder containing agent identity, project purpose, delimited diff evidence, grounding rules, and exact JSON output schema
- Fixed 100,000-byte input bound that rejects oversized reports without corrupting deterministic evidence
- Environment-only Bedrock Runtime Converse client with explicit model, temperature, and maximum-token settings
- Structured invocation response metadata and failure wrapping that omits provider details and credentials
- Strict JSON parser rejecting malformed/nonstandard JSON, duplicate/missing/extra fields, invalid field types, and invalid recommendations
- Frozen dataclass models for executive analysis and recommendations
- Cohesive service orchestration with lifecycle and failure logging
- Fully mocked tests for prompt determinism, parser success/failures, model invocation/failure, and service orchestration

## Phase 5 — Email Reporting

**Status:** Completed.

**Goal:** Convert validated executive analysis into accessible HTML and plain-text reports and deliver them through Amazon SES.

**Inputs:** A validated `ExecutiveAnalysis`; an aware generation timestamp; and required `AWS_REGION`, `SES_SENDER`, and `SES_RECIPIENT` environment variables.

**Outputs:** A validated `NotificationRequest`, a UTF-8 `multipart/alternative` message, and a `NotificationResult` containing the SES message ID and `sent` status.

**Delivered:**
- Deterministic plain-text and semantic HTML formatters with matching report sections
- Correct escaping of all model-provided HTML content and no external CSS or JavaScript
- Frozen typed models for formatted notification requests and successful delivery results
- Environment-only SES configuration with plain-address and header-injection validation
- Deterministic MIME multipart generation containing text and HTML alternatives
- Lazy `boto3` SES client creation and `send_raw_email` delivery
- Sanitized provider failure handling with no raw provider exception chain
- Cohesive formatting-to-delivery service orchestration and lifecycle logging
- Fully mocked tests for both formats, SES success/failure, MIME structure, and service orchestration

Persisted idempotency, retries, retry queues, CloudWatch alarms, scheduling, and alternate notification channels are not implemented in this phase.

## Phase 6 — Documentation

**Goal:** Publish accurate project, deployment, operations, security, and challenge documentation based only on validated behavior.

**Inputs:** Completed implementation, architecture decisions, tests, deployment procedure, operational evidence, cost observations, and real screenshots where useful.

**Outputs:** Release-ready open-source documentation and a completed AWS Builder Center article.

**Deliverables:**
- Updated README and architecture diagram
- Deployment, configuration, security, operations, and troubleshooting guides
- Supported-resource and known-limitation documentation
- Contribution guidance and release notes
- Completed Builder Center article with verified results and authentic screenshots

## Phase Completion Policy

A phase is complete when its deliverables are reviewed, relevant automated checks pass, failure behavior is documented, and downstream phases can rely on its output contract. Generated examples, screenshots, metrics, or claims must not be presented as real before they are produced by the implemented system.
