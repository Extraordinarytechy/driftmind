import { Activity, Clock3, GitCompareArrows, Server, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { AgentActivity } from "../components/AgentActivity";
import { AISummary } from "../components/AISummary";
import { ChangeTable } from "../components/ChangeTable";
import { Header } from "../components/Header";
import { KPICard } from "../components/KPICard";
import { PipelineFlow } from "../components/PipelineFlow";
import { ReportsTable } from "../components/ReportsTable";
import { RiskAssessment } from "../components/RiskAssessment";
import { effectiveAnalysis, flattenChanges, formatDateTime, formatRelativeTime, pipelineStages, statusLabel } from "../lib/report";
import { getAutonomousReport, type AutonomousReport } from "../services/api";

export function Dashboard() {
  const [report, setReport] = useState<AutonomousReport | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    getAutonomousReport(controller.signal).then(setReport).catch((reason: unknown) => {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      setError(reason instanceof Error ? reason.message : "Unable to load DriftMind report");
    });
    return () => controller.abort();
  }, []);

  if (error) return <main className="flex min-h-screen items-center justify-center p-6"><div className="max-w-lg rounded-xl border border-red-500/30 bg-red-500/10 p-6 text-center text-red-200"><p className="font-semibold">Dashboard unavailable</p><p className="mt-2 text-sm">{error}</p></div></main>;
  if (!report) return <main className="flex min-h-screen items-center justify-center"><div className="flex items-center gap-3 text-slate-400"><Activity className="h-5 w-5 animate-pulse text-accent" />Loading DriftMind report…</div></main>;

  const changes = flattenChanges(report);
  const statusValue = report.status === "DRIFT_DETECTED" ? `${report.drift_summary.total_changes} Drift Detected` : statusLabel(report.status);
  const effective = effectiveAnalysis(report);
  const riskDetail = effective.source === "generated" ? "AI-assessed change risk" : effective.source === "last_drift" ? "From most recent detected drift" : "No AI assessment available";
  return <div className="relative min-h-screen"><Header report={report} />
    <main className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <section aria-label="Latest autonomous scan metrics" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KPICard title="Resources Scanned" value={report.resources_scanned} detail="Evaluated in the latest snapshot" icon={Server} />
        <KPICard title="Latest Scan" value={formatRelativeTime(report.run_time)} detail={formatDateTime(report.run_time)} icon={Clock3} />
        <KPICard title="Current Drift Status" value={statusValue} detail={report.summary} icon={GitCompareArrows} accent={report.changes_detected} />
        <KPICard title="Risk Level" value={effective.analysis?.risk_level ?? "Not analyzed"} detail={riskDetail} icon={ShieldAlert} accent={Boolean(effective.analysis && effective.analysis.risk_level !== "Low")} />
      </section>
      <section className="grid gap-6 lg:grid-cols-3"><div className="lg:col-span-2"><AISummary report={report} /></div><RiskAssessment report={report} changes={changes} /></section>
      <PipelineFlow stages={pipelineStages(report)} />
      <AgentActivity report={report} />
      <ChangeTable changes={changes} risk={report.risk} runTime={report.run_time} />
      <ReportsTable report={report} />
    </main>
    <footer className="border-t border-slate-800/80 px-4 py-6 text-center text-xs text-slate-500">Powered by AWS Lambda • Amazon S3 • Amazon Bedrock • Amazon EventBridge • Amazon SES</footer>
  </div>;
}