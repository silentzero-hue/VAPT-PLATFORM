import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import AppleIcon from "../../components/ui/AppleIcon";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { SEVERITY_COLOR, cn, formatDate } from "../../lib/cn";
import type { CompareResult, DiffRow, IngestionJob } from "../../types";

export default function MultiScanPage() {
  const { wid, eid } = useParams();
  const auth = useAuth();
  const workspaceId = wid ?? auth.activeWorkspace;
  const engagementId = eid ?? "";
  const qc = useQueryClient();

  const [baseline, setBaseline] = useState("");
  const [current, setCurrent] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const jobs = useQuery({
    queryKey: ["ingestion-jobs", engagementId],
    queryFn: async () =>
      (await api.get<IngestionJob[]>(`/ingestion/engagements/${engagementId}/jobs`)).data,
    enabled: !!engagementId,
  });

  const compare = useQuery({
    queryKey: ["multiscan-compare", engagementId, baseline, current],
    queryFn: async () => {
      const params = new URLSearchParams({ baseline, current });
      return (
        await api.get<CompareResult>(
          `/engagements/${engagementId}/multiscan/compare?${params}`
        )
      ).data;
    },
    enabled: !!engagementId && !!baseline && !!current && baseline !== current,
  });

  const bulkDelete = useMutation({
    mutationFn: async (ids: string[]) =>
      api.post("/findings/bulk-delete", { finding_ids: ids }),
    onSuccess: (data: any) => {
      toast.success(`Deleted ${data?.deleted ?? selected.size} findings`);
      setSelected(new Set());
      qc.invalidateQueries({ queryKey: ["multiscan-compare", engagementId] });
      qc.invalidateQueries({ queryKey: ["ingestion-jobs", engagementId] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Delete failed"),
  });

  const swap = () => {
    setBaseline(current);
    setCurrent(baseline);
  };

  const toggleAll = (rows: DiffRow[], checked: boolean) => {
    const next = new Set(selected);
    if (checked) rows.forEach((r) => next.add(r.finding_id));
    else rows.forEach((r) => next.delete(r.finding_id));
    setSelected(next);
  };

  const renderTable = (
    title: string,
    accent: string,
    rows: DiffRow[],
    withSelection: boolean
  ) => {
    const allChecked = rows.length > 0 && rows.every((r) => selected.has(r.finding_id));
    return (
      <div className="panel overflow-hidden">
        <div className={cn("px-4 py-2.5 border-b border-border-soft flex items-center justify-between", accent)}>
          <h3 className="text-sm font-semibold">
            {title}{" "}
            <span className="text-xs text-fg-muted font-normal">({rows.length})</span>
          </h3>
          {withSelection && rows.length > 0 && (
            <label className="text-xs text-fg-muted flex items-center gap-1.5">
              <input
                type="checkbox"
                className="accent-accent"
                checked={allChecked}
                onChange={(e) => toggleAll(rows, e.target.checked)}
              />
              select all
            </label>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-fg-muted text-xs bg-bg-soft">
              <tr className="text-left">
                {withSelection && <th className="px-3 py-2 w-8"></th>}
                <th className="px-3 py-2">Severity</th>
                <th className="px-3 py-2">Title</th>
                <th className="px-3 py-2">Asset</th>
                <th className="px-3 py-2">Port</th>
                <th className="px-3 py-2">CVE</th>
                <th className="px-3 py-2">Last seen</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const checked = selected.has(r.finding_id);
                return (
                  <tr
                    key={r.finding_id}
                    className={cn(
                      "border-t border-border-soft",
                      checked && "bg-accent/5"
                    )}
                  >
                    {withSelection && (
                      <td className="px-3 py-2">
                        <input
                          type="checkbox"
                          className="accent-accent"
                          checked={checked}
                          onChange={(e) => {
                            const next = new Set(selected);
                            if (e.target.checked) next.add(r.finding_id);
                            else next.delete(r.finding_id);
                            setSelected(next);
                          }}
                        />
                      </td>
                    )}
                    <td className="px-3 py-2">
                      <span className={`chip ${SEVERITY_COLOR[r.severity]}`}>
                        {r.severity}
                      </span>
                    </td>
                    <td className="px-3 py-2 truncate max-w-xs">{r.title}</td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {r.asset_value ?? "—"}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-fg-muted">
                      {r.port ?? "—"}
                    </td>
                    <td className="px-3 py-2 font-mono text-[10px] text-fg-muted">
                      {r.cve_id ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-xs text-fg-muted">
                      {formatDate(r.last_seen)}
                    </td>
                  </tr>
                );
              })}
              {rows.length === 0 && (
                <tr>
                  <td
                    colSpan={withSelection ? 7 : 6}
                    className="text-center text-fg-muted py-6"
                  >
                    None
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <AppleIcon name="check-shield" size={20} className="text-accent" /> Multi-scan compare
          </h1>
          <p className="text-sm text-fg-muted">
            Pick a baseline and a current ingestion job to see what stayed, regressed, or got fixed
          </p>
        </div>
        {selected.size > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-fg-muted">{selected.size} selected</span>
            <button
              onClick={() => bulkDelete.mutate([...selected])}
              disabled={bulkDelete.isPending}
              className="bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/30 rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5 disabled:opacity-50"
            >
              <AppleIcon name="trash" size={14} />
              {bulkDelete.isPending ? "Deleting…" : "Bulk delete new findings"}
            </button>
          </div>
        )}
      </div>

      <div className="panel p-4">
        <div className="grid grid-cols-[1fr_auto_1fr_auto] items-end gap-3">
          <div>
            <label className="text-xs text-fg-muted">Baseline (older)</label>
            <select
              value={baseline}
              onChange={(e) => setBaseline(e.target.value)}
              className="w-full bg-bg-soft border border-border-soft rounded-lg px-2.5 py-1.5 text-sm mt-1 outline-none focus:border-accent"
            >
              <option value="">Select job…</option>
              {(jobs.data ?? []).map((j) => (
                <option key={j.id} value={j.id}>
                  {j.source_filename ?? j.source} · {formatDate(j.finished_at ?? j.started_at)}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={swap}
            disabled={!baseline || !current}
            className="bg-bg-soft border border-border-soft rounded-lg p-2 text-fg-muted hover:text-accent disabled:opacity-40 mb-0.5"
            title="Swap baseline and current"
          >
            <AppleIcon name="arrow-left-right" size={14} />
          </button>
          <div>
            <label className="text-xs text-fg-muted">Current (newer)</label>
            <select
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              className="w-full bg-bg-soft border border-border-soft rounded-lg px-2.5 py-1.5 text-sm mt-1 outline-none focus:border-accent"
            >
              <option value="">Select job…</option>
              {(jobs.data ?? []).map((j) => (
                <option key={j.id} value={j.id}>
                  {j.source_filename ?? j.source} · {formatDate(j.finished_at ?? j.started_at)}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={() => compare.refetch()}
            disabled={!baseline || !current || baseline === current || compare.isFetching}
            className="bg-accent hover:bg-accent-strong text-white rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5 disabled:opacity-50"
          >
            <AppleIcon name="check-shield" size={14} />
            {compare.isFetching ? "Comparing…" : "Run compare"}
          </button>
        </div>
        {baseline && current && baseline === current && (
          <p className="text-xs text-amber-300 mt-2">
            Pick two different jobs to compare.
          </p>
        )}
      </div>

      {compare.data && (
        <div className="grid grid-cols-3 gap-4">
          {renderTable(
            "STILL PRESENT",
            "bg-amber-500/10",
            compare.data.still_present,
            false
          )}
          {renderTable(
            "NEW FINDINGS",
            "bg-rose-500/10",
            compare.data.new_findings,
            true
          )}
          {renderTable(
            "FIXED",
            "bg-emerald-500/10",
            compare.data.fixed,
            false
          )}
        </div>
      )}

      {!compare.data && !compare.isFetching && (
        <div className="panel p-10 text-center text-fg-muted text-sm">
          Select a baseline and a current ingestion job, then run compare.
        </div>
      )}
    </div>
  );
}
