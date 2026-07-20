import { Check, ChevronRight, Circle, Minus, X } from "lucide-react";
import type { PipelineStage } from "../lib/report";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

const styles = {
  COMPLETED: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  FAILED: "border-red-500/40 bg-red-500/10 text-red-300",
  SKIPPED: "border-slate-600 bg-slate-800/80 text-slate-400",
  PENDING: "border-slate-600 bg-slate-800/80 text-slate-400",
};

export function PipelineFlow({ stages }: { stages: PipelineStage[] }) {
  return <Card><CardHeader><CardTitle>Last Autonomous Run</CardTitle></CardHeader><CardContent>
    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-6 xl:gap-0">{stages.map((stage, index) => {
      const Icon = stage.status === "COMPLETED" ? Check : stage.status === "FAILED" ? X : stage.status === "SKIPPED" ? Minus : Circle;
      const label = stage.label === "AI Analysis" && stage.status === "FAILED" ? "AI Analysis Failed" : stage.label;
      return <div key={stage.label} className="relative flex min-w-0 items-center xl:justify-center"><div className={`z-10 flex w-full items-center gap-2 rounded-lg border px-3 py-3 xl:w-auto xl:flex-col xl:px-4 ${styles[stage.status]}`}><span className="rounded-full bg-current/10 p-1"><Icon className="h-4 w-4" /></span><span className="text-xs font-semibold">{label}</span></div>{index < stages.length - 1 && <ChevronRight className="mx-1 hidden h-5 w-5 shrink-0 text-slate-600 xl:block" />}</div>;
    })}</div>
  </CardContent></Card>;
}