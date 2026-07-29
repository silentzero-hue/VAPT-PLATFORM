import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { cn, formatDate, getDominantSeverity, SEVERITY_BAR, SEVERITY_TEXT } from "../../lib/cn";
import type { Engagement, EngagementStatus } from "../../types";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import FolderCard from "../../components/ui/FolderCard";
import Toolbar from "../../components/ui/Toolbar";
import ViewToggle, { type ViewMode } from "../../components/ui/ViewToggle";
import { List, Plus, X } from "lucide-react";

const STATUS_PILL: Record<string, string> = {
  active: "bg-sev-low-soft text-sev-low-strong border-sev-low",
  in_reporting: "bg-sev-info-soft text-sev-info-strong border-sev-info",
  delivered: "bg-sev-low-soft text-sev-low-strong border-sev-low",
  closed: "bg-paper-soft text-ink-muted border-hairline-strong",
  planned: "bg-sev-medium-soft text-sev-medium-strong border-sev-medium",
  cancelled: "bg-sev-critical-soft text-sev-critical-strong border-sev-critical",
};

const STATUS_LABEL: Record<EngagementStatus, string> = {
  active: "Active",
  in_reporting: "In reporting",
  delivered: "Delivered",
  closed: "Closed",
  planned: "Planned",
  cancelled: "Cancelled",
};

const COLUMN_GROUPS: { key: EngagementStatus | "all"; label: string }[] = [
  { key: "active", label: "Active" },
  { key: "in_reporting", label: "In reporting" },
  { key: "planned", label: "Planned" },
  { key: "delivered", label: "Delivered" },
  { key: "closed", label: "Closed" },
];

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
  const [view, setView] = useState<ViewMode>("grid");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [q, setQ] = useState("");

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

  const filtered = useMemo(() => {
    const all = engs.data ?? [];
    const needle = q.trim().toLowerCase();
    if (!needle) return all;
    return all.filter(
      (e) =>
        e.name.toLowerCase().includes(needle) ||
        e.client.toLowerCase().includes(needle) ||
        e.code.toLowerCase().includes(needle)
    );
  }, [engs.data, q]);

  const groupedByStatus = useMemo(() => {
    const m: Record<string, Engagement[]> = {};
    for (const e of filtered) {
      const k = e.status ?? "other";
      (m[k] ??= []).push(e);
    }
    return m;
  }, [filtered]);

  const open = (e: Engagement) => {
    navigate(`/workspaces/${workspaceId}/engagements/${e.id}`);
  };

  return (
    <div className="space-y-4 max-w-[1400px] mx-auto">
      <Toolbar
        left={
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Engagements</h1>
            <p className="text-sm text-ink-muted">
              Track each pentest contract from kickoff to delivery.
            </p>
          </div>
        }
        right={
          <div className="flex items-center gap-2">
            <div className="relative">
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                type="search"
                placeholder="Filter…"
                className={cn(
                  "bg-paper-soft border border-hairline-strong rounded-full",
                  "pl-3 pr-3 h-8 text-sm outline-none w-44",
                  "focus:border-finder-blue/50 transition-colors duration-200 ease-out",
                  "placeholder:text-ink-subtle"
                )}
              />
            </div>
            <ViewToggle value={view} onChange={setView} />
            <button
              onClick={() => setShowNew(true)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-sm",
                "bg-finder-blue text-white hover:bg-folder-to",
                "transition-all duration-200 ease-out active:scale-[0.98]"
              )}
            >
              <Plus size={14} /> New engagement
            </button>
          </div>
        }
      />

      {(engs.data ?? []).length === 0 ? (
        <Card>
          <EmptyState
            icon={<List size={20} className="text-ink-muted" />}
            title="No engagements yet"
            description="Create your first engagement to start ingesting scans and tracking findings."
            cta={
              <button
                onClick={() => setShowNew(true)}
                className="rounded-full bg-finder-blue hover:bg-folder-to text-white px-4 py-1.5 text-sm transition-colors duration-200"
              >
                <Plus size={14} className="inline-block mr-1" /> New engagement
              </button>
            }
          />
        </Card>
      ) : filtered.length === 0 ? (
        <Card>
          <div className="p-6 text-center text-sm text-ink-muted">
            No engagements match "{q}".
          </div>
        </Card>
      ) : view === "grid" ? (
        <EngagementGrid
          items={filtered}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onOpen={open}
          onCreateNew={() => setShowNew(true)}
        />
      ) : view === "list" ? (
        <EngagementList items={filtered} onOpen={open} />
      ) : (
        <EngagementColumns
          items={filtered}
          groupedByStatus={groupedByStatus}
          onOpen={open}
        />
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
                className="text-ink-muted hover:text-ink"
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
                <label className="text-xs text-ink-muted">Code</label>
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  required
                  minLength={2}
                  maxLength={40}
                  placeholder="ENG-2026-01"
                  className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-sm mt-1 font-mono"
                />
              </div>
              <div>
                <label className="text-xs text-ink-muted">Type</label>
                <select
                  value={type}
                  onChange={(e) => setType(e.target.value)}
                  className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-sm mt-1"
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
                <label className="text-xs text-ink-muted">Name</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  minLength={2}
                  maxLength={200}
                  placeholder="Acme webapp pentest"
                  className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-sm mt-1"
                />
              </div>
              <div className="col-span-2">
                <label className="text-xs text-ink-muted">Client</label>
                <input
                  value={client}
                  onChange={(e) => setClient(e.target.value)}
                  required
                  maxLength={200}
                  placeholder="Acme Corp"
                  className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-sm mt-1"
                />
              </div>
              <div>
                <label className="text-xs text-ink-muted">Start date</label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-sm mt-1"
                />
              </div>
              <div>
                <label className="text-xs text-ink-muted">End date</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-sm mt-1"
                />
              </div>
              <div className="col-span-2">
                <label className="text-xs text-ink-muted">Report due</label>
                <input
                  type="date"
                  value={reportDue}
                  onChange={(e) => setReportDue(e.target.value)}
                  className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-sm mt-1"
                />
              </div>
              <button
                type="submit"
                disabled={create.isPending}
                className="col-span-2 bg-finder-blue hover:bg-folder-to text-white rounded-lg px-3 py-1.5 text-sm disabled:opacity-50"
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

function EngagementGrid({
  items,
  selectedId,
  onSelect,
  onOpen,
  onCreateNew,
}: {
  items: Engagement[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onOpen: (e: Engagement) => void;
  onCreateNew: () => void;
}) {
  return (
    <div
      className={cn(
        "grid gap-3",
        "grid-cols-[repeat(auto-fill,minmax(108px,1fr))]"
      )}
    >
      {items.map((e) => (
        <FolderCard
          key={e.id}
          name={e.name}
          sub={
            <span className="inline-flex items-center gap-1">
              <span className="font-mono text-ink-muted">
                {e.findings_total ?? 0}
              </span>
              <span>findings</span>
            </span>
          }
          selected={selectedId === e.id}
          onClick={() => onSelect(e.id)}
          onDoubleClick={() => onOpen(e)}
          ariaLabel={`Open engagement ${e.name}`}
        />
      ))}
      <button
        type="button"
        onClick={onCreateNew}
        className={cn(
          "flex flex-col items-center gap-1.5 p-2 rounded-lg",
          "border-2 border-dashed border-hairline-strong text-ink-subtle",
          "hover:border-finder-blue/50 hover:text-ink hover:bg-paper-soft",
          "transition-colors duration-150 ease-out"
        )}
      >
        <svg
          width="44"
          height="34"
          viewBox="0 0 44 34"
          aria-hidden="true"
          className="opacity-60"
        >
          <path
            d="M2 6a2 2 0 0 1 2-2h10l3 4h21a2 2 0 0 1 2 2v20a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2z"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeDasharray="3 3"
          />
          <path d="M22 14v10M17 19h10" stroke="currentColor" strokeWidth="1.6" />
        </svg>
        <span className="text-[11.5px]">New engagement</span>
      </button>
    </div>
  );
}

function EngagementList({
  items,
  onOpen,
}: {
  items: Engagement[];
  onOpen: (e: Engagement) => void;
}) {
  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[760px]">
          <thead className="text-ink-muted text-xs bg-paper-soft/50">
            <tr className="text-left">
              <th className="px-3 py-2.5 font-medium">Name</th>
              <th className="px-3 py-2.5 font-medium">Code</th>
              <th className="px-3 py-2.5 font-medium">Client</th>
              <th className="px-3 py-2.5 font-medium">Type</th>
              <th className="px-3 py-2.5 font-medium">Status</th>
              <th className="px-3 py-2.5 font-medium text-right">Findings</th>
              <th className="px-3 py-2.5 font-medium">Due</th>
            </tr>
          </thead>
          <tbody>
            {items.map((e) => {
              const dom = getDominantSeverity(e.severity_breakdown);
              return (
                <tr
                  key={e.id}
                  onClick={() => onOpen(e)}
                  className={cn(
                    "border-t border-hairline cursor-pointer",
                    "hover:bg-paper-soft transition-colors duration-150"
                  )}
                >
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-2">
                      {dom && (
                        <span
                          className={cn(
                            "h-4 w-0.5 rounded-full shrink-0",
                            SEVERITY_BAR[dom] ?? "bg-sev-info"
                          )}
                        />
                      )}
                      <span className="font-medium truncate">{e.name}</span>
                    </div>
                  </td>
                  <td className="px-3 py-2.5 font-mono text-[11px] text-ink-muted">
                    {e.code}
                  </td>
                  <td className="px-3 py-2.5 text-ink-muted truncate max-w-[180px]">
                    {e.client}
                  </td>
                  <td className="px-3 py-2.5">
                    <span className="chip chip-muted uppercase tracking-wider text-[10px]">
                      {e.type}
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    <span
                      className={cn(
                        "inline-flex items-center px-2 py-0.5 rounded-md text-[10.5px] border",
                        STATUS_PILL[e.status] ?? "bg-paper-soft text-ink-muted border-hairline-strong"
                      )}
                    >
                      {STATUS_LABEL[e.status as EngagementStatus] ?? e.status}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono tabular-nums">
                    {e.findings_total ?? 0}
                  </td>
                  <td className="px-3 py-2.5 text-ink-muted text-xs whitespace-nowrap">
                    {e.report_due_date ? formatDate(e.report_due_date) : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function EngagementColumns({
  items,
  groupedByStatus,
  onOpen,
}: {
  items: Engagement[];
  groupedByStatus: Record<string, Engagement[]>;
  onOpen: (e: Engagement) => void;
}) {
  return (
    <Card className="overflow-hidden">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 divide-x divide-white/[0.05]">
        {COLUMN_GROUPS.map((col) => {
          const list = groupedByStatus[col.key] ?? [];
          return (
            <div key={col.key} className="min-h-[280px] flex flex-col">
              <div className="px-3 py-2 text-[11px] uppercase tracking-wider text-ink-muted border-b border-hairline flex items-center justify-between">
                <span className="font-semibold">{col.label}</span>
                <span className="text-ink-subtle tabular-nums">{list.length}</span>
              </div>
              <div className="flex-1 overflow-y-auto p-2 space-y-1">
                {list.length === 0 ? (
                  <div className="text-[11px] text-ink-subtle text-center py-4">
                    No items
                  </div>
                ) : (
                  list.map((e) => {
                    const dom = getDominantSeverity(e.severity_breakdown);
                    return (
                      <button
                        key={e.id}
                        onClick={() => onOpen(e)}
                        className={cn(
                          "w-full text-left px-2 py-1.5 rounded-md",
                          "hover:bg-paper-soft active:bg-paper-deep",
                          "transition-colors duration-150"
                        )}
                      >
                        <div className="flex items-start gap-1.5">
                          {dom && (
                            <span
                              className={cn(
                                "h-4 w-0.5 rounded-full shrink-0 mt-0.5",
                                SEVERITY_BAR[dom] ?? "bg-sev-info"
                              )}
                            />
                          )}
                          <div className="min-w-0 flex-1">
                            <div className="text-[12px] truncate">{e.name}</div>
                            <div className="text-[10px] text-ink-muted truncate font-mono">
                              {e.code}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center justify-between mt-1 text-[10px] text-ink-subtle">
                          <span className="truncate">{e.client}</span>
                          <span
                            className={cn(
                              "font-mono tabular-nums",
                              SEVERITY_TEXT[dom ?? "info"]
                            )}
                          >
                            {e.findings_total ?? 0}
                          </span>
                        </div>
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          );
        })}
      </div>
      {items.length === 0 && (
        <div className="p-6 text-center text-sm text-ink-muted">
          No engagements to show.
        </div>
      )}
    </Card>
  );
}
