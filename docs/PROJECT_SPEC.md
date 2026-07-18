# DriftMind Project Specification

## Goals

- Detect meaningful changes in supported AWS infrastructure on a recurring schedule.
- Convert deterministic infrastructure differences into clear, grounded explanations.
- Assess likely operational impact and identify items that warrant human review.
- Deliver a concise executive summary without requiring an operator to initiate each run.
- Provide an auditable history of snapshots, diffs, analyses, and delivery outcomes.

## Scope

The initial product covers one configured AWS account and Region per deployment. It collects an explicitly supported set of resource metadata, normalizes and stores snapshots, compares consecutive successful snapshots, invokes Amazon Bedrock with the structured diff, and emails a report through Amazon SES. It also emits operational telemetry to Amazon CloudWatch.

## Non-Goals

- Replacing AWS Config, AWS CloudTrail, security scanners, or incident-response platforms
- Applying changes, remediating resources, or approving deployments
- Inferring intent when evidence is unavailable
- Providing real-time event processing in the initial release
- Supporting every AWS service or multi-cloud environment in the initial release
- Making compliance, legal, security, or financial determinations

## Functional Requirements

1. **FR-1 Scheduling:** A configurable EventBridge schedule starts the workflow.
2. **FR-2 Collection:** The system queries supported AWS APIs through `boto3` using read-only permissions.
3. **FR-3 Normalization:** Volatile and irrelevant fields are removed before comparison.
4. **FR-4 Snapshot storage:** Each successful snapshot is stored immutably in S3 with schema and run metadata.
5. **FR-5 Baseline selection:** The latest compatible successful snapshot is selected as the baseline.
6. **FR-6 Diffing:** Added, removed, and modified resources and attributes are identified deterministically.
7. **FR-7 First run:** A run without a baseline stores the snapshot and reports baseline creation without inventing changes.
8. **FR-8 Intelligence:** A bounded structured diff is sent to Bedrock with instructions to remain grounded in supplied evidence.
9. **FR-9 Reporting:** A human-readable executive summary includes detected changes, impact, limitations, and suggested review actions.
10. **FR-10 Delivery:** Reports are sent to configured, verified recipients through SES.
11. **FR-11 Observability:** Run status, duration, counts, failures, and delivery outcomes are observable in CloudWatch.
12. **FR-12 Traceability:** Artifacts share stable run identifiers and schema versions.

## Non-Functional Requirements

- **Runtime:** Application code will target Python 3.12 and use the AWS SDK for Python (`boto3`).
- **Security:** Use least-privilege IAM, encryption in transit and at rest, and no secrets in source control or logs.
- **Reliability:** Retries must be bounded; partial collection must not silently replace a valid baseline.
- **Idempotency:** Reprocessing a run identifier must not create inconsistent baseline state or duplicate reports.
- **Performance:** A normal run must complete within configured Lambda timeout and service quotas.
- **Maintainability:** Collectors, diffing, model interaction, and delivery must have explicit interfaces and versioned contracts.
- **Auditability:** Generated claims must be traceable to a run, diff, and stored source snapshot.
- **Cost control:** Collection scope, storage retention, model input size, and invocation frequency must be configurable.
- **Accessibility:** Email reports must be understandable without requiring access to raw JSON artifacts.

## System Components

1. **EventBridge schedule** — triggers recurring runs.
2. **Lambda orchestrator** — validates configuration and coordinates the workflow.
3. **Resource collectors** — retrieve allow-listed metadata from supported services.
4. **Normalizer and validator** — create canonical snapshots and reject incomplete candidates.
5. **S3 artifact store** — retain snapshots, diffs, and run metadata.
6. **Diff engine** — calculate deterministic changes between compatible snapshots.
7. **Bedrock intelligence adapter** — build bounded prompts, invoke the selected model, and validate responses.
8. **Report formatter** — combine deterministic evidence and model analysis into an accessible report.
9. **SES delivery adapter** — send reports and capture delivery outcomes.
10. **CloudWatch observability** — centralize structured logs, metrics, and alarms.

## Data Flow

1. EventBridge starts a run with invocation metadata.
2. Lambda validates configuration and establishes a correlation/run identifier.
3. Collectors query supported AWS APIs with pagination and bounded retries.
4. Responses are normalized, sorted, schema-validated, and marked complete or partial.
5. A complete candidate snapshot is written to S3.
6. The latest compatible complete snapshot is loaded as the baseline.
7. The diff engine generates a structured change set; on first run, it records baseline creation instead.
8. If changes exist, a bounded diff and approved context are submitted to Bedrock.
9. The validated analysis and deterministic facts are rendered into a report.
10. SES sends the report, and the run outcome is emitted to CloudWatch.
11. The complete current snapshot becomes eligible for the next run's baseline.

## Error Handling Strategy

- Validate configuration and schemas before invoking downstream services.
- Use AWS SDK retry behavior plus explicit bounded retries only for transient failures.
- Treat authorization errors, malformed responses, incompatible schemas, and incomplete collection as non-retryable until corrected.
- Never promote a partial or invalid snapshot to baseline status.
- Preserve the last known valid baseline when a run fails.
- Skip Bedrock on first-run baseline creation or when there is no change, according to final reporting policy.
- If Bedrock fails or returns invalid output, send a deterministic fallback report when safe to do so and label the analysis unavailable.
- Record SES delivery failures without reporting the run as fully successful; avoid unbounded duplicate sends.
- Emit structured, correlated, redacted diagnostics and alarms for actionable failures.

## Success Criteria

- A scheduled run completes without manual initiation in the supported deployment scope.
- Two known snapshots produce an exact, repeatable change set.
- The first run establishes a baseline without claiming nonexistent changes.
- The generated explanation contains no facts outside the provided evidence and clearly communicates uncertainty.
- A verified recipient receives an accurate, readable summary for a successful run.
- Failed or partial runs do not corrupt the valid baseline and are visible through CloudWatch.
- Stored artifacts can reconstruct what was observed, compared, analyzed, and delivered for a run.
- Documentation enables another developer to understand, deploy, operate, and extend the validated implementation.
