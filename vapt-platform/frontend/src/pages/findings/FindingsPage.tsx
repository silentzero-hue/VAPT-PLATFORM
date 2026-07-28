import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertOctagon, Bug, Filter, MessageSquare, RefreshCcw, Search, X } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { cn, formatDate, SEVERITY_BAR, SEVERITY_COLOR } from "../../lib/cn";
import type { Finding, FindingStatus, Severity } from "../../types";
import { CommentsPanel } from "../../components/comments/CommentsPanel";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import Toolbar from "../../components/ui/Toolbar";
import ViewToggle, { type ViewMode } from "../../components/ui/ViewToggle";

const STATUSES: FindingStatus[] = [
  "new", "confirmed", "in_remediation",
  "remediated_pending_confirmation", "regressed",
  "resolved", "false_positive", "accepted_risk", "deferred",
];

export default function FindingsPage() {
  const { wid } = useParams();
  const auth = useAuth();
  const workspaceId = wid ?? auth.activeWorkspace;
  const qc = useQueryClient();
  const [engagementId, setEngagementId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<FindingStatus | "all">("all");
  const [sevFilter, setSevFilter] = useState<Severity | "all">("all");
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState<string | null>(null);
  const [view, setView] = useState<ViewMode>("grid");
  const [searchParams] = useSearchParams();
  const focusFromUrl = searchParams.get("focus");

  const engs = useQuery({
    queryKey: ["engagements", workspaceId],
    queryFn: async () =>
      (await api.get<any[]>(`/workspaces/${workspaceId}/engagements`)).data,
    enabled: !!workspaceId,
  });

  const engId = engagementId ?? engs.data?.[0]?.id ?? null;

  useEffect(() => {
    const id = setTimeout(() => setDebouncedQ(q), 250);
    return () => clearTimeout(id);
  }, [q]);

  const findings = useQuery({
    queryKey: ["findings", engId, statusFilter, sevFilter, debouncedQ],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (statusFilter !== "all") params.set("status", statusFilter);
      if (debouncedQ) params.set("q", debouncedQ);
      const res = await api.get<Finding[]>(`/engagements/${engId}/findings?${params}`);
      let list = res.data;
      if (sevFilter !== "all") list = list.filter((f) => f.effective_severity === sevFilter);
      return list;
    },
    enabled: !!engId,
  });

  const triage = useMutation({
    mutationFn: async (vars: { ids: string[]; action: string; comment?: string; severity_override?: string }) => {
      return api.post("/findings/bulk-triage", {
        finding_ids: vars.ids,
        action: { action: vars.action, comment: vars.comment, severity_override: vars.severity_override },
      });
    },
    onSuccess: () => {
      toast.success("Updated");
      qc.invalidateQueries({ queryKey: ["findings", engId] });
      setSelected(new Set());
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Triage failed"),
  });

  const visible = useMemo(() => findings.data ?? [], [findings.data]);
  const allChecked = visible.length > 0 && visible.every((f) => selected.has(f.id));
  const someChecked = !allChecked && visible.some((f) => selected.has(f.id));

  return (
    <div className="space-y-4 max-w-[1400px] mx-auto">
      <Toolbar
        left={
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Triage queue</h1>
            <p className="text-sm text-fg-muted">
              One row per (vulnerability, asset, port) — multiple hosts share a single vulnerability.
            </p>
          </div>
        }
        right={
          <>
            <select
              value={engId ?? ""}
              onChange={(e) => { setEngagementId(e.target.value); setSelected(new Set()); }}
              className={cn(
                "bg-white/[0.04] border border-white/[0.08] rounded-full",
                "px-3 py-1.5 text-sm outline-none focus:border-accent/50",
                "transition-colors duration-200 ease-out"
              )}
            >
              {(engs.data ?? []).map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
            </select>
            <ViewToggle value={view} onChange={setView} />
            <button
              onClick={() => findings.refetch()}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm",
                "bg-white/[0.04] border border-white/[0.08] hover:border-accent/40",
                "transition-colors duration-200 ease-out"
              )}
            >
              <RefreshCcw size={14} /> Refresh
            </button>
          </>
        }
      />

      {/* Bulk action toolbar (slide-down when items selected) */}
      {selected.size > 0 && (
        <div className="animate-slide-down glass-strong rounded-2xl p-3 flex flex-wrap items-center gap-2">
          <span className="text-xs text-fg-muted ml-1">
            <span className="text-fg font-medium">{selected.size}</span> selected
          </span>
          <button
            onClick={() => triage.mutate({ ids: [...selected], action: "confirm" })}
            className="rounded-lg px-3 py-1 text-xs pill-success hover:brightness-125 transition-all duration-200"
          >
            Confirm
          </button>
          <button
            onClick={() => triage.mutate({ ids: [...selected], action: "reject" })}
            className="rounded-lg px-3 py-1 text-xs pill-danger hover:brightness-125 transition-all duration-200"
          >
            Reject
          </button>
          <button
            onClick={() => triage.mutate({ ids: [...selected], action: "mark_remediated" })}
            className="rounded-lg px-3 py-1 text-xs pill-info hover:brightness-125 transition-all duration-200"
          >
            Mark remediated
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="ml-auto text-fg-muted hover:text-fg p-1.5 rounded-md hover:bg-white/[0.05] transition-colors duration-200"
            title="Clear selection"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Filters */}
      <Card className="p-3 flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[220px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-fg-muted" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by title, CVE…"
            className={cn(
              "w-full bg-white/[0.04] border border-white/[0.08] focus:border-accent/50",
              "rounded-full pl-9 pr-4 py-1.5 text-sm outline-none",
              "transition-colors duration-200 ease-out placeholder:text-fg-subtle"
            )}
          />
        </div>
        <FilterPill label="Status" value={statusFilter} options={["all", ...STATUSES]} onChange={(v) => setStatusFilter(v as any)} />
        <FilterPill label="Severity" value={sevFilter} options={["all", "critical", "high", "medium", "low", "info"]} onChange={(v) => setSevFilter(v as any)} />
      </Card>

      {/* Empty state */}
      {visible.length === 0 ? (
        <Card>
          <EmptyState
            icon={Bug}
            title="No findings"
            description="Once you ingest scans for this engagement, findings will appear here for triage."
          />
        </Card>
      ) : view === "grid" ? (
        <FindingsGrid
          findings={visible}
          selected={selected}
          setSelected={setSelected}
          workspaceId={workspaceId ?? ""}
        />
      ) : (
        <FindingsTable
          findings={visible}
          selected={selected}
          setSelected={setSelected}
          allChecked={allChecked}
          someChecked={someChecked}
          workspaceId={workspaceId ?? ""}
          expanded={expanded}
          setExpanded={setExpanded}
        />
      )}
    </div>
  );
}

function FilterPill({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <div className="flex items-center gap-1.5 text-xs">
      <span className="text-fg-muted flex items-center gap-1"><Filter size={10} /> {label}:</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          "bg-white/[0.04] border border-white/[0.08] rounded-md px-2 py-1 outline-none",
          "focus:border-accent/50 transition-colors duration-200 ease-out"
        )}
      >
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}

function FindingsGrid({
  findings,
  selected,
  setSelected,
  workspaceId,
}: {
  findings: Finding[];
  selected: Set<string>;
  setSelected: (s: Set<string>) => void;
  workspaceId: string;
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {findings.map((f) => {
        const checked = selected.has(f.id);
        return (
          <Card
            key={f.id}
            selected={checked}
            onClick={() => {
              const next = new Set(selected);
              if (next.has(f.id)) next.delete(f.id);
              else next.add(f.id);
              setSelected(next);
            }}
            className={cn("card-hover p-4")}
            ariaLabel={`Finding ${f.vuln_title ?? f.vuln_cve_id}`}
          >
            <div
              className={cn(
                "sev-bar",
                SEVERITY_BAR[f.effective_severity] ?? "bg-sev-info"
              )}
            />
            <div className="flex items-center justify-between gap-2">
              <span className={cn("chip", SEVERITY_COLOR[f.effective_severity] ?? "chip-muted")}>
                {f.effective_severity}
              </span>
              {f.sla_breached ? (
                <span className="pill pill-danger">
                  <AlertOctagon size={10} /> SLA
                </span>
              ) : f.sla_due_at ? (
                <span className="text-[10px] text-fg-muted font-mono">
                  due {formatDate(f.sla_due_at)}
                </span>
              ) : null}
            </div>
            <Link
              to={`/workspaces/${workspaceId}/vulnerabilities/${f.vulnerability_id}?finding=${f.id}`}
              onClick={(e) => e.stopPropagation()}
              className="block mt-2 text-sm font-semibold leading-snug line-clamp-2 hover:text-accent transition-colors duration-200"
            >
              {f.vuln_title ?? f.vuln_cve_id ?? "—"}
            </Link>
            {f.vuln_cve_id && (
              <div className="text-[10px] font-mono text-fg-muted mt-0.5">{f.vuln_cve_id}</div>
            )}
            <div className="mt-3 flex items-center gap-2 text-[11px] text-fg-muted">
              <span className="font-mono truncate">{f.asset_value ?? "—"}</span>
              {f.port && (
                <>
                  <span className="text-fg-subtle">·</span>
                  <span className="font-mono">{f.port}/{f.protocol ?? "tcp"}</span>
                </>
              )}
            </div>
            <div className="mt-3 flex items-center justify-between text-[10px] text-fg-subtle">
              <span className="pill pill-muted">{f.status}</span>
              <span className="font-mono">{formatDate(f.first_seen)}</span>
            </div>
          </Card>
        );
      })}
    </div>
  );
}

function FindingsTable({
  findings,
  selected,
  setSelected,
  allChecked,
  someChecked,
  workspaceId,
  expanded,
  setExpanded,
}: {
  findings: Finding[];
  selected: Set<string>;
  setSelected: (s: Set<string>) => void;
  allChecked: boolean;
  someChecked: boolean;
  workspaceId: string;
  expanded: string | null;
  setExpanded: (s: string | null) => void;
}) {
  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[920px]">
          <thead className="text-fg-muted text-xs bg-white/[0.02]">
            <tr className="text-left">
              <th className="px-3 py-2.5 w-10">
                <input
                  type="checkbox"
                  className="accent-accent"
                  checked={allChecked}
                  ref={(el) => { if (el) el.indeterminate = someChecked; }}
                  onChange={(e) => {
                    if (e.target.checked) setSelected(new Set(findings.map((f) => f.id)));
                    else setSelected(new Set());
                  }}
                />
              </th>
              <th className="px-3 py-2.5 font-medium w-6"></th>
              <th className="px-3 py-2.5 font-medium">Severity</th>
              <th className="px-3 py-2.5 font-medium">Title</th>
              <th className="px-3 py-2.5 font-medium">Asset</th>
              <th className="px-3 py-2.5 font-medium">Port</th>
              <th className="px-3 py-2.5 font-medium">Status</th>
              <th className="px-3 py-2.5 font-medium">First seen</th>
              <th className="px-3 py-2.5 font-medium">SLA</th>
              <th className="px-3 py-2.5 font-medium w-10"></th>
            </tr>
          </thead>
          <tbody>
            {findings.map((f) => {
              const checked = selected.has(f.id);
              return (
                <FindingsRow
                  key={f.id}
                  f={f}
                  checked={checked}
                  setSelected={setSelected}
                  selected={selected}
                  workspaceId={workspaceId}
                  expanded={expanded === f.id}
                  setExpanded={setExpanded}
                />
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function FindingsRow({
  f,
  checked,
  setSelected,
  selected,
  workspaceId,
  expanded,
  setExpanded,
}: {
  f: Finding;
  checked: boolean;
  setSelected: (s: Set<string>) => void;
  selected: Set<string>;
  workspaceId: string;
  expanded: boolean;
  setExpanded: (s: string | null) => void;
}) {
  return (
    <>
      <tr
        className={cn(
          "border-b border-white/[0.05] hover:bg-white/[0.03]",
          "transition-colors duration-200 ease-out",
          checked && "bg-accent/[0.06]"
        )}
      >
        <td className="px-3 py-2.5">
          <input
            type="checkbox"
            className="accent-accent"
            checked={checked}
            onChange={(e) => {
              const next = new Set(selected);
              if (e.target.checked) next.add(f.id);
              else next.delete(f.id);
              setSelected(next);
            }}
          />
        </td>
        <td className="px-1 py-2.5">
          <div
            className={cn(
              "h-5 w-0.5 rounded-full",
              SEVERITY_BAR[f.effective_severity] ?? "bg-sev-info"
            )}
          />
        </td>
        <td className="px-3 py-2.5">
          <span className={cn("chip", SEVERITY_COLOR[f.effective_severity] ?? "chip-muted")}>
            {f.effective_severity}
          </span>
        </td>
        <td className="px-3 py-2.5 max-w-[280px]">
          <Link
            to={`/workspaces/${workspaceId}/vulnerabilities/${f.vulnerability_id}?finding=${f.id}`}
            className="text-fg hover:text-accent truncate block transition-colors duration-200"
          >
            {f.vuln_title ?? f.vuln_cve_id ?? "—"}
          </Link>
          {f.vuln_cve_id && (
            <div className="text-[10px] font-mono text-fg-muted">{f.vuln_cve_id}</div>
          )}
        </td>
        <td className="px-3 py-2.5 font-mono text-xs truncate max-w-[200px]">{f.asset_value ?? "—"}</td>
        <td className="px-3 py-2.5 font-mono text-xs text-fg-muted">
          {f.port ? `${f.port}/${f.protocol ?? "tcp"}` : "—"}
        </td>
        <td className="px-3 py-2.5">
          <span className="pill pill-muted">{f.status}</span>
        </td>
        <td className="px-3 py-2.5 text-fg-muted text-xs whitespace-nowrap">{formatDate(f.first_seen)}</td>
        <td className="px-3 py-2.5">
          {f.sla_breached ? (
            <span className="pill pill-danger">breached</span>
          ) : f.sla_due_at ? (
            <span className="text-fg-muted text-xs">{formatDate(f.sla_due_at)}</span>
          ) : (
            <span className="text-fg-subtle">—</span>
          )}
        </td>
        <td className="px-3 py-2.5 text-right">
          <button
            onClick={() => setExpanded(expanded ? null : f.id)}
            className="text-fg-muted hover:text-accent p-1 rounded transition-colors duration-200"
            title="Discuss"
          >
            <MessageSquare size={12} />
          </button>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-white/[0.02]">
          <td colSpan={10} className="px-3 py-3 border-b border-white/[0.05]">
            <CommentsPanel findingId={f.id} />
          </td>
        </tr>
      )}
    </>
  );
}
