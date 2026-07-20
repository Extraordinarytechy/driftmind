import { Bot, Check, CircleAlert, ShieldCheck } from "lucide-react";
import { formatRelativeTime, pipelineStages, statusLabel } from "../lib/report";
import type { AutonomousReport } from "../services/api";
import { Badge } from "./ui/badge";

export function Header({ report }: { report: AutonomousReport }) {
  const stages = pipelineStages(report);
  const stage = (label: string) => stages.find((item) => item.label === label)?.status;
  const outcomes = report.status === "DRIFT_DETECTED"
    ? [
        { text: "Drift detected", ok: true },
        { text: stage("AI Analysis") === "COMPLETED" ? "AI analyzed infrastructure changes" : "AI analysis unavailable", ok: stage("AI Analysis") !== "FAILED" },
        { text: stage("Report") === "COMPLETED" ? "Report generated" : "Report generation incomplete", ok: stage("Report") !== "FAILED" },
        { text: report.ses_sent ? "Notification dispatched" : stage("Notification") === "FAILED" ? "Notification failed" : "Notification not dispatched", ok: stage("Notification") !== "FAILED" },
      ]
    : [
        { text: report.status === "BASELINE_CREATED" ? "Infrastructure baseline created" : "No infrastructure drift detected", ok: true },
        { text: "Infrastructure baseline verified", ok: true },
        { text: "No action required", ok: true },
      ];

  return <header className="border-b border-slate-800/80 bg-slate-950/45 backdrop-blur">
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex gap-4"><div className="h-fit rounded-2xl bg-accent/10 p-3 ring-1 ring-accent/30"><ShieldCheck className="h-8 w-8 text-accent" /></div>
          <div><div className="flex flex-wrap items-center gap-3"><h1 className="text-3xl font-bold tracking-tight sm:text-4xl">DriftMind</h1><Badge variant={report.status === "DRIFT_DETECTED" ? "warning" : "default"}>{statusLabel(report.status)}</Badge></div>
            <p className="mt-2 text-base text-slate-300 sm:text-lg">Autonomous AI Infrastructure Drift Detection</p>
            <p className="mt-3 flex items-center gap-2 text-sm text-slate-400"><Bot className="h-4 w-4 text-sky-400" />Last autonomous scan completed {formatRelativeTime(report.run_time)}</p>
          </div>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:max-w-xl">{outcomes.map((outcome) => <div key={outcome.text} className="flex items-center gap-2 rounded-lg border border-slate-700/70 bg-slate-900/45 px-3 py-2 text-sm text-slate-200">{outcome.ok ? <Check className="h-4 w-4 shrink-0 text-emerald-400" /> : <CircleAlert className="h-4 w-4 shrink-0 text-red-400" />}<span>{outcome.text}</span></div>)}</div>
      </div>
    </div>
  </header>;
}