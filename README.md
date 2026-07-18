# DriftMind

DriftMind is an AI-powered infrastructure intelligence prototype for AWS. It converts versioned infrastructure snapshots into deterministic change evidence, asks Amazon Bedrock for a strictly structured executive analysis, and delivers an escaped HTML and plain-text report through Amazon SES.

> **Status:** Feature-complete prototype. Snapshot, diff, intelligence, and notification components are implemented and unit tested. Scheduled deployment infrastructure and full end-to-end Lambda orchestration are not yet implemented.

## Project Overview

DriftMind is designed to help teams understand infrastructure drift without manually reviewing raw configuration documents. Its deterministic pipeline identifies exactly what was added, removed, or modified before any generative model is invoked. Amazon Bedrock receives only that validated change report, and its response must satisfy a strict JSON contract before it can be formatted and delivered.

The current prototype includes a deterministic demo provider, S3 snapshot storage, local previous/current snapshot loading, property-level comparison, Bedrock Runtime integration, and multipart SES reporting. It does not yet collect live AWS resources, discover snapshot history in S3, or provision a scheduled AWS deployment.

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
Amazon EventBridge (intended deployment; not provisioned)
        |
        v
AWS Lambda orchestration (intended; only the snapshot handler exists)
        |
        v
Snapshot Engine ---> Amazon S3 snapshot object
        |
        v
Previous Snapshot Loader (local JSON in the current prototype)
        |
        v
Diff Engine
        |
        v
Amazon Bedrock Runtime
        |
        v
Validated Executive Analysis
        |
        v
Report Formatter
        |
        v
Amazon SES
```

EventBridge scheduling and complete Lambda orchestration represent the intended deployment architecture. The repository currently implements the individual processing and delivery components, not the scheduled infrastructure that connects them in AWS. See [architecture/architecture.md](architecture/architecture.md) for the detailed design and implementation boundaries.

## Example Workflow

```text
Scheduled Run (intended EventBridge trigger)
        |
        v
Snapshot Created
        |
        v
Previous Snapshot Loaded
        |
        v
Deterministic Diff Generated
        |
        v
Bedrock Analysis Validated
        |
        v
Executive Report Formatted
        |
        v
Amazon SES Delivery
```

In the current prototype, snapshot creation, local snapshot loading, diffing, Bedrock analysis, formatting, and SES delivery are implemented as composable components. The scheduled trigger, S3 history discovery, and single end-to-end orchestrator remain future work.

## AWS Services Used

| AWS service | Role | Current status |
| --- | --- | --- |
| Amazon S3 | Stores validated snapshot JSON objects | Storage adapter implemented; bucket provisioning is not included |
| Amazon Bedrock Runtime | Converts deterministic diffs into structured executive analysis | Converse API wrapper, prompt, and response validation implemented |
| Amazon SES | Sends UTF-8 multipart reports with HTML and plain-text alternatives | `send_raw_email` adapter implemented |
| AWS Lambda | Intended runtime for the workflow | Snapshot Lambda handler implemented; complete workflow orchestration is not |
| Amazon EventBridge | Intended scheduled trigger | Not provisioned or implemented |
| Amazon CloudWatch | Intended destination for Lambda logs and operational telemetry | Standard structured-style logging exists; custom metrics and alarms do not |

AWS integrations use the AWS SDK for Python (`boto3`) and support injected clients for testing.

## Repository Structure

Project files, excluding Git metadata and ignored Python caches:

```text
driftmind/
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
├── config.py
├── logger.py
├── models.py
├── requirements.txt
├── storage.py
├── architecture/
│   └── architecture.md
├── docs/
│   ├── AWS_SERVICES.md
│   ├── DEVELOPMENT_PLAN.md
│   └── PROJECT_SPEC.md
├── lambda/
│   ├── app.py
│   ├── ai/
│   │   ├── client.py
│   │   ├── models.py
│   │   ├── parser.py
│   │   ├── prompt.py
│   │   └── service.py
│   ├── diff/
│   │   ├── comparator.py
│   │   ├── loader.py
│   │   ├── models.py
│   │   └── report.py
│   └── notification/
│       ├── email.py
│       ├── formatter.py
│       ├── models.py
│       └── service.py
├── prompts/
│   └── .gitkeep
├── providers/
│   ├── aws_provider.py
│   ├── base.py
│   └── demo_provider.py
├── sample_data/
│   └── .gitkeep
├── screenshots/
│   └── .gitkeep
├── snapshot/
│   └── collector.py
├── snapshots/
│   └── .gitkeep
└── tests/
    ├── test_ai_engine.py
    ├── test_diff_engine.py
    ├── test_notification.py
    └── test_snapshot.py
```

## Installation

DriftMind targets **Python 3.12**.

```shell
git clone <repository-url>
cd driftmind
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

Install the repository requirements:

```shell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The test suite uses the Python standard library and does not require live AWS access. AWS Lambda's Python runtime includes `boto3`; invoking an AWS adapter outside Lambda requires a compatible local `boto3` installation and credentials available through the standard AWS SDK credential chain.

There is currently no deployment command or end-to-end CLI. Use the unit suite to run the implemented workflow components locally without contacting AWS.

## Configuration

Configuration is read directly from process environment variables. The application does not load `.env` files automatically.

| Variable | Required by | Description | Default |
| --- | --- | --- | --- |
| `AWS_REGION` | Snapshot storage, Bedrock, SES | AWS Region used to initialize service clients | None |
| `SNAPSHOT_BUCKET` | Snapshot storage | Existing S3 bucket that receives snapshot JSON | None |
| `PROVIDER` | Snapshot collection | Provider name; only `demo` is executable today | None |
| `BEDROCK_MODEL_ID` | Bedrock intelligence | Bedrock model or inference profile identifier | None |
| `BEDROCK_TEMPERATURE` | Bedrock intelligence | Temperature from `0.0` to `1.0` | `0.0` |
| `BEDROCK_MAX_TOKENS` | Bedrock intelligence | Positive maximum output-token count | `1024` |
| `SES_SENDER` | SES delivery | One plain sender email address configured for SES | None |
| `SES_RECIPIENT` | SES delivery | One plain recipient email address permitted by SES | None |

No model ID, bucket, account identifier, sender, or recipient is hardcoded. Selecting `aws` as the provider reaches the intentionally unimplemented `AWSProvider`; the deterministic `demo` provider is the only current collector.

## Running Tests

Run the complete suite from the repository root:

```shell
python -m unittest discover -s tests -v
```

The tests mock or inject S3, Bedrock Runtime, and SES clients. They do not call AWS or send email.

## Implemented Components

### Infrastructure Snapshot Engine

- Schema `1.0` snapshot and resource dataclasses with strict validation
- Deterministic demo resources for an EC2 instance, security group, and S3 bucket
- Canonical JSON serialization and date-partitioned S3 object keys
- Conditional, AES256-encrypted S3 uploads
- Environment-based snapshot configuration
- Snapshot-focused Lambda handler

Live AWS resource collection is not implemented; `AWSProvider` is an explicit placeholder.

### Infrastructure Diff Engine

- Strict loading of previous and current snapshots from local JSON files
- Compatibility checks for schema version, provider, and environment
- Added, removed, and recursively modified property detection
- Stable sequential identifiers such as `CHG-0001`
- Deterministic JSON reports containing numeric summaries and before/after evidence

S3 snapshot-history scanning and automatic baseline selection are not implemented.

### Amazon Bedrock Intelligence Engine

- Deterministic, versioned prompt with explicit grounding and anti-hallucination rules
- Fixed input-size bound that rejects oversized evidence without truncating it
- Environment-configured Bedrock Runtime Converse client
- Strict parsing of the exact executive-analysis JSON schema
- Typed executive analysis and recommendation models
- Redacted provider failures and lifecycle logging

Structural validation ensures response shape and types; it does not independently prove the semantic accuracy of model conclusions.

### Notification & Reporting Engine

- Deterministic HTML and plain-text executive reports
- Correct escaping of model content in HTML
- UTC generation timestamp and matching report sections
- Environment-configured SES sender and recipient
- Explicit UTF-8 `multipart/alternative` MIME generation
- Typed successful-delivery result containing the SES message ID
- Redacted SES failures and delivery lifecycle logging

Retries, persisted idempotency, retry queues, and alternate notification channels are not implemented.

## Security Principles

- **Least privilege:** AWS roles should permit only the required S3, Bedrock Runtime, SES, and logging actions for the selected resources.
- **Deterministic evidence first:** Snapshots and diffs are validated before generative interpretation, preserving a clear evidence boundary.
- **No credential logging:** Credentials, report bodies, model output, and recipient addresses are not written to application logs.
- **Provider error redaction:** S3, Bedrock, and SES failures expose sanitized application errors without raw provider messages in logs or public responses.
- **Environment-only configuration:** AWS Region, storage, model, sender, and recipient settings remain outside source code.

## Future Enhancements

- Implement read-only collection of live AWS resources in `AWSProvider`.
- Discover compatible previous snapshots from S3.
- Connect all components through a complete Lambda orchestrator.
- Provision scheduled execution with EventBridge and infrastructure as code.
- Add bounded retries, delivery idempotency, operational metrics, and alarms.
- Expand to multiple AWS accounts, Regions, and resource types.
- Add historical trend analysis and deployment-event correlation.
- Support additional report destinations behind explicit safety controls.

## Project Background

DriftMind was originally developed for the AWS Builder Center **Always-On Agent Weekend Challenge**. The repository is structured as an open-source foundation for further infrastructure intelligence work rather than as a challenge-specific demo.

## Contributing

Contributions are welcome. Before proposing a change, review [docs/PROJECT_SPEC.md](docs/PROJECT_SPEC.md) and [architecture/architecture.md](architecture/architecture.md), open an issue describing the intended behavior, and preserve the deterministic evidence boundary. Changes should include focused tests and must not introduce live AWS calls into the unit suite.

## License

Licensed under the [Apache License 2.0](LICENSE).
