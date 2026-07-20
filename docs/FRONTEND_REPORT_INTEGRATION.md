# Frontend Report Integration

## Existing report flow

`backend/lambda/agent/service.py` builds a validated `AutonomousReport` after snapshot collection, comparison, and the conditional Bedrock and SES stages. Baseline, healthy, drift-success, Bedrock-failure, and SES-failure paths all persist a final report.

`backend/lambda/agent/storage.py` serializes the report as deterministic UTF-8 JSON and stores its immutable historical copy at:

```text
reports/YYYY/MM/DD/report-YYYYMMDDTHHMMSSffffffZ.json
```

The report uses schema `1.0` from `backend/lambda/agent/models.py`. It contains run status, resources scanned, drift counts and grouped changes, AI analysis, snapshot keys, notification state, and the activity timeline.

Before frontend integration there was no report index, manifest, stable latest key, download URL, presigned URL, or HTTP read endpoint. Discovering the newest object required private S3 list access and pagination. The existing Lambda handler always starts a scan and must never be called by the dashboard.

## Integration approach

Each successful historical report write now also refreshes:

```text
reports/latest.json
```

This object contains the same report JSON, not a second schema. The historical write remains conditional and authoritative; all dated reports remain accessible. The latest write is an overwrite with `Cache-Control: no-cache, max-age=0`. A latest-write failure is logged but does not turn an otherwise completed autonomous run into a failure.

The frontend should set `VITE_REPORT_SOURCE` to a read-only HTTPS URL that serves only `reports/latest.json`, for example an S3 object URL or CloudFront path configured with GET-only access and CORS for the dashboard origin. Do not expose the snapshot bucket broadly, grant the browser list access, or point the frontend at the drift Lambda.

No EventBridge, snapshot, diff, collector, provider, Bedrock, SES, report schema, or scheduling behavior changes are required.
