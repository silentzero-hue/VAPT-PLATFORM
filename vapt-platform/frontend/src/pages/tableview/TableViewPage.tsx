import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { SEVERITY_COLOR, cn, formatDate } from "../../lib/cn";
import type { Engagement, Severity, TableRow, TableViewPayload } from "../../types";
import { FileText, Download, Printer } from "lucide-react";

const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low", "info"];

const SEVERITY_HEADING: Record<Severity, string> = {
  critical: "bg-sev-critical-soft border-sev-critical text-sev-critical-strong",
  high: "bg-sev-high-soft border-sev-high text-sev-high-strong",
  medium: "bg-sev-medium-soft border-sev-medium text-sev-medium-strong",
  low: "bg-sev-low-soft border-sev-low text-sev-low-strong",
  info: "bg-sev-info-soft border-sev-info text-sev-info-strong",
};

const SEVERITY_TEXT: Record<Severity, string> = {
  critical: "text-sev-critical-strong",
  high: "text-sev-high-strong",
  medium: "text-sev-medium-strong",
  low: "text-sev-low-strong",
  info: "text-finder-blue",
};

export default function TableViewPage() {
  const { wid, eid: eidParam } = useParams();
  const auth = useAuth();
  const workspaceId = wid ?? auth.activeWorkspace;
  const [engagementId, setEngagementId] = useState<string>(eidParam ?? "");

  const engs = useQuery({
    queryKey: ["engagements", workspaceId],
    queryFn: async () =>
      (await api.get<Engagement[]>(`/workspaces/${workspaceId}/engagements`)).data,
    enabled: !!workspaceId,
  });

  const activeEngagementId = engagementId || engs.data?.[0]?.id || "";

  const data = useQuery({
    queryKey: ["table-view", activeEngagementId],
    queryFn: async () =>
      (
        await api.get<TableViewPayload>(
          `/engagements/${activeEngagementId}/table-view?fmt=json`
        )
      ).data,
    enabled: !!activeEngagementId,
  });

  const downloadFile = useMutation({
    mutationFn: async (vars: { fmt: "docx" | "html" }) => {
      const res = await api.get(
        `/engagements/${activeEngagementId}/table-view?fmt=${vars.fmt}`,
        { responseType: "blob" }
      );
      const ext = vars.fmt === "docx" ? "docx" : "html";
      const mime =
        vars.fmt === "docx"
          ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          : "text/html";
      const blob = new Blob([res.data], { type: mime });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `table-view-${data.data?.engagement.code ?? activeEngagementId}.${ext}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },
    onSuccess: (_d, vars) => toast.success(`Downloaded ${vars.fmt.toUpperCase()}`),
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Download failed"),
  });

  return (
    <div className="space-y-4 max-w-[1400px] mx-auto p-4 min-w-0">
      <div className="flex items-end justify-between gap-3 flex-wrap no-print">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <FileText size={20} className="text-finder-blue" /> Table view
          </h1>
          <p className="text-sm text-ink-muted">
            Banded executive view of all findings, grouped by severity — ready to print or export
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={activeEngagementId}
            onChange={(e) => setEngagementId(e.target.value)}
            className="bg-paper-soft border border-hairline rounded-lg px-2.5 py-1.5 text-sm no-print"
          >
            <option value="">Select engagement…</option>
            {(engs.data ?? []).map((e) => (
              <option key={e.id} value={e.id}>
                {e.name}
              </option>
            ))}
          </select>
          <button
            onClick={() => downloadFile.mutate({ fmt: "docx" })}
            disabled={!activeEngagementId || downloadFile.isPending}
            className="bg-paper-soft border border-hairline hover:border-finder-blue rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5 disabled:opacity-50"
          >
            <Download size={14} /> DOCX
          </button>
          <button
            onClick={() => downloadFile.mutate({ fmt: "html" })}
            disabled={!activeEngagementId || downloadFile.isPending}
            className="bg-paper-soft border border-hairline hover:border-finder-blue rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5 disabled:opacity-50"
          >
            <Download size={14} /> HTML
          </button>
          <button
            onClick={() => {
              document.body.classList.add("printing");
              setTimeout(() => {
                window.print();
                document.body.classList.remove("printing");
              }, 0);
            }}
            disabled={!data.data}
            className="bg-finder-blue hover:bg-folder-to text-white rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5 disabled:opacity-50"
          >
            <Printer size={14} /> Print
          </button>
        </div>
      </div>

      {data.isLoading && (
        <div className="panel p-10 text-center text-ink-muted text-sm">
          Loading findings…
        </div>
      )}

      {data.data && (
        <div className="panel p-6 space-y-5 print:p-0 print:shadow-none print-area">
          <div className="border-b border-hairline pb-3 flex items-end justify-between">
            <div>
              <div className="text-xs text-ink-muted font-mono">
                {data.data.engagement.code}
              </div>
              <h2 className="text-xl font-semibold">{data.data.engagement.name}</h2>
              <p className="text-sm text-ink-muted">{data.data.engagement.client}</p>
            </div>
            <div className="text-xs text-ink-muted">
              Generated {formatDate(data.data.generated_at)}
            </div>
          </div>

          {SEVERITY_ORDER.map((sev) => {
            const rows = data.data!.by_severity?.[sev] ?? [];
            const total = data.data!.totals?.[sev] ?? rows.length;
            return (
              <section key={sev} className="space-y-2 break-inside-avoid">
                <div
                  className={cn(
                    "px-3 py-2 rounded-lg border flex items-center justify-between",
                    SEVERITY_HEADING[sev]
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span className={`chip ${SEVERITY_COLOR[sev]}`}>{sev}</span>
                    <h3 className="text-sm font-semibold uppercase tracking-wide">
                      {sev} findings
                    </h3>
                  </div>
                  <span className="text-xs font-mono">{total} total</span>
                </div>
                {rows.length === 0 ? (
                  <p className="text-sm text-ink-muted px-2">
                    No {sev} findings.
                  </p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="text-ink-muted text-xs bg-paper-soft">
                        <tr className="text-left">
                          <th className="px-3 py-2">CVE</th>
                          <th className="px-3 py-2">Title</th>
                          <th className="px-3 py-2">CVSS</th>
                          <th className="px-3 py-2">Hosts</th>
                          <th className="px-3 py-2">Ports</th>
                          <th className="px-3 py-2">Sample asset</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((r, i) => (
                          <tr
                            key={`${r.cve_id ?? r.title}-${i}`}
                            className="border-t border-hairline"
                          >
                            <td className="px-3 py-2 font-mono text-xs text-ink-muted">
                              {r.cve_id ?? "—"}
                            </td>
                            <td
                              className={cn(
                                "px-3 py-2 font-medium",
                                SEVERITY_TEXT[sev]
                              )}
                            >
                              {r.title}
                            </td>
                            <td className="px-3 py-2 font-mono text-xs">
                              {r.cvss_score != null ? r.cvss_score.toFixed(1) : "—"}
                            </td>
                            <td className="px-3 py-2 font-mono text-xs text-ink-muted">
                              {r.hosts.length}
                            </td>
                            <td className="px-3 py-2 font-mono text-xs text-ink-muted">
                              {r.ports.length === 0
                                ? "—"
                                : r.ports.slice(0, 6).join(", ") +
                                  (r.ports.length > 6 ? "…" : "")}
                            </td>
                            <td className="px-3 py-2 font-mono text-xs text-ink-muted truncate max-w-xs">
                              {r.sample_asset ?? "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            );
          })}

          {SEVERITY_ORDER.every(
            (s) => (data.data!.by_severity?.[s] ?? []).length === 0
          ) && (
            <div className="text-center text-ink-muted py-10 text-sm">
              No findings to display.
            </div>
          )}
        </div>
      )}

      {!data.isLoading && !data.data && (
        <div className="panel p-10 text-center text-ink-muted text-sm">
          Select an engagement to generate the table view.
        </div>
      )}
    </div>
  );
}
