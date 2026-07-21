import { Gauge, Network, ShieldAlert, Sparkles } from "lucide-react";
import { affectedServices, changedResourceCount, effectiveAnalysis, riskBadgeVariant } from "../lib/report";
import type { AutonomousReport, NativeChange } from "../services/api";
import { Badge } from "./ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

function Metric({ icon: Icon, label, value }: { icon: typeof Gauge; label: string; value: string }) {
  return <div className="rounded-xl bg-slate-900/40 p-4"><div className="flex items-center gap-2 text-slate-500"><Icon className="h-4 w-4" /><span className="muted-label">{label}</span></div><p className="mt-2 text-sm font-semibold leading-6 text-slate-200">{value}</p></div>;
}

export function RiskAssessment({ report, changes }: { report: AutonomousReport; changes: NativeChange[] }) {
  const services = affectedServices(changes);
  const resourceCount = changedResourceCount(changes);
  const { analysis, source } = effectiveAnalysis(report);
  const risk = analysis?.risk_level ?? "UNKNOWN";
  const riskValue = analysis ? (source === "last_drift" ? `${analysis.risk_level} (last drift)` : analysis.risk_level) : "Not analyzed";
  const blastRadius = `${resourceCount} resource${resourceCount === 1 ? "" : "s"} / ${services.length} resource type${services.length === 1 ? "" : "s"}`;
  return <Card className="h-full"><CardHeader className="flex-row items-center justify-between space-y-0"><CardTitle className="flex items-center gap-2"><ShieldAlert className="h-5 w-5 text-accent" />AI Risk Assessment</CardTitle><Badge variant={riskBadgeVariant(risk)}>{risk}</Badge></CardHeader><CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
    <Metric icon={ShieldAlert} label="Risk Level" value={riskValue} />
    <Metric icon={Network} label="Affected Services" value={services.join(", ") || "None"} />
    <Metric icon={Gauge} label="Estimated Blast Radius" value={blastRadius} />
    <Metric icon={Sparkles} label="AI Confidence" value="Not provided" />
  </CardContent></Card>;
}