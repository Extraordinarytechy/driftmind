# AWS Services

DriftMind uses managed AWS services to minimize operational overhead while preserving clear boundaries between scheduling, execution, storage, intelligence, delivery, and observability. Exact permissions, quotas, and costs will be validated during implementation.

## Amazon EventBridge

**Why it is used:** EventBridge provides the always-on schedule that starts DriftMind without a continuously running host. A schedule expression can be changed independently of application code, and failed invocation policies can be monitored.

**Planned responsibility:**
- Invoke the workflow on a configured recurring schedule
- Pass a small invocation context, not infrastructure data
- Apply retry and dead-letter behavior appropriate to the final design

## AWS Lambda

**Why it is used:** Lambda fits a periodic, bounded Python workload and removes server management. Its native integrations with EventBridge, S3, Bedrock, SES, IAM, and CloudWatch make it suitable for the initial single-workflow architecture.

**Planned responsibility:**
- Coordinate collection, baseline lookup, diffing, Bedrock analysis, and reporting
- Use Python 3.12 and `boto3`
- Emit structured logs and custom metrics

The implementation will set explicit memory, timeout, concurrency, and ephemeral-storage limits. If runtime or payload constraints are exceeded, orchestration may later be decomposed rather than hidden inside retries.

## Amazon S3

**Why it is used:** S3 provides durable, low-maintenance object storage for immutable snapshots and related run artifacts. Object keys and metadata can support account, Region, date, run, and schema-version partitioning.

**Planned responsibility:**
- Store normalized snapshots and deterministic diffs
- Retain artifact metadata needed for traceability
- Support encryption, versioning, lifecycle management, and retention controls

S3 is the source of truth for baseline selection. A partial or invalid collection must not be promoted as the latest valid baseline.

## Amazon Bedrock

**Why it is used:** Bedrock provides managed access to foundation models while keeping the generative layer within the AWS architecture. It turns structured change evidence into an accessible explanation and operational-impact assessment.

**Planned responsibility:**
- Analyze only the bounded diff and approved context supplied by DriftMind
- Produce output conforming to a validated response contract
- State uncertainty and avoid unsupported claims

Model choice, Region availability, token limits, guardrails, and invocation cost will be explicit configuration decisions. Bedrock does not detect changes; it interprets the deterministic diff.

## Amazon Simple Email Service (SES)

**Why it is used:** SES provides managed, programmatic email delivery and fits the requirement to send an executive summary without operating a mail server.

**Planned responsibility:**
- Send plain-text and HTML reports from a verified identity
- Deliver only to configured recipients
- Return message identifiers and errors for correlated run telemetry

The design will account for SES sandbox restrictions, identity and recipient verification, Region selection, quotas, suppression handling, and safe HTML escaping. SES is a delivery channel, not the source of record for run artifacts.

## Amazon CloudWatch

**Why it is used:** CloudWatch is the native observability layer for Lambda and the surrounding AWS integrations. It makes unattended runs supportable through correlated logs, metrics, dashboards, and alarms.

**Planned responsibility:**
- Store structured, redacted logs keyed by run identifier
- Track success, failure, duration, resource count, change count, model status, and email status
- Alarm on consecutive failures, missing scheduled runs, throttling, and delivery errors

Log retention and metric dimensions will be deliberately bounded to control cost and avoid high-cardinality or sensitive data.

## Service Interaction Summary

1. EventBridge invokes Lambda on schedule.
2. Lambda queries supported AWS APIs and stores normalized artifacts in S3.
3. Lambda computes a deterministic diff locally.
4. Lambda sends only the approved bounded diff to Bedrock.
5. Lambda formats the result and sends it through SES.
6. CloudWatch observes each stage and raises alarms for actionable failures.

## Cross-Cutting AWS Controls

Although not standalone workflow stages, IAM and AWS encryption capabilities are fundamental. Roles will grant only required actions and resource scope; S3 objects and service traffic will use encryption appropriate to the final deployment. Configuration and recipient data will remain external to source control. No service is authorized to mutate observed infrastructure as part of the initial product.
