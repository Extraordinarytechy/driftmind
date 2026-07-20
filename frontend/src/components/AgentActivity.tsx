import { Bot, Check, Minus, X } from "lucide-react";
import { formatTime, humanize } from "../lib/report";
import type { ActivityEvent, ActivityStatus, AutonomousReport } from "../services/api";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

interface TimelineItem { label: string; status: ActivityStatus; timestamp: string }
const completedLabels: Record<string, string> = {
  SNAPSHOT_COLLECTED: "Infrastructure snapshot created",
  SNAPSHOT_STORED: "Infrastructure snapshot stored",
  PREVIOUS_SNAPSHOT_LOADED: "Previous baseline loaded",
  SNAPSHOT_COMPARISON: "Compared with previous baseline",
  BEDROCK_ANALYSIS: "AI analysis completed",
  REPORT_STORED: "Report stored",
  SES_NOTIFICATION: "Notification sent",
};

function eventLabel(event: ActivityEvent): string {
  if (event.status === "COMPLETED") return completedLabels[event.stage] ?? `${humanize(event.stage)} completed`;
  if (event.stage === "BEDROCK_ANALYSIS") return event.status === "FAILED" ? "AI analysis failed" : "AI analysis not required";
  if (event.stage === "SES_NOTIFICATION") return event.status === "FAILED" ? "Notification failed" : "Notification not required";
  if (event.stage === "PREVIOUS_SNAPSHOT_LOADED" && event.status === "SKIPPED") return "No previous baseline available";
  return `${humanize(event.stage)} ${event.status.toLowerCase()}`;
}

export function AgentActivity({ report }: { report: AutonomousReport }) {
  const items: TimelineItem[] = [{ label: "Scheduled scan started", status: "COMPLETED", timestamp: report.run_time }];
  report.activity_timeline.forEach((event) => {
    items.push({ label: eventLabel(event), status: event.status, timestamp: event.timestamp });
    if (event.stage === "SNAPSHOT_COMPARISON" && event.status === "COMPLETED") items.push({ label: report.status === "DRIFT_DETECTED" ? "Drift detected" : report.status === "HEALTHY" ? "Infrastructure baseline verified" : "Initial baseline created", status: "COMPLETED", timestamp: event.timestamp });
  });
  return <Card><CardHeader><CardTitle className="flex items-center gap-2"><Bot className="h-5 w-5 text-accent" />Agent Activity</CardTitle></CardHeader><CardContent><ol className="grid gap-0 sm:grid-cols-2 xl:grid-cols-3">{items.map((item, index) => {
    const Icon = item.status === "COMPLETED" ? Check : item.status === "FAILED" ? X : Minus;
    const color = item.status === "COMPLETED" ? "text-emerald-400" : item.status === "FAILED" ? "text-red-400" : "text-slate-500";
    return <li key={`${item.label}-${index}`} className="relative flex gap-3 border-l border-slate-700 pb-5 pl-5 last:pb-0 sm:last:pb-5"><span className={`absolute -left-2.5 top-0 rounded-full bg-slate-900 p-1 ${color}`}><Icon className="h-3 w-3" /></span><div><time className="text-xs font-medium text-slate-500" dateTime={item.timestamp}>{formatTime(item.timestamp)}</time><p className="mt-1 text-sm text-slate-200">{item.label}</p></div></li>;
  })}</ol></CardContent></Card>;
}