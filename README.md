# DriftMind

DriftMind is an AI-powered infrastructure intelligence agent for AWS. It creates versioned snapshots, loads the latest previous snapshot from Amazon S3, produces deterministic drift evidence, conditionally asks Amazon Bedrock for structured risk analysis, stores a frontend-ready report, and sends drift-only notifications through Amazon SES.

> **Status:** Autonomous Lambda pipeline and read-only AWS discovery are implemented and unit tested. Snapshot collection, S3 baseline discovery, deterministic diffing, cost-aware decisions, Bedrock analysis, report storage, and conditional SES delivery are connected. EventBridge and infrastructure-as-code provisioning remain external deployment work.

## Project Overview

DriftMind is designed to help teams understand infrastructure drift without manually reviewing raw configuration documents. Its deterministic pipeline identifies exactly what was added, removed, or modified before any generative model is invoked. Amazon Bedrock receives only that validated change report, and its response must satisfy a strict JSON contract before it can be formatted and delivered.

Collection can use the deterministic `DemoProvider` or the read-only `AWSProvider`, which discovers Lambda, S3, IAM, DynamoDB, CloudWatch alarm, EventBridge rule, SNS, and SQS configuration. Both feed the same snapshot schema and autonomous pipeline. The repository does not provision an EventBridge schedule or other infrastructure.

## Problem Statement

AWS environments evolve through deployments, automation, console actions, and service-managed operations. Although configuration data is available, answering practical questions can still require significant manual effort:

- What changed since the previous observation?
- Which resources and properties were affected?
- What operational, security, or cost implications are supported by the evidence?
- How can decision-makers receive a concise, readable report?

## Solution

DriftMind separates evidence generation from AI interpretation:

1. Create and validate a versioned infrastructure snapshot.
2. Compare it with a previous compatible snapshot.
3. Produce a deterministic report of additions, removals, and property changes.
4. Submit only that report to Amazon Bedrock with strict grounding instructions.
5. Validate the model's JSON response.
6. Format matching HTML and plain-text reports and deliver them through Amazon SES.

This boundary keeps infrastructure detection deterministic and auditable while using generative AI only to interpret explicit change evidence.

## Key Features

- See added, removed, and modified infrastructure resources at property level.
- Receive stable change identifiers that make findings easy to reference.
- Generate executive analysis grounded only in the supplied change report.
- Reject malformed or structurally invalid model responses.
- Receive readable HTML email with a plain-text fallback.
- Preserve deterministic snapshot, diff, prompt, and report formatting.
- Exercise every AWS integration locally through fully mocked unit tests.
- Keep service configuration external to source control.

## High-Level Architecture

```text
Amazon EventBridge (intended schedule; not provisioned)
        |
        v
AWS Lambda autonomous orchestrator
        |
        v
Snapshot Engine ---> Amazon S3 snapshot object
        |
        v
Previous Snapshot Loader (automatic S3 discovery)
        |
        v
Deterministic Diff Engine ---> Decision Engine
        |                            |
        | no drift                   | drift
        v                            v
Healthy Report              Amazon Bedrock Runtime
        |                            |
        |                    Validated Risk Analysis
        |                            |
        |                     Drift-only Amazon SES
        +------------+---------------+
                     v
             Amazon S3 Report
```

EventBridge remains the intended scheduler and is not provisioned by this repository. The Lambda handler implements the autonomous processing path and stores every run report under `reports/` for read-only consumers. See [architecture/architecture.md](architecture/architecture.md) for the detailed design and deployment boundaries.

## Example Workflow

```text
Scheduled Run (intended EventBridge trigger)
        |
        v
Current Snapshot Stored
        |
        v
Latest Previous Snapshot Loaded from S3
        |
        v
Deterministic Diff + Decision
        |
        +-- No drift --> Healthy Report --> S3
        |
        +-- Drift --> Bedrock Risk Analysis --> SES Alert --> S3 Report
```

The Lambda handler executes this workflow autonomously when invoked. Bedrock and SES are constructed only after deterministic drift is detected; baseline and healthy runs skip both services.

## AWS Services Used

| AWS service | Role | Current status |
| --- | --- | --- |
| Amazon S3 | Stores immutable snapshots and frontend-ready autonomous reports | Snapshot writes, paginated baseline loading, and report storage implemented; bucket provisioning is not included |
| Amazon Bedrock Runtime | Converts deterministic drift into strict risk analysis | Drift-gated Converse API wrapper and strict response validation implemented |
| Amazon SES | Sends drift-only UTF-8 multipart alerts | Invoked only after drift analysis; `send_raw_email` adapter implemented |
| AWS Lambda | Runs the autonomous watcher workflow | Complete snapshot-to-report orchestration implemented |
| Amazon EventBridge | Intended scheduled trigger | Not provisioned by this repository |
| Amazon CloudWatch | Receives Lambda logs | Required lifecycle decisions are logged; custom metrics and alarms are not implemented |

AWS integrations use the AWS SDK for Python (`boto3`) and support injected clients for testing. With `PROVIDER=aws`, read-only collectors cover:

- AWS Lambda functions
- Amazon S3 buckets in the configured Region
- AWS IAM roles
- Amazon DynamoDB tables
- Amazon CloudWatch metric and composite alarms
- Amazon EventBridge rules across visible event buses
- Amazon SNS topics
- Amazon SQS queues

Collectors paginate where supported, normalize stable fields, sort deterministically, and isolate service failures. They do not mutate observed resources. See [docs/AWS_PROVIDER_IAM.md](docs/AWS_PROVIDER_IAM.md) for the minimum discovery policy.

## Repository Structure

Key public project files, excluding Git metadata, local evidence, dependencies, and generated artifacts:

```text
driftmind/
├── backend/
│   ├── collectors/
│   ├── lambda/
│   │   ├── agent/
│   │   ├── ai/
│   │   ├── diff/
│   │   └── notification/
│   ├── providers/
│   ├── scripts/package_lambda.py
│   ├── snapshot/
│   ├── tests/
│   ├── config.py
│   ├── logger.py
│   ├── models.py
│   ├── requirements.txt
│   └── storage.py
├── frontend/
│   ├── public/sample-report.json
│   ├── src/
│   ├── .env.development
│   ├── .env.production
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── .github/workflows/tests.yml
├── architecture/
├── docs/
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
└── SECURITY.md
```

## Backend Installation

DriftMind targets **Python 3.12**. Run backend commands from the backend project directory:

```shell
git clone <repository-url>
cd driftmind/backend
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```shell
# macOS or Linux
source .venv/bin/activate
```

Install the backend requirements:

```shell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The test suite uses the Python standard library and does not require live AWS access. AWS Lambda's Python runtime includes `boto3`; invoking an AWS adapter outside Lambda requires a compatible local `boto3` installation and credentials available through the standard AWS SDK credential chain.

Build the reproducible Lambda artifact from `backend/`:

```shell
python scripts/package_lambda.py
```

The script vendors Python 3.12-compatible dependencies, writes `backend/dist/deployment.zip`, and validates `lambda.app.lambda_handler` directly from the ZIP. Infrastructure provisioning and EventBridge schedule creation are intentionally not performed by the build.

## Frontend Dashboard

The dashboard is an independent Vite project. Run frontend commands from `frontend/`:

```shell
cd ../frontend
npm install
npm run dev
npm run build
```

Development uses `.env.development` and the local `public/sample-report.json`. Production uses `.env.production`; set `VITE_REPORT_SOURCE` to the deployed Lambda Function URL or report JSON URL before building. Vite environment variables are public build-time values and must not contain credentials.

## Configuration

Configuration is read directly from process environment variables. The application does not load `.env` files automatically.

| Variable | Required by | Description | Default |
| --- | --- | --- | --- |
| `AWS_REGION` | AWS discovery, snapshot storage, Bedrock, SES | AWS Region used to initialize service clients and scope regional discovery | None |
| `SNAPSHOT_BUCKET` | Snapshot storage | Existing S3 bucket that receives snapshot JSON | None |
| `PROVIDER` | Snapshot collection | `demo` for deterministic local resources or `aws` for live read-only discovery | None |
| `BEDROCK_MODEL_ID` | Bedrock intelligence | Bedrock model or inference profile identifier | None |
| `BEDROCK_TEMPERATURE` | Bedrock intelligence | Temperature from `0.0` to `1.0` | `0.0` |
| `BEDROCK_MAX_TOKENS` | Bedrock intelligence | Positive maximum output-token count | `1024` |
| `SES_SENDER` | SES delivery | One plain sender email address configured for SES | None |
| `SES_RECIPIENT` | SES delivery | One plain recipient email address permitted by SES | None |

No model ID, bucket, account identifier, sender, or recipient is hardcoded. Set `PROVIDER=demo` for reproducible sample snapshots with no discovery calls. Set `PROVIDER=aws` to discover live resources using the Lambda execution role and standard boto3 credential chain. AWS mode calls STS once to derive `aws:<account-id>:<region>` as the snapshot environment, preventing comparisons across accounts or Regions. It needs no new environment variable beyond the existing `AWS_REGION` and `PROVIDER=aws`; grant the [minimum read-only discovery permissions](docs/AWS_PROVIDER_IAM.md).

## Running Tests

Run the complete suite from the `backend/` project directory:

```shell
python -m unittest discover -s tests -v
```

The tests mock or inject AWS discovery, STS, S3, Bedrock Runtime, and SES clients. They do not call AWS or send email.

## Implemented Components

### Infrastructure Snapshot Engine

- Schema `1.0` snapshot and resource dataclasses with strict validation
- Deterministic demo resources for an EC2 instance, security group, and S3 bucket
- Canonical JSON serialization and date-partitioned S3 object keys
- Conditional, AES256-encrypted S3 uploads
- Environment-based snapshot configuration
- Autonomous Lambda entry point that preserves the original snapshot response fields
- Backward-compatible `demo` and `aws` providers using one common resource schema
- Read-only, paginated AWS discovery for Lambda, S3, IAM, DynamoDB, CloudWatch alarms, EventBridge rules, SNS, and SQS
- Shared boto3 session, account/Region-scoped environment identity, per-service failure isolation, and deterministic ordering

`DemoProvider` snapshots are fixed and network-free, making them suitable for local development and repeatable tests. `AWSProvider` snapshots reflect normalized live configuration visible to the execution role in one account and Region; volatile runtime counters, timestamps, status fields, Lambda environment values, and raw provider responses are excluded.

### Infrastructure Diff Engine

- Strict loading of snapshots from local JSON and automatically selected S3 objects
- Paginated discovery of the latest older canonical snapshot key
- Compatibility checks for schema version, provider, and environment
- Added, removed, and recursively modified property detection
- Stable sequential identifiers such as `CHG-0001`
- Deterministic JSON reports containing numeric summaries and before/after evidence

The S3 loader ignores noncanonical keys and chooses the latest canonical snapshot strictly older than the current object. Snapshot compatibility is then enforced by the deterministic comparator.

### Amazon Bedrock Intelligence Engine

- Deterministic, versioned prompts with explicit grounding and anti-hallucination rules
- Fixed input-size bounds that reject oversized evidence without truncating it
- Environment-configured Bedrock Runtime Converse client
- Drift-only autonomous contract with `executive_summary`, `change_explanation`, `potential_impact`, `risk_level`, and `recommendations`
- Exact risk levels: `Low`, `Medium`, `High`, and `Critical`
- Strict parsing, typed models, redacted provider failures, and lifecycle logging

Bedrock is never constructed or invoked for baseline and healthy runs. Structural validation guarantees response shape and types; it does not independently prove the semantic accuracy of model conclusions.

### Notification & Reporting Engine

- Stable schema `1.0` autonomous reports for baseline, healthy, drift, and downstream-failure evidence
- Immutable report objects under `reports/YYYY/MM/DD/report-<timestamp>.json`
- Frontend-ready health, drift, risk, AI, delivery, snapshot, and activity fields
- Drift-only HTML and plain-text alerts containing deterministic changes, risk, AI explanation, impact, and recommendations
- Correct escaping of model content and deterministic UTF-8 `multipart/alternative` MIME generation
- Environment-configured SES sender and recipient with typed delivery results
- Redacted SES failures and delivery lifecycle logging

SES is never constructed or invoked for baseline and healthy runs. Retries, persisted idempotency, retry queues, and alternate notification channels are not implemented.

### Autonomous Watcher Orchestration

- Uploads the current validated snapshot and discovers the latest older canonical snapshot through paginated S3 listing
- Creates an initial baseline report when no previous snapshot exists
- Runs deterministic comparison on every subsequent invocation
- Skips Bedrock and SES for healthy runs
- Invokes strict risk analysis and sends SES only when drift exists
- Stores every completed run report as the source of truth for future read-only consumers
- Persists drift evidence before re-raising Bedrock analysis or SES delivery failures
- Emits lifecycle logs for baseline loading, comparison, change count, Bedrock, report storage, and SES

## Security Principles

- **Least privilege:** AWS roles should permit only the [documented read-only discovery actions](docs/AWS_PROVIDER_IAM.md) plus required S3, Bedrock Runtime, SES, and logging actions for selected resources.
- **Deterministic evidence first:** Snapshots and diffs are validated before generative interpretation, preserving a clear evidence boundary.
- **No credential logging:** Credentials, report bodies, model output, and recipient addresses are not written to application logs.
- **Provider error redaction:** S3, Bedrock, and SES failures expose sanitized application errors without raw provider messages in logs or public responses.
- **Environment-only configuration:** AWS Region, storage, model, sender, and recipient settings remain outside application source code.

## Future Enhancements

- Provision scheduled execution with EventBridge and infrastructure as code.
- Add bounded retries, delivery idempotency, operational metrics, and alarms.
- Define concurrency and baseline-promotion policy for overlapping or failed runs.
- Expand to multiple AWS accounts, Regions, and resource types.
- Add historical trend analysis and deployment-event correlation.
- Support additional report destinations behind explicit safety controls.

## Project Background

DriftMind was originally developed for the AWS Builder Center **Always-On Agent Weekend Challenge**. The repository is structured as an open-source foundation for further infrastructure intelligence work rather than as a challenge-specific demo.

## Contributing

Contributions are welcome. Before proposing a change, review [docs/PROJECT_SPEC.md](docs/PROJECT_SPEC.md) and [architecture/architecture.md](architecture/architecture.md), open an issue describing the intended behavior, and preserve the deterministic evidence boundary. Changes should include focused tests and must not introduce live AWS calls into the unit suite.

## License

Licensed under the [Apache License 2.0](LICENSE).