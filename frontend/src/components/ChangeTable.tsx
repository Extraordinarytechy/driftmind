import { formatDateTime, humanize, riskBadgeVariant } from "../lib/report";
import type { NativeChange, RiskLevel } from "../services/api";
import { Badge } from "./ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

const changeVariants = { added: "default", modified: "warning", removed: "destructive" } as const;
function changeLabel(change: NativeChange): string {
  if (change.change_type === "modified") return `${humanize(change.field ?? "property")} modified`;
  return `${humanize(change.resource_type)} ${change.change_type}`;
}

interface ChangeTableProps { changes: NativeChange[]; risk: RiskLevel | null; runTime: string }
export function ChangeTable({ changes, risk, runTime }: ChangeTableProps) {
  return <Card><CardHeader className="flex-row items-center justify-between space-y-0"><CardTitle>Detected Changes</CardTitle><Badge variant="secondary">{changes.length}</Badge></CardHeader><CardContent>
    {changes.length === 0 ? <div className="flex min-h-36 items-center justify-center rounded-lg border border-dashed border-slate-700 px-6 text-center text-sm leading-6 text-slate-400">No infrastructure drift detected. The latest autonomous scan verified the infrastructure baseline successfully.</div> : <div className="table-shell"><table className="data-table"><caption className="sr-only">Infrastructure changes detected during the latest autonomous run</caption><thead><tr><th scope="col">Resource</th><th scope="col">Change</th><th scope="col">Risk</th><th scope="col">Time</th></tr></thead><tbody>{changes.map((change) => <tr key={change.change_id}><td><p className="font-medium text-white">{change.logical_name}</p><p className="mt-1 text-xs text-slate-500">{humanize(change.resource_type)}</p></td><td><Badge variant={changeVariants[change.change_type]}>{changeLabel(change)}</Badge></td><td><Badge variant={riskBadgeVariant(risk)}>{risk ?? "Not analyzed"}</Badge></td><td className="whitespace-nowrap">{formatDateTime(runTime)}</td></tr>)}</tbody></table></div>}
  </CardContent></Card>;
}