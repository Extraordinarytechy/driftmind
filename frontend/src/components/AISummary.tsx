import { Bot, History, Lightbulb, ShieldAlert, Sparkles } from "lucide-react";
import { effectiveAnalysis, formatDateTime, riskBadgeVariant } from "../lib/report";
import type { AutonomousReport } from "../services/api";
import { Badge } from "./ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

export function AISummary({ report }: { report: AutonomousReport }) {
  const { analysis, source, runTime } = effectiveAnalysis(report);
  if (!analysis) return <Card className="h-full border-slate-600/80"><CardHeader><CardTitle className="flex items-center gap-2 text-lg"><Bot className="h-5 w-5 text-accent" />AI Analysis</CardTitle></CardHeader><CardContent><div className="flex min-h-56 items-center justify-center rounded-xl border border-dashed border-slate-600 bg-slate-900/30 text-sm text-slate-400">AI analysis unavailable.</div></CardContent></Card>;
  const reused = source === "last_drift";
  const eyebrow = reused ? "Last AI drift analysis" : "Primary agent conclusion";
  const recommendation = analysis.recommendations.join(" ") || "Manual review recommended.";
  return <Card className="h-full overflow-hidden border-accent/30 bg-gradient-to-br from-card via-card to-orange-950/20">
    <CardHeader className="flex-row items-center justify-between space-y-0 border-b border-slate-700/60"><div><p className="muted-label text-accent">{eyebrow}</p><CardTitle className="mt-1 flex items-center gap-2 text-xl"><Sparkles className="h-5 w-5 text-accent" />AI Analysis</CardTitle></div><Badge variant={riskBadgeVariant(analysis.risk_level)}><ShieldAlert className="mr-1 h-3.5 w-3.5" />{analysis.risk_level} risk</Badge></CardHeader>
    <CardContent className="grid gap-5 pt-5 sm:grid-cols-2">
      {reused && <div className="sm:col-span-2 flex items-center gap-2 rounded-lg border border-slate-700/70 bg-slate-900/45 px-3 py-2 text-xs text-slate-400"><History className="h-3.5 w-3.5 shrink-0 text-sky-400" />Latest scan detected no drift. Showing analysis from the most recent detected drift{runTime ? ` (${formatDateTime(runTime)})` : ""}.</div>}
      <section className="sm:col-span-2"><p className="muted-label">Summary</p><p className="mt-2 text-base leading-7 text-slate-200">{analysis.executive_summary}</p>{analysis.change_explanation && <p className="mt-3 text-sm leading-6 text-slate-400">{analysis.change_explanation}</p>}</section>
      <section className="rounded-xl bg-slate-900/45 p-4"><p className="muted-label">Risk</p><p className="mt-2 text-lg font-semibold text-white">{analysis.risk_level}</p></section>
      <section className="rounded-xl bg-slate-900/45 p-4"><p className="muted-label">Impact</p><p className="mt-2 text-sm leading-6 text-slate-300">{analysis.potential_impact}</p></section>
      <section className="rounded-xl border border-accent/25 bg-accent/5 p-4 sm:col-span-2"><p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-accent"><Lightbulb className="h-4 w-4" />Recommendation</p><p className="mt-2 text-sm leading-6 text-slate-200">{recommendation}</p></section>
    </CardContent>
  </Card>;
}