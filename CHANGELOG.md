# Changelog

All notable changes to DriftMind are documented in this file. This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-18

### Added

- Snapshot Engine with schema `1.0` validation, deterministic demo resources, canonical JSON serialization, and conditional AES256-encrypted Amazon S3 uploads.
- Diff Engine with explicit local snapshot loading, compatibility validation, property-level comparison, and stable change identifiers.
- Amazon Bedrock Intelligence Engine using the Converse API, bounded deterministic evidence, typed executive analysis, and strict response validation.
- Notification Engine with escaped HTML, matching plain-text output, deterministic UTF-8 MIME generation, and Amazon SES delivery.
- Architecture documentation describing implemented component boundaries and intended deployment infrastructure.
- AWS Builder Center documentation explaining the evidence-first design and current prototype limitations.
- Unit tests for snapshot, diff, intelligence, and notification behavior with injected or mocked AWS clients.
- Security hardening for sanitized provider failures and stable Lambda error responses.
- SVG and PNG architecture diagrams distinguishing implemented components from intended infrastructure.

### Security

- Separates deterministic snapshot and diff evidence from generative interpretation.
- Redacts S3, Bedrock Runtime, and SES provider error details from application logs and public responses.
- Escapes model-provided content before rendering HTML reports.
- Rejects malformed, duplicate, missing, extra, or incorrectly typed model-response fields through strict JSON validation.
- Reads service configuration from environment variables and does not hardcode AWS credentials, bucket names, model identifiers, or email addresses.

### Known Limitations

- `AWSProvider` is an explicit placeholder; live AWS resource collection is not implemented.
- Amazon EventBridge scheduling is intended deployment infrastructure and is not implemented or provisioned.
- Full AWS Lambda workflow orchestration is not implemented; only the snapshot-focused handler exists.
- Amazon S3 snapshot-history discovery and automatic baseline selection are not implemented.
