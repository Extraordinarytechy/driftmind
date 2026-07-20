import type { ActivityStatus, AutonomousReport, NativeChange, ReportStatus, RiskLevel } from "../services/api";

export type PipelineState = ActivityStatus | "PENDING";
export interface PipelineStage { label: string; status: PipelineState }

export function flattenChanges(report: AutonomousReport): NativeChange[] {
  return [...report.added, ...report.removed, ...report.modified].sort((a, b) => a.change_id.localeCompare(b.change_id));
}

export function formatRelativeTime(value: string, now = Date.now()): string {
  const elapsed = Math.max(0, now - Date.parse(value));
  const minutes = Math.floor(elapsed / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

const DATE_TIME = new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" });
const TIME = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: "UTC", timeZoneName: "short" });
export const formatDateTime = (value: string) => DATE_TIME.format(new Date(value));
export const formatTime = (value: string) => TIME.format(new Date(value));

export function statusLabel(status: ReportStatus): string {
  return { BASELINE_CREATED: "Baseline Created", HEALTHY: "Healthy", DRIFT_DETECTED: "Drift Detected" }[status];
}

export function humanize(value: string): string {
  return value.toLowerCase().split("_").filter(Boolean).map((word) => word[0]?.toUpperCase() + word.slice(1)).join(" ");
}

export function affectedServices(changes: NativeChange[]): string[] {
  return [...new Set(changes.map((change) => humanize(change.resource_type)))].sort();
}

export function changedResourceCount(changes: NativeChange[]): number {
  return new Set(changes.map((change) => `${change.resource_type}:${change.logical_name}`)).size;
}

export function riskBadgeVariant(risk: RiskLevel | null): "default" | "warning" | "destructive" | "secondary" {
  if (risk === "Low") return "default";
  if (risk === "Medium") return "warning";
  if (risk === "High" || risk === "Critical") return "destructive";
  return "secondary";
}

function aggregateStage(report: AutonomousReport, names: string[]): PipelineState {
  const events = report.activity_timeline.filter((event) => names.includes(event.stage));
  if (events.length === 0) return "PENDING";
  if (events.some((event) => event.status === "FAILED")) return "FAILED";
  if (events.some((event) => event.status === "COMPLETED")) return "COMPLETED";
  return "SKIPPED";
}

export function pipelineStages(report: AutonomousReport): PipelineStage[] {
  return [
    { label: "Scheduler", status: "COMPLETED" },
    { label: "Snapshot", status: aggregateStage(report, ["SNAPSHOT_COLLECTED", "SNAPSHOT_STORED"]) },
    { label: "Compare", status: aggregateStage(report, ["PREVIOUS_SNAPSHOT_LOADED", "SNAPSHOT_COMPARISON"]) },
    { label: "AI Analysis", status: aggregateStage(report, ["BEDROCK_ANALYSIS"]) },
    { label: "Report", status: aggregateStage(report, ["REPORT_STORED"]) },
    { label: "Notification", status: aggregateStage(report, ["SES_NOTIFICATION"]) },
  ];
}