export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };
export type ReportStatus = "BASELINE_CREATED" | "HEALTHY" | "DRIFT_DETECTED";
export type ChangeType = "added" | "removed" | "modified";
export type ActivityStatus = "COMPLETED" | "SKIPPED" | "FAILED";
export type RiskLevel = "Low" | "Medium" | "High" | "Critical" | "UNKNOWN";

export interface NativeChange {
  change_id: string;
  change_type: ChangeType;
  resource_type: string;
  logical_name: string;
  field: string | null;
  old: JsonValue;
  new: JsonValue;
}

export interface ActivityEvent {
  stage: string;
  status: ActivityStatus;
  timestamp: string;
}

export interface DriftAnalysis {
  executive_summary: string;
  change_explanation: string;
  potential_impact: string;
  risk_level: RiskLevel;
  recommendations: string[];
}

export interface AutonomousReport {
  schema_version: string;
  run_time: string;
  status: ReportStatus;
  resources_scanned: number;
  changes_detected: boolean;
  bedrock_invoked: boolean;
  summary: string;
  drift_summary: { total_changes: number; added: number; removed: number; modified: number };
  added: NativeChange[];
  removed: NativeChange[];
  modified: NativeChange[];
  risk: RiskLevel | null;
  ai_summary: string | null;
  ai_explanation: string | null;
  potential_impact: string | null;
  recommendation: string | null;
  recommendations: string[];
  analysis: DriftAnalysis | null;
  snapshots: { current: string; previous: string | null };
  ses_sent: boolean;
  ses_message_id: string | null;
  activity_timeline: ActivityEvent[];
  analysis_source: AnalysisSource;
  last_drift_analysis: DriftAnalysis | null;
  last_drift_run_time: string | null;
}

export type AnalysisSource = "generated" | "last_drift" | "none";
const ANALYSIS_SOURCES: AnalysisSource[] = ["generated", "last_drift", "none"];

type UnknownRecord = Record<string, unknown>;
const REPORT_STATUSES: ReportStatus[] = ["BASELINE_CREATED", "HEALTHY", "DRIFT_DETECTED"];
const ACTIVITY_STATUSES: ActivityStatus[] = ["COMPLETED", "SKIPPED", "FAILED"];
const RISK_LEVELS: RiskLevel[] = ["Low", "Medium", "High", "Critical", "UNKNOWN"];

function invalid(message: string): never {
  throw new Error(`Invalid DriftMind report: ${message}`);
}

function record(value: unknown, field: string): UnknownRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) invalid(`${field} must be an object`);
  return value as UnknownRecord;
}

function text(value: unknown, field: string): string {
  if (typeof value !== "string" || value.trim() === "") invalid(`${field} must be a non-empty string`);
  return value;
}

function nullableText(value: unknown, field: string): string | null {
  return value === null ? null : text(value, field);
}

function boolean(value: unknown, field: string): boolean {
  if (typeof value !== "boolean") invalid(`${field} must be boolean`);
  return value;
}

function count(value: unknown, field: string): number {
  if (!Number.isInteger(value) || (value as number) < 0) invalid(`${field} must be a non-negative integer`);
  return value as number;
}

function timestamp(value: unknown, field: string): string {
  const result = text(value, field);
  if (!result.endsWith("Z") || Number.isNaN(Date.parse(result))) invalid(`${field} must be a UTC ISO timestamp`);
  return result;
}

function oneOf<T extends string>(value: unknown, values: readonly T[], field: string): T {
  if (typeof value !== "string" || !values.includes(value as T)) invalid(`${field} has an unsupported value`);
  return value as T;
}

function jsonValue(value: unknown, field: string): JsonValue {
  if (value === null || typeof value === "string" || typeof value === "boolean") return value;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (Array.isArray(value)) return value.map((item, index) => jsonValue(item, `${field}[${index}]`));
  const source = record(value, field);
  return Object.fromEntries(Object.entries(source).map(([key, item]) => [key, jsonValue(item, `${field}.${key}`)]));
}

function stringArray(value: unknown, field: string): string[] {
  if (!Array.isArray(value)) invalid(`${field} must be an array`);
  return value.map((item, index) => text(item, `${field}[${index}]`));
}

function change(value: unknown, expectedType: ChangeType, field: string): NativeChange {
  const source = record(value, field);
  const changeType = oneOf(source.change_type, ["added", "removed", "modified"], `${field}.change_type`);
  if (changeType !== expectedType) invalid(`${field}.change_type does not match its group`);
  const changeId = text(source.change_id, `${field}.change_id`);
  if (!/^CHG-[0-9]{4,}$/.test(changeId)) invalid(`${field}.change_id is invalid`);
  const changeField = source.field === null ? null : text(source.field, `${field}.field`);
  if (changeType === "modified" && changeField === null) invalid(`${field}.field is required for modified changes`);
  if (changeType !== "modified" && changeField !== null) invalid(`${field}.field must be null`);
  const oldValue = jsonValue(source.old, `${field}.old`);
  const newValue = jsonValue(source.new, `${field}.new`);
  if (changeType === "added" && oldValue !== null) invalid(`${field}.old must be null`);
  if (changeType === "removed" && newValue !== null) invalid(`${field}.new must be null`);
  return {
    change_id: changeId,
    change_type: changeType,
    resource_type: text(source.resource_type, `${field}.resource_type`),
    logical_name: text(source.logical_name, `${field}.logical_name`),
    field: changeField,
    old: oldValue,
    new: newValue,
  };
}

function changeGroup(value: unknown, type: ChangeType): NativeChange[] {
  if (!Array.isArray(value)) invalid(`${type} must be an array`);
  return value.map((item, index) => change(item, type, `${type}[${index}]`));
}

function analysis(value: unknown): DriftAnalysis | null {
  if (value === null) return null;
  const source = record(value, "analysis");
  return {
    executive_summary: text(source.executive_summary, "analysis.executive_summary"),
    change_explanation: text(source.change_explanation, "analysis.change_explanation"),
    potential_impact: text(source.potential_impact, "analysis.potential_impact"),
    risk_level: oneOf(source.risk_level, RISK_LEVELS, "analysis.risk_level"),
    recommendations: stringArray(source.recommendations, "analysis.recommendations"),
  };
}

function activity(value: unknown, index: number): ActivityEvent {
  const source = record(value, `activity_timeline[${index}]`);
  return {
    stage: text(source.stage, `activity_timeline[${index}].stage`),
    status: oneOf(source.status, ACTIVITY_STATUSES, `activity_timeline[${index}].status`),
    timestamp: timestamp(source.timestamp, `activity_timeline[${index}].timestamp`),
  };
}

export function parseAutonomousReport(value: unknown): AutonomousReport {
  const source = record(value, "report");
  const drift = record(source.drift_summary, "drift_summary");
  const driftSummary = {
    total_changes: count(drift.total_changes, "drift_summary.total_changes"),
    added: count(drift.added, "drift_summary.added"),
    removed: count(drift.removed, "drift_summary.removed"),
    modified: count(drift.modified, "drift_summary.modified"),
  };
  if (driftSummary.total_changes !== driftSummary.added + driftSummary.removed + driftSummary.modified) invalid("drift summary counts do not add up");

  const added = changeGroup(source.added, "added");
  const removed = changeGroup(source.removed, "removed");
  const modified = changeGroup(source.modified, "modified");
  const allChanges = [...added, ...removed, ...modified].sort((a, b) => a.change_id.localeCompare(b.change_id));
  if (allChanges.length !== driftSummary.total_changes) invalid("drift summary does not match change entries");
  allChanges.forEach((item, index) => {
    if (item.change_id !== `CHG-${String(index + 1).padStart(4, "0")}`) invalid("change IDs must be sequential");
  });

  const reportStatus = oneOf(source.status, REPORT_STATUSES, "status");
  const changesDetected = boolean(source.changes_detected, "changes_detected");
  if (changesDetected !== (driftSummary.total_changes > 0)) invalid("changes_detected does not match drift summary");
  if (reportStatus === "DRIFT_DETECTED" && !changesDetected) invalid("drift status requires changes");
  if (reportStatus !== "DRIFT_DETECTED" && changesDetected) invalid("non-drift status cannot contain changes");

  const snapshotSource = record(source.snapshots, "snapshots");
  const previousSnapshot = nullableText(snapshotSource.previous, "snapshots.previous");
  if (reportStatus === "BASELINE_CREATED" && previousSnapshot !== null) invalid("baseline report cannot have a previous snapshot");
  if (reportStatus === "HEALTHY" && previousSnapshot === null) invalid("healthy report requires a previous snapshot");

  const parsedAnalysis = analysis(source.analysis);
  const bedrockInvoked = boolean(source.bedrock_invoked, "bedrock_invoked");
  if (bedrockInvoked && !changesDetected) invalid("AI invocation requires detected drift");
  if (parsedAnalysis !== null && (!bedrockInvoked || !changesDetected)) invalid("analysis requires an invoked drift run");
  const risk = source.risk === null ? null : oneOf(source.risk, RISK_LEVELS, "risk");
  if ((parsedAnalysis?.risk_level ?? null) !== risk) invalid("risk does not match analysis");

  const sesSent = boolean(source.ses_sent, "ses_sent");
  const sesMessageId = nullableText(source.ses_message_id, "ses_message_id");
  if (sesSent && (parsedAnalysis === null || sesMessageId === null)) invalid("successful notification requires analysis and message ID");
  if (!sesSent && sesMessageId !== null) invalid("message ID requires a successful notification");
  if (!Array.isArray(source.activity_timeline)) invalid("activity_timeline must be an array");

  return {
    schema_version: text(source.schema_version, "schema_version"),
    run_time: timestamp(source.run_time, "run_time"),
    status: reportStatus,
    resources_scanned: count(source.resources_scanned, "resources_scanned"),
    changes_detected: changesDetected,
    bedrock_invoked: bedrockInvoked,
    summary: text(source.summary, "summary"),
    drift_summary: driftSummary,
    added,
    removed,
    modified,
    risk,
    ai_summary: nullableText(source.ai_summary, "ai_summary"),
    ai_explanation: nullableText(source.ai_explanation, "ai_explanation"),
    potential_impact: nullableText(source.potential_impact, "potential_impact"),
    recommendation: nullableText(source.recommendation, "recommendation"),
    recommendations: stringArray(source.recommendations, "recommendations"),
    analysis: parsedAnalysis,
    snapshots: { current: text(snapshotSource.current, "snapshots.current"), previous: previousSnapshot },
    ses_sent: sesSent,
    ses_message_id: sesMessageId,
    activity_timeline: source.activity_timeline.map(activity),
    analysis_source:
      typeof source.analysis_source === "string" && ANALYSIS_SOURCES.includes(source.analysis_source as AnalysisSource)
        ? (source.analysis_source as AnalysisSource)
        : "none",
    last_drift_analysis: optionalAnalysis(source.last_drift_analysis),
    last_drift_run_time: optionalTimestamp(source.last_drift_run_time),
  };
}

/**
 * Parse the optional reused-analysis block defensively. It is display-only
 * metadata, so a malformed value must degrade to null (showing the normal
 * "AI analysis unavailable" state) rather than failing the whole report parse.
 * The primary `analysis` field keeps its strict validation.
 */
function optionalAnalysis(value: unknown): DriftAnalysis | null {
  if (value == null) return null;
  try {
    return analysis(value);
  } catch {
    return null;
  }
}

function optionalTimestamp(value: unknown): string | null {
  if (value == null) return null;
  try {
    return timestamp(value, "last_drift_run_time");
  } catch {
    return null;
  }
}

function reportSource(): string {
  const mode = import.meta.env.VITE_DATA_MODE;
  const source = import.meta.env.VITE_REPORT_SOURCE?.trim();
  if (mode !== "demo" && mode !== "live") {
    throw new Error("VITE_DATA_MODE must be either demo or live");
  }
  if (!source) {
    throw new Error(`VITE_REPORT_SOURCE is required when VITE_DATA_MODE=${mode}`);
  }
  return source;
}

export async function getAutonomousReport(signal?: AbortSignal): Promise<AutonomousReport> {
  const response = await fetch(reportSource(), { headers: { Accept: "application/json" }, signal });
  if (!response.ok) throw new Error(`Unable to load DriftMind report (${response.status})`);
  return parseAutonomousReport(await response.json());
}