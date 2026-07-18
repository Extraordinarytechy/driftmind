# DriftMind

DriftMind is an autonomous, AI-powered infrastructure intelligence agent for AWS. It is being developed for the AWS Builder Center **Always-On Agent Weekend Challenge**.

> **Project status:** Phase 2 — Infrastructure Snapshot Engine implemented and covered by unit tests. No infrastructure diffing, Bedrock, SES, EventBridge deployment, or infrastructure as code is included.

## Phase 2: Infrastructure Snapshot Engine

The executable pipeline loads configuration from `SNAPSHOT_BUCKET`, `AWS_REGION`, and `PROVIDER`; loads the configured provider; generates and validates a schema `1.0` snapshot; serializes deterministic JSON; and uploads it to Amazon S3. Phase 2 implements only `DemoProvider`, which returns deterministic EC2 instance, security group, and S3 bucket models without calling AWS APIs. `AWSProvider` is an explicit future placeholder.

Snapshots contain exactly `schema_version`, `generated_at`, `provider`, `environment`, and `resources`. Objects are written with server-side AES256 encryption and a conditional create to `snapshots/YYYY/MM/DD/snapshot-<timestamp>.json`.

Run the complete unit suite, including local Lambda pipeline execution with mocked S3, from the repository root:

```shell
python -m unittest discover -s tests -v
```

The actual Lambda runtime receives `boto3` from the Python 3.12 AWS Lambda runtime. Unit tests inject an S3 client and never make AWS calls.

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
