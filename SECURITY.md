# Security Policy

DriftMind is an open-source infrastructure intelligence prototype. It demonstrates validated snapshot, diff, Amazon Bedrock, reporting, and Amazon SES components; it is not production infrastructure or a complete deployed AWS workflow.

## Supported Versions

Security updates are provided for the current release line.

| Version | Supported |
| --- | --- |
| 1.0.x | Yes |
| Earlier versions | No |

## Reporting a Vulnerability

Please report suspected vulnerabilities privately through GitHub's **Report a vulnerability** security-advisory workflow for this repository. Do not open a public issue containing exploit details, credentials, account identifiers, infrastructure data, email addresses, or provider responses.

Include the affected component and version, reproduction conditions, potential impact, and any suggested mitigation. Use synthetic data wherever possible. Maintainers will review the report, acknowledge it through the private advisory, investigate its scope, and coordinate remediation and disclosure.

If the security-advisory workflow is unavailable, contact the maintainers through a private channel listed on the repository owner's GitHub profile. Do not test findings against AWS accounts or resources without explicit authorization.

## Security Principles

- **Least privilege:** Intended AWS deployments should grant only the S3, Bedrock Runtime, SES, logging, and read-only collection permissions required for configured resources.
- **Deterministic evidence:** Snapshot validation and deterministic diffing establish change evidence before any generative interpretation.
- **No credential logging:** Credentials, report bodies, model output, recipient addresses, and raw provider responses must not be written to application logs.
- **Provider error redaction:** S3, Bedrock Runtime, and SES failures expose sanitized application errors while retaining only approved operational metadata.
- **Strict validation:** Snapshot contracts, model JSON, notification content, configuration, and service responses are validated before downstream use.
- **Safe rendering:** Model-provided values are escaped before insertion into HTML email.
- **Environment-only configuration:** AWS Region, storage, model, sender, and recipient settings remain outside source code.
- **Mocked AWS tests:** Unit tests inject or mock AWS clients and must not call live AWS services or send email.

## Prototype and Deployment Scope

The repository does not provision IAM policies, S3 buckets, EventBridge schedules, complete Lambda orchestration, CloudWatch alarms, or other production controls. Deployers are responsible for identity policies, encryption choices, block-public-access settings, retention, monitoring, SES identity verification, service quotas, and regional availability.

Live AWS collection is not implemented. `AWSProvider` remains an explicit placeholder. Do not treat DriftMind output as a compliance determination, security verdict, or authorization to modify infrastructure.

## Responsible Disclosure

Allow maintainers reasonable time to investigate and prepare a fix before publishing details. Avoid accessing, modifying, retaining, or sharing data that does not belong to you. Coordinate disclosure timing through the private security advisory.
