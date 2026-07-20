import type { LucideIcon } from "lucide-react";
import { Card, CardContent } from "./ui/card";

interface KPICardProps { title: string; value: string | number; detail: string; icon: LucideIcon; accent?: boolean }
export function KPICard({ title, value, detail, icon: Icon, accent }: KPICardProps) {
  return <Card className="group overflow-hidden transition hover:-translate-y-0.5 hover:border-slate-600">
    <CardContent className="relative p-5">
      <div className="flex items-start justify-between"><span className="muted-label">{title}</span><span className="rounded-lg bg-slate-900/60 p-2"><Icon className={accent ? "h-4 w-4 text-accent" : "h-4 w-4 text-sky-400"} /></span></div>
      <p className={accent ? "mt-3 text-2xl font-bold leading-tight text-accent" : "mt-3 text-2xl font-bold leading-tight text-white"}>{value}</p>
      <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-400">{detail}</p>
    </CardContent>
  </Card>;
}