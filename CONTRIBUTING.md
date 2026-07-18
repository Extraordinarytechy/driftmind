# Contributing to DriftMind

Thank you for contributing. DriftMind is an evidence-first AWS infrastructure intelligence prototype. Contributions should preserve deterministic change detection, explicit validation boundaries, and an honest distinction between implemented components and intended deployment infrastructure.

## Project Goals

- Produce deterministic, auditable infrastructure snapshots and property-level change evidence.
- Keep generative interpretation downstream of validated evidence.
- Use narrow, replaceable interfaces for providers and AWS service clients.
- Fail safely without exposing credentials, infrastructure evidence, recipient data, or raw provider responses.
- Remain read-only with respect to observed infrastructure.

## Repository Layout

- `snapshot/`, `models.py`, `storage.py`, and `config.py`: snapshot collection, contracts, serialization, storage, and configuration.
- `providers/`: provider interface, deterministic demo provider, and the explicit future AWS provider boundary.
- `lambda/diff/`: local snapshot loading and deterministic comparison.
- `lambda/ai/`: Amazon Bedrock Runtime client, bounded request construction, response models, and strict JSON parsing.
- `lambda/notification/`: report formatting, MIME generation, and Amazon SES delivery.
- `lambda/app.py`: snapshot-focused Lambda entry point; it is not complete workflow orchestration.
- `tests/`: standard-library unit tests using injected or mocked AWS clients.
- `architecture/` and `docs/`: implementation boundaries, target architecture, service rationale, and project documentation.

## Coding Standards

Target Python 3.12 and follow established standard-library style. Use type hints, focused functions, explicit exceptions, and validated dataclasses or protocols where they clarify contracts. Preserve canonical ordering, stable identifiers, UTC handling, and deterministic serialization. Do not add hidden network calls, global mutable state, broad fallback parsing, or unredacted exception logging.

Keep provider-specific collection separate from normalized snapshot models. Keep AWS SDK calls behind narrow adapters that accept injected clients. Do not describe planned capabilities as implemented.

## Testing

Run the complete suite from the repository root:

```shell
python -m unittest discover -s tests -v
```

Add focused tests for changed behavior and failure paths. Tests must be deterministic and must not depend on wall-clock time, local AWS configuration, account state, or network availability. Inject clocks where timestamps affect output.

## AWS Service Mocking

Mock or inject Amazon S3, Amazon Bedrock Runtime, and Amazon SES clients in unit tests. **Never make live AWS calls or send real email from the unit suite.** Use synthetic account identifiers, addresses, resource names, request IDs, errors, and report content. Verify both request shape and sensitive-data redaction.

## Documentation Expectations

Update documentation when behavior, configuration, contracts, limitations, or security properties change. Clearly label intended EventBridge/Lambda deployment infrastructure, live AWS collection, S3 baseline discovery, retries, alarms, and infrastructure as code as unimplemented until verified. Do not add fabricated screenshots, metrics, costs, deployment results, or AWS service behavior.

## Pull Request Checklist

- [ ] The change is focused and preserves the deterministic evidence boundary.
- [ ] Public APIs and serialized contracts remain compatible, or the change is documented and justified.
- [ ] Relevant unit tests were added or updated and the full suite passes.
- [ ] AWS clients are mocked or injected; no unit test contacts AWS.
- [ ] Logs and errors exclude credentials, raw provider details, report bodies, model output, and recipient addresses.
- [ ] Documentation accurately distinguishes implemented behavior from future work.
- [ ] No secrets, generated snapshots, caches, or local environment files are included.
- [ ] The change follows Python 3.12 compatibility and existing module organization.
