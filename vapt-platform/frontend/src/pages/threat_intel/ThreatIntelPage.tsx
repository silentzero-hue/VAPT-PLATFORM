import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCcw, ShieldAlert, Sparkles, TrendingUp, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { SEVERITY_COLOR, formatDate } from "../../lib/cn";
import type { VulnWithIntel } from "../../types";

export default function ThreatIntelPage() {
  const { wid } = useParams();
  const auth = useAuth();
  const workspaceId = wid ?? auth.activeWorkspace;
  const qc = useQueryClient();
  const [intelModal, setIntelModal] = useState<{ cveId: string; data: any } | null>(null);

  const vulns = useQuery({
    queryKey: ["vulns-intel", workspaceId],
    queryFn: async () =>
      (
        await api.get<VulnWithIntel[]>(
          `/workspaces/${workspaceId}/threat-intel/feed?limit=200`
        )
      ).data,
    enabled: !!workspaceId,
  });

  const topRisk = useQuery({
    queryKey: ["top-risk", workspaceId],
    queryFn: async () =>
      (await api.get<any[]>(`/workspaces/${workspaceId}/findings/by-risk?limit=50`)).data,
    enabled: !!workspaceId,
  });

  const enrich = useMutation({
    mutationFn: async (vid: string) =>
      (await api.post(`/workspaces/${workspaceId}/vulnerabilities/${vid}/enrich`)).data,
    onSuccess: (data, vid) => {
      toast.success("Enriched");
      qc.invalidateQueries({ queryKey: ["vulns-intel", workspaceId] });
      if (data?.cve_id) setIntelModal({ cveId: data.cve_id, data });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Enrich failed"),
  });

  const showIntel = useMutation({
    mutationFn: async (cveId: string) =>
      (await api.get(`/workspaces/${workspaceId}/threat-intel/${cveId}`)).data,
    onSuccess: (data, cveId) => setIntelModal({ cveId, data }),
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "No intel yet"),
  });

  const recompute = useMutation({
    mutationFn: async () =>
      (await api.post(`/workspaces/${workspaceId}/findings/recompute-risk`)).data,
    onSuccess: (data) =>
      toast.success(`Recomputed ${data?.updated ?? 0} findings`),
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Recompute failed"),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <ShieldAlert size={20} className="text-accent" /> Threat intelligence
          </h1>
          <p className="text-sm text-fg-muted">
            Enrich vulns with EPSS / KEV / CVSS v3 and rank findings by composite risk
          </p>
        </div>
        <button
          onClick={() => recompute.mutate()}
          disabled={recompute.isPending}
          className="bg-accent hover:bg-accent-strong text-white rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5 disabled:opacity-50"
        >
          <RefreshCcw size={14} />
          {recompute.isPending ? "Recomputing…" : "Recompute all risk scores"}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="panel p-4 col-span-2">
          <h3 className="text-sm font-semibold mb-3">Vulnerabilities</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-fg-muted text-xs bg-bg-soft">
                <tr className="text-left">
                  <th className="px-2 py-2">Severity</th>
                  <th className="px-2 py-2">Title / CVE</th>
                  <th className="px-2 py-2">CVSS v3</th>
                  <th className="px-2 py-2">EPSS</th>
                  <th className="px-2 py-2">KEV</th>
                  <th className="px-2 py-2">Last enriched</th>
                  <th className="px-2 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {(vulns.data ?? []).map((v) => (
                  <tr key={v.id} className="border-t border-border-soft hover:bg-bg-soft/40">
                    <td className="px-2 py-2">
                      <span className={`chip ${SEVERITY_COLOR[v.severity]}`}>{v.severity}</span>
                    </td>
                    <td className="px-2 py-2">
                      <div className="truncate max-w-xs">{v.title}</div>
                      {v.cve_id && (
                        <div className="font-mono text-[10px] text-fg-muted">{v.cve_id}</div>
                      )}
                    </td>
                    <td className="px-2 py-2 font-mono text-xs">
                      {v.cvss_score != null ? v.cvss_score.toFixed(1) : "—"}
                    </td>
                    <td className="px-2 py-2 font-mono text-xs">
                      {v.epss_score != null ? (
                        <span>
                          {(v.epss_score * 100).toFixed(1)}%
                          {v.epss_percentile != null && (
                            <span className="text-fg-muted">
                              {" "}· p{(v.epss_percentile * 100).toFixed(0)}
                            </span>
                          )}
                        </span>
                      ) : (
                        <span className="text-fg-subtle">—</span>
                      )}
                    </td>
                    <td className="px-2 py-2">
                      {v.kev ? (
                        <span className="pill bg-rose-500/15 text-rose-300 border-rose-500/30">
                          KEV
                        </span>
                      ) : (
                        <span className="text-fg-subtle">—</span>
                      )}
                    </td>
                    <td className="px-2 py-2 text-fg-muted text-xs">
                      {formatDate(v.fetched_at)}
                    </td>
                    <td className="px-2 py-2">
                      <div className="flex gap-1">
                        {v.cve_id && (
                          <button
                            onClick={() => showIntel.mutate(v.cve_id!)}
                            className="text-xs px-2 py-1 bg-bg-soft border border-border-soft rounded hover:border-accent"
                          >
                            View
                          </button>
                        )}
                        <button
                          onClick={() => enrich.mutate(v.id)}
                          disabled={enrich.isPending}
                          className="bg-accent/15 hover:bg-accent/25 text-accent border border-accent/30 rounded-lg px-2 py-1 text-xs flex items-center gap-1 disabled:opacity-50"
                        >
                          <Sparkles size={10} /> Enrich
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {(vulns.data ?? []).length === 0 && (
                  <tr>
                    <td colSpan={7} className="text-center text-fg-muted py-8">
                      No vulnerabilities
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel p-4">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-1.5">
            <TrendingUp size={14} /> Top by risk
          </h3>
          <ol className="space-y-1 text-sm">
            {(topRisk.data ?? []).map((f: any, i: number) => (
              <li
                key={f.id ?? i}
                className="flex items-center gap-2 border-t border-border-soft py-1.5"
              >
                <span className="font-mono text-xs text-fg-muted w-6">#{i + 1}</span>
                <span
                  className={`chip ${SEVERITY_COLOR[f.effective_severity] ?? "chip-muted"}`}
                >
                  {f.effective_severity}
                </span>
                <span className="flex-1 truncate">
                  {f.vuln_title ?? f.title ?? "—"}
                </span>
                <span className="font-mono text-xs text-accent">
                  {(f.risk_score ?? 0).toFixed(1)}
                </span>
              </li>
            ))}
            {(topRisk.data ?? []).length === 0 && (
              <li className="text-fg-muted text-center py-6">
                No ranked findings yet
              </li>
            )}
          </ol>
        </div>
      </div>

      {intelModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setIntelModal(null)}
        >
          <div
            className="panel p-5 max-w-2xl w-full max-h-[80vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold font-mono">{intelModal.cveId}</h2>
              <button
                onClick={() => setIntelModal(null)}
                className="text-fg-muted hover:text-fg"
              >
                <X size={16} />
              </button>
            </div>
            <pre className="text-xs bg-bg-soft border border-border-soft rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">
              {JSON.stringify(intelModal.data, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
