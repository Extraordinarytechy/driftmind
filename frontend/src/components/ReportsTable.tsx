import { Download } from "lucide-react";
import { formatDateTime, statusLabel } from "../lib/report";
import type { AutonomousReport } from "../services/api";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

export function ReportsTable({ report }: { report: AutonomousReport }) {
  const download = () => {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `driftmind-report-${report.run_time.replace(/:/g, "-")}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };
  return <Card><CardHeader><CardTitle>Recent Reports</CardTitle></CardHeader><CardContent><div className="table-shell"><table className="data-table min-w-[480px]"><caption className="sr-only">Latest available autonomous report</caption><thead><tr><th scope="col">Generated</th><th scope="col">Status</th><th scope="col" className="text-right">Download</th></tr></thead><tbody><tr><td>{formatDateTime(report.run_time)}</td><td><Badge variant={report.status === "DRIFT_DETECTED" ? "warning" : "default"}>{statusLabel(report.status)}</Badge></td><td className="text-right"><Button type="button" variant="outline" onClick={download}><Download className="h-4 w-4" />Download JSON</Button></td></tr></tbody></table></div></CardContent></Card>;
}