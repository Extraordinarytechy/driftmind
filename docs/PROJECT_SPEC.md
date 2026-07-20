# DriftMind Project Specification

## Purpose and Status
DriftMind detects infrastructure drift with deterministic code and uses generative AI only to interpret validated change evidence. The autonomous Python 3.12 Lambda pipeline and read-only `AWSProvider` are implemented and unit tested with mocked AWS clients. EventBridge and infrastructure-as-code provisioning remain external; collection can use deterministic demo resources or live AWS discovery across eight services.

## Goals
- Produce immutable, schema-validated snapshots and deterministic added/removed/modified evidence.
- Avoid Bedrock and SES cost when no drift exists.
- Convert drift into strict risk analysis and a concise, evidence-linked alert.
- Store a stable per-run report for future read-only dashboards.
- Keep observed infrastructure read-only and application logs free of credentials, report bodies, model output, and recipient addresses.

## Non-Goals
DriftMind does not replace AWS Config, CloudTrail, security scanners, or incident response; remediate or approve changes; infer intent without evidence; provide real-time event processing; add authentication or administration; or make compliance, legal, security, or financial determinations.

## Implemented Functional Requirements
1. **Snapshot storage:** Store each validated current snapshot immutably under its canonical `snapshots/` key.
2. **Baseline discovery:** Paginate S3 and select the latest canonical snapshot key strictly older than the current key; validate its payload and let the comparator enforce compatibility.
3. **Diffing:** Deterministically identify added, removed, and property-level modified resources with stable IDs.
4. **First run:** Store a `BASELINE_CREATED` report without fabricated changes, Bedrock, or SES.
5. **Healthy run:** Store a `HEALTHY` report and skip Bedrock and SES when the diff is empty.
6. **Intelligence:** For drift only, send a bounded structured diff to Bedrock and require strict summary, explanation, impact, risk, and recommendation fields.
7. **Reporting:** Store schema `1.0` reports under `reports/` with health, resources scanned, grouped evidence, risk/AI fields, snapshot keys, delivery state, and an activity timeline.
8. **Delivery:** Send escaped UTF-8 multipart SES alerts only after drift receives valid analysis.
9. **Failure evidence:** Persist available drift evidence on Bedrock or SES failure before returning a sanitized Lambda error.
10. **Compatibility:** Preserve existing snapshot serialization, key behavior, deterministic diff contracts, reusable analysis/notification APIs, and Lambda success fields.
11. **Live discovery:** With `PROVIDER=aws`, use read-only, paginated service collectors for Lambda, S3, IAM, DynamoDB, CloudWatch alarms, EventBridge rules, SNS, and SQS; isolate failures and normalize resources into the unchanged snapshot schema.

## Target Requirements Not Yet Delivered
- A configurable EventBridge schedule and infrastructure-as-code deployment.
- Completeness markers and explicit resource caps for large or partially visible AWS inventories.
- Explicit bounded retries, persistent idempotency, overlapping-run control, and successful-baseline promotion state.
- CloudWatch custom metrics, dashboards, alarms, correlation IDs, and per-stage durations.
- Configurable retention, multi-account/Region collection, and additional resource types.

## Implemented Data Flow
1. Lambda collects and validates the current snapshot, then conditionally stores it in S3.
2. S3 history discovery loads the latest older canonical snapshot or reports that no baseline exists.
3. The comparator always runs when a previous snapshot exists; the decision engine selects baseline, healthy, or drift state.
4. Baseline and healthy states store a report and finish without Bedrock or SES.
5. Drift invokes Bedrock, validates `Low|Medium|High|Critical` risk analysis, sends one SES alert, and stores the final report.
6. Bedrock or SES failure stores the best available drift report and re-raises to the sanitized Lambda boundary.

## Contracts and Quality Attributes
Snapshots, changes, analyses, notifications, and reports are validated typed values. Serialization and change ordering are deterministic. S3 writes use AES256 and `If-None-Match: *`. Model input is bounded; malformed model output fails closed. Reports are the source of truth for read-only consumers and never trigger execution. Unit tests inject S3, Bedrock Runtime, and SES clients and make no live AWS calls.

## Acceptance Criteria
The existing snapshot pipeline remains compatible; baseline discovery and deterministic comparison work; baseline/healthy reports skip Bedrock and SES; drift reports include validated risk and recommendations; reports persist to S3; SES is drift-only; all tests pass; and the deployment ZIP imports `lambda.app.lambda_handler` with all autonomous modules included.
