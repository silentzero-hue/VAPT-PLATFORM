import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router-dom";
import { ClipboardList, Plus, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { cn, formatDate, getDominantSeverity, SEVERITY_BAR } from "../../lib/cn";
import type { Engagement } from "../../types";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import Toolbar from "../../components/ui/Toolbar";

export default function EngagementsPage() {
  const { wid } = useParams();
  const auth = useAuth();
  const navigate = useNavigate();
  const workspaceId = wid ?? auth.activeWorkspace;
  const engs = useQuery({
    queryKey: ["engagements", workspaceId],
    queryFn: async () =>
      (await api.get<Engagement[]>(`/workspaces/${workspaceId}/engagements`)).data,
    enabled: !!workspaceId,
  });

  const qc = useQueryClient();
  const [showNew, setShowNew] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [client, setClient] = useState("");
  const [type, setType] = useState("webapp");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [reportDue, setReportDue] = useState("");

  const create = useMutation({
    mutationFn: async () => {
      const body: Record<string, unknown> = { code, name, client, type };
      if (startDate) body.start_date = startDate;
      if (endDate) body.end_date = endDate;
      if (reportDue) body.report_due_date = reportDue;
      return (
        await api.post<Engagement>(
          `/workspaces/${workspaceId}/engagements`,
          body,
        )
      ).data;
    },
    onSuccess: () => {
      toast.success("Engagement created");
      qc.invalidateQueries({ queryKey: ["engagements", workspaceId] });
      setShowNew(false);
      setCode("");
      setName("");
      setClient("");
      setType("webapp");
      setStartDate("");
      setEndDate("");
      setReportDue("");
    },
    onError: (e: any) =>
      toast.error(e?.response?.data?.detail ?? "Create failed"),
  });

  return (
    <div className="space-y-4 max-w-[1400px] mx-auto">
      <Toolbar
        left={
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Engagements</h1>
            <p className="text-sm text-fg-muted">
              Track each pentest contract from kickoff to delivery.
            </p>
          </div>
        }
        right={
          <button
            onClick={() => setShowNew(true)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-sm",
              "bg-accent text-white hover:bg-accent-strong",
              "transition-all duration-200 ease-out active:scale-[0.98]"
            )}
          >
            <Plus size={14} /> New engagement
          </button>
        }
      />

      {(engs.data ?? []).length === 0 ? (
        <Card>
          <EmptyState
            icon={ClipboardList}
            title="No engagements yet"
            description="Create your first engagement to start ingesting scans and tracking findings."
            cta={
              <button
                onClick={() => setShowNew(true)}
                className="rounded-full bg-accent hover:bg-accent-strong text-white px-4 py-1.5 text-sm transition-colors duration-200"
              >
                <Plus size={14} className="inline-block mr-1" /> New engagement
              </button>
            }
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {(engs.data ?? []).map((e) => {
            const dom = getDominantSeverity(e.severity_breakdown);
            return (
              <Card
                key={e.id}
                onClick={() =>
                  navigate(`/workspaces/${workspaceId}/engagements/${e.id}`)
                }
                className="card-hover p-5"
                ariaLabel={`Open engagement ${e.name}`}
              >
                {dom && <div className={cn("sev-bar", SEVERITY_BAR[dom] ?? "bg-sev-info")} />}
                <div className="flex items-center justify-between gap-2">
                  <div className="font-mono text-[11px] text-fg-muted truncate">
                    {e.code}
                  </div>
                  <span className="pill pill-muted shrink-0">{e.status}</span>
                </div>
                <div className="mt-1.5 text-base font-semibold leading-snug line-clamp-2">
                  {e.name}
                </div>
                <div className="text-xs text-fg-muted truncate mt-0.5">{e.client}</div>

                <div className="mt-4 flex flex-wrap gap-1.5">
                  <span className="chip chip-muted uppercase tracking-wider text-[10px]">
                    {e.type}
                  </span>
                  {e.methodology && (
                    <span className="chip chip-muted">{e.methodology}</span>
                  )}
                </div>

                <div className="mt-4 flex items-center justify-between text-[11px] text-fg-muted">
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-fg">{e.findings_total ?? 0}</span>
                    <span>findings</span>
                  </div>
                  {e.report_due_date && (
                    <div className="font-mono">due {formatDate(e.report_due_date)}</div>
                  )}
                </div>

                {e.severity_breakdown && (
                  <div className="mt-3 flex gap-1 flex-wrap">
                    {Object.entries(e.severity_breakdown)
                      .filter(([, n]) => n > 0)
                      .map(([sev, n]) => (
                        <span key={sev} className={cn("chip", `chip-${sev}`)}>
                          {sev} {n}
                        </span>
                      ))}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {showNew && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setShowNew(false)}
        >
          <div
            className="panel p-5 w-full max-w-lg max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold">New engagement</h2>
              <button
                onClick={() => setShowNew(false)}
                className="text-fg-muted hover:text-fg"
              >
                <X size={16} />
              </button>
            </div>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                create.mutate();
              }}
              className="grid grid-cols-2 gap-3"
            >
              <div>
                <label className="text-xs text-fg-muted">Code</label>
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  required
                  minLength={2}
                  maxLength={40}
                  placeholder="ENG-2026-01"
                  className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm mt-1 font-mono"
                />
              </div>
              <div>
                <label className="text-xs text-fg-muted">Type</label>
                <select
                  value={type}
                  onChange={(e) => setType(e.target.value)}
                  className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm mt-1"
                >
                  <option value="webapp">webapp</option>
                  <option value="network">network</option>
                  <option value="wireless">wireless</option>
                  <option value="mobile">mobile</option>
                  <option value="cloud">cloud</option>
                  <option value="redteam">redteam</option>
                  <option value="social">social</option>
                  <option value="other">other</option>
                </select>
              </div>
              <div className="col-span-2">
                <label className="text-xs text-fg-muted">Name</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  minLength={2}
                  maxLength={200}
                  placeholder="Acme webapp pentest"
                  className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm mt-1"
                />
              </div>
              <div className="col-span-2">
                <label className="text-xs text-fg-muted">Client</label>
                <input
                  value={client}
                  onChange={(e) => setClient(e.target.value)}
                  required
                  maxLength={200}
                  placeholder="Acme Corp"
                  className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm mt-1"
                />
              </div>
              <div>
                <label className="text-xs text-fg-muted">Start date</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm mt-1"
                />
              </div>
              <div>
                <label className="text-xs text-fg-muted">End date</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm mt-1"
                />
              </div>
              <div className="col-span-2">
                <label className="text-xs text-fg-muted">Report due</label>
                <input
                  type="date"
                  value={reportDue}
                  onChange={(e) => setReportDue(e.target.value)}
                  className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm mt-1"
                />
              </div>
              <button
                type="submit"
                disabled={create.isPending}
                className="col-span-2 bg-accent hover:bg-accent-strong text-white rounded-lg px-3 py-1.5 text-sm disabled:opacity-50"
              >
                {create.isPending ? "Creating…" : "Create engagement"}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
