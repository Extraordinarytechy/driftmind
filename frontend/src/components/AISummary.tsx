import { Bot, Lightbulb, ShieldAlert, Sparkles } from "lucide-react";
import { riskBadgeVariant } from "../lib/report";
import type { AutonomousReport } from "../services/api";
import { Badge } from "./ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

export function AISummary({ report }: { report: AutonomousReport }) {
  if (!report.analysis || !report.ai_summary) return <Card className="h-full border-slate-600/80"><CardHeader><CardTitle className="flex items-center gap-2 text-lg"><Bot className="h-5 w-5 text-accent" />AI Analysis</CardTitle></CardHeader><CardContent><div className="flex min-h-56 items-center justify-center rounded-xl border border-dashed border-slate-600 bg-slate-900/30 text-sm text-slate-400">AI analysis unavailable.</div></CardContent></Card>;
  return <Card className="h-full overflow-hidden border-accent/30 bg-gradient-to-br from-card via-card to-orange-950/20">
    <CardHeader className="flex-row items-center justify-between space-y-0 border-b border-slate-700/60"><div><p className="muted-label text-accent">Primary agent conclusion</p><CardTitle className="mt-1 flex items-center gap-2 text-xl"><Sparkles className="h-5 w-5 text-accent" />AI Analysis</CardTitle></div><Badge variant={riskBadgeVariant(report.analysis.risk_level)}><ShieldAlert className="mr-1 h-3.5 w-3.5" />{report.analysis.risk_level} risk</Badge></CardHeader>
    <CardContent className="grid gap-5 pt-5 sm:grid-cols-2">
      <section className="sm:col-span-2"><p className="muted-label">Summary</p><p className="mt-2 text-base leading-7 text-slate-200">{report.ai_summary}</p>{report.ai_explanation && <p className="mt-3 text-sm leading-6 text-slate-400">{report.ai_explanation}</p>}</section>
      <section className="rounded-xl bg-slate-900/45 p-4"><p className="muted-label">Risk</p><p className="mt-2 text-lg font-semibold text-white">{report.risk ?? "UNKNOWN"}</p></section>
      <section className="rounded-xl bg-slate-900/45 p-4"><p className="muted-label">Impact</p><p className="mt-2 text-sm leading-6 text-slate-300">{report.potential_impact ?? "Impact not provided."}</p></section>
      <section className="rounded-xl border border-accent/25 bg-accent/5 p-4 sm:col-span-2"><p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-accent"><Lightbulb className="h-4 w-4" />Recommendation</p><p className="mt-2 text-sm leading-6 text-slate-200">{report.recommendation ?? "Manual review recommended."}</p></section>
    </CardContent>
  </Card>;
}