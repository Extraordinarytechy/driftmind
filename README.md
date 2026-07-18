# DriftMind

DriftMind is an autonomous, AI-powered infrastructure intelligence agent for AWS. It is being developed for the AWS Builder Center **Always-On Agent Weekend Challenge**.

> **Project status:** Phase 5 — snapshot collection, deterministic infrastructure diffing, Bedrock intelligence, and SES notification reporting are implemented and covered by unit tests. EventBridge scheduling, retry queues, CloudWatch alarms, infrastructure as code, and alternate notification channels are not included.

## Phase 2: Infrastructure Snapshot Engine

The executable snapshot pipeline loads configuration from `SNAPSHOT_BUCKET`, `AWS_REGION`, and `PROVIDER`; loads the configured provider; generates and validates a schema `1.0` snapshot; serializes deterministic JSON; and uploads it to Amazon S3. Phase 2 implements only `DemoProvider`, which returns deterministic EC2 instance, security group, and S3 bucket models without calling AWS APIs. `AWSProvider` remains the explicit future provider placeholder.

Snapshots contain exactly `schema_version`, `generated_at`, `provider`, `environment`, and `resources`. Objects are written with server-side AES256 encryption and a conditional create to `snapshots/YYYY/MM/DD/snapshot-<timestamp>.json`.

## Phase 3: Infrastructure Diff Engine

The diff engine strictly loads previous and current schema `1.0` snapshots from local UTF-8 JSON files, validates them through the Phase 2 models, and requires matching schema version, provider, and environment. It detects added and removed resources by `(resource_type, logical_name)` identity and recursively detects modified properties. Unchanged resources and properties are omitted.

Reports contain exactly `summary` and `changes`. Each change contains `change_id`, `change_type`, `resource_type`, `logical_name`, `field`, `old`, and `new`. IDs such as `CHG-0001` are assigned after deterministic ordering. Added and removed resources use `field: null`; modified fields use dotted property paths such as `tags.Environment`. The report contains no generated prose.

## Phase 4: Amazon Bedrock Intelligence Engine

The intelligence service accepts a validated Phase 3 report, builds a deterministic prompt, invokes Amazon Bedrock through the Runtime Converse API, strictly parses the returned JSON, and returns a typed `ExecutiveAnalysis`. The prompt identifies DriftMind and the analyst role, embeds only the supplied report, rejects reports larger than 100,000 UTF-8 bytes, prohibits invented infrastructure and speculation, and requires conclusions and review actions to remain grounded in change IDs.

Bedrock configuration comes only from environment variables:

- Required: `AWS_REGION`, `BEDROCK_MODEL_ID`
- Optional: `BEDROCK_TEMPERATURE` (default `0.0`), `BEDROCK_MAX_TOKENS` (default `1024`)

No model ID is hardcoded. The response must be one JSON object containing exactly `summary`, `security_impact`, `operational_impact`, `cost_impact`, and `recommendations`. Markdown, surrounding prose, missing or extra fields, duplicate fields, invalid types, and malformed JSON are rejected. API failures are wrapped without returning or logging provider exception details.

## Phase 5: Notification & Reporting Engine

`NotificationService` converts a validated `ExecutiveAnalysis` into matching HTML and plain-text reports using an injectable UTC generation timestamp. Reports include the title, timestamp, executive summary, security, operational and cost impacts, recommendations, and footer. HTML model content is escaped, and no external CSS or JavaScript is used.

SES configuration comes only from required environment variables:

- `AWS_REGION`
- `SES_SENDER`
- `SES_RECIPIENT`

The SES adapter validates plain email addresses, creates an explicit UTF-8 `multipart/alternative` message, and sends it through `send_raw_email`. Successful delivery returns a typed result containing the SES message ID and `sent` status. Provider failures are sanitized, and recipient addresses, report bodies, credentials, and raw provider errors are not logged.

Run the complete unit suite from the repository root:

```shell
python -m unittest discover -s tests -v
```

Bedrock and S3 are fully mocked or injected in tests; the suite makes no AWS calls.

## Project Overview

DriftMind runs on a schedule, captures a normalized snapshot of selected AWS infrastructure, compares it with the previous snapshot, and uses Amazon Bedrock to explain meaningful changes and their likely operational impact. It then sends a concise executive summary by email.

## Problem Statement

Cloud environments change continuously through deployments, automation, console actions, and service-managed operations. Raw audit events and configuration data are valuable, but they can be difficult to turn into a timely answer to three practical questions: **What changed? Why does it matter? What should be reviewed next?**

## Solution

DriftMind creates a recurring infrastructure intelligence loop:

1. Collect the current infrastructure state.
2. Load the most recent prior state.
3. Compute a deterministic change set.
4. Ask Amazon Bedrock to explain and assess the changes.
5. Email an executive summary and retain the new snapshot for the next run.

Deterministic collection and comparison remain separate from generative analysis so that results are auditable and AI output is grounded in explicit evidence.

## Features

- Scheduled, unattended infrastructure reviews
- Normalized and versioned AWS resource snapshots
- Deterministic detection of additions, removals, and modifications
- Bedrock-generated explanations grounded in the computed diff
- Operational impact and review guidance
- Executive email summaries through Amazon SES
- CloudWatch logs, metrics, and alarms for operational visibility
- Privacy-aware reporting with least-privilege access as a design goal

## High-Level Architecture

Amazon EventBridge invokes an AWS Lambda workflow on a configured schedule. Lambda queries supported AWS APIs with `boto3`, writes snapshots to Amazon S3, and compares the current snapshot with the previous successful snapshot. The resulting structured diff is supplied to Amazon Bedrock for analysis. Lambda formats the grounded response and sends it through Amazon SES. Amazon CloudWatch captures logs, metrics, and alarms across the workflow.

Detailed design decisions are documented in [architecture/architecture.md](architecture/architecture.md).

## AWS Services

| Service | Purpose |
| --- | --- |
| Amazon EventBridge | Starts each scheduled analysis run |
| AWS Lambda | Coordinates collection, comparison, analysis, and reporting |
| Amazon S3 | Stores durable, versionable infrastructure snapshots and run artifacts |
| Amazon Bedrock | Explains detected changes and evaluates operational impact |
| Amazon SES | Delivers the executive email summary |
| Amazon CloudWatch | Provides logs, metrics, dashboards, and alarms |

## Repository Structure

```text
driftmind/
├── README.md
├── LICENSE
├── .gitignore
├── requirements.txt
├── architecture/
│   └── architecture.md
├── docs/
│   ├── PROJECT_SPEC.md
│   ├── DEVELOPMENT_PLAN.md
│   └── AWS_SERVICES.md
├── article/
│   └── builder-center.md
├── lambda/
├── prompts/
├── sample_data/
├── screenshots/
├── snapshots/
└── tests/
```

Empty working directories contain `.gitkeep` files so Git can retain the project structure.

## Planned Implementation Phases

1. **Repository:** Establish scope, architecture, documentation, licensing, and project structure.
2. **Infrastructure Snapshot Engine:** Collect and normalize selected AWS resource metadata and persist versioned snapshots.
3. **Diff Engine:** Compare compatible snapshots and produce a deterministic structured change set.
4. **Bedrock Intelligence:** Generate grounded explanations and operational-impact assessments from the diff.
5. **Email Reporting:** Format and deliver reports through SES with observable failure handling.
6. **Documentation:** Finalize deployment, operations, security, testing, and Builder Center materials using verified results.

See [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) for phase inputs, outputs, and deliverables.

## Development Principles

- Python 3.12 for application code
- AWS SDK for Python (`boto3`) for AWS integrations
- Least-privilege IAM and explicit data boundaries
- Deterministic snapshots and diffs before generative interpretation
- Versioned schemas, prompts, and artifacts
- Structured observability without logging secrets or unnecessary infrastructure data

## Future Enhancements

- Multi-account and multi-Region collection through AWS Organizations
- Broader AWS resource coverage and configurable collector plug-ins
- Trend analysis across more than two snapshots
- Change correlation with approved deployment and audit metadata
- Additional notification channels and report formats
- Interactive investigation with citations to stored evidence
- Human-approved remediation workflows with strict safety controls

## Contributing

Contribution guidance and issue templates will be added with the first implementation phase. Until then, use the project specification and architecture documents as the source of truth for proposed changes.

## License

Licensed under the [Apache License 2.0](LICENSE).
