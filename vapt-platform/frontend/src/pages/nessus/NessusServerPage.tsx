import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { cn, formatDate } from "../../lib/cn";
import type { Engagement, NessusScan, NessusServer } from "../../types";
import { RotateCw, Plug, Save, Upload } from "lucide-react";

const EMPTY_FORM = {
  name: "",
  base_url: "",
  access_key: "",
  secret_key: "",
  verify_ssl: true,
  request_timeout: 30,
  max_concurrency: 4,
  only_completed_scans: true,
};

export default function NessusServerPage() {
  const { wid } = useParams();
  const auth = useAuth();
  const workspaceId = wid ?? auth.activeWorkspace;
  const qc = useQueryClient();

  const [form, setForm] = useState(EMPTY_FORM);
  const [importFor, setImportFor] = useState<{ scanId: string; engagementId: string } | null>(null);

  const server = useQuery({
    queryKey: ["nessus-server", workspaceId],
    queryFn: async () => {
      try {
        return (await api.get<NessusServer>(`/workspaces/${workspaceId}/nessus/server`)).data;
      } catch (e: any) {
        if (e?.response?.status === 404) return null;
        throw e;
      }
    },
    enabled: !!workspaceId,
  });

  useEffect(() => {
    if (server.data) {
      setForm({
        name: server.data.name ?? "",
        base_url: server.data.base_url ?? "",
        access_key: server.data.access_key ?? "",
        secret_key: server.data.secret_key ?? "",
        verify_ssl: server.data.verify_ssl ?? true,
        request_timeout: server.data.request_timeout ?? 30,
        max_concurrency: server.data.max_concurrency ?? 4,
        only_completed_scans: server.data.only_completed_scans ?? true,
      });
    }
  }, [server.data]);

  const scans = useQuery({
    queryKey: ["nessus-scans", workspaceId],
    queryFn: async () =>
      (await api.get<NessusScan[]>(`/workspaces/${workspaceId}/nessus/scans`)).data,
    enabled: !!workspaceId,
  });

  const engs = useQuery({
    queryKey: ["engagements", workspaceId],
    queryFn: async () =>
      (await api.get<Engagement[]>(`/workspaces/${workspaceId}/engagements`)).data,
    enabled: !!workspaceId,
  });

  const savePut = useMutation({
    mutationFn: async () =>
      api.put(`/workspaces/${workspaceId}/nessus/server`, form),
    onSuccess: () => {
      toast.success("Server saved");
      qc.invalidateQueries({ queryKey: ["nessus-server", workspaceId] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Save failed"),
  });

  const savePatch = useMutation({
    mutationFn: async () =>
      api.patch(`/workspaces/${workspaceId}/nessus/server`, form),
    onSuccess: () => {
      toast.success("Server updated");
      qc.invalidateQueries({ queryKey: ["nessus-server", workspaceId] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Update failed"),
  });

  const syncNow = useMutation({
    mutationFn: async () =>
      api.post(`/workspaces/${workspaceId}/nessus/sync`),
    onSuccess: () => {
      toast.success("Sync complete");
      qc.invalidateQueries({ queryKey: ["nessus-scans", workspaceId] });
      qc.invalidateQueries({ queryKey: ["nessus-server", workspaceId] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Sync failed"),
  });

  const importScan = useMutation({
    mutationFn: async (vars: { scanId: string; engagementId: string }) =>
      api.post(
        `/workspaces/${workspaceId}/nessus/ingest/${vars.scanId}?engagement_id=${vars.engagementId}`
      ),
    onSuccess: () => {
      toast.success("Imported to engagement");
      qc.invalidateQueries({ queryKey: ["nessus-scans", workspaceId] });
      setImportFor(null);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Import failed"),
  });

  return (
    <div className="space-y-4 max-w-[1400px] mx-auto p-4 min-w-0">
      <div className="flex items-end justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <Plug size={20} className="text-finder-blue" /> Nessus server
          </h1>
          <p className="text-sm text-ink-muted">
            Configure a Tenable Nessus instance and import its scans as findings
          </p>
        </div>
        <button
          onClick={() => syncNow.mutate()}
          disabled={syncNow.isPending || !server.data}
          className="bg-finder-blue hover:bg-folder-to text-white rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5 disabled:opacity-50"
        >
          <RotateCw size={14} />
          {syncNow.isPending ? "Syncing…" : "Sync now"}
        </button>
      </div>

      <div className="panel p-4 space-y-3">
        <h3 className="text-sm font-semibold">Connection</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 min-w-0">
          <div>
            <label className="text-xs text-ink-muted">Name</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full bg-paper-soft border border-hairline rounded-lg px-2.5 py-1.5 text-sm mt-1 outline-none focus:border-finder-blue"
            />
          </div>
          <div>
            <label className="text-xs text-ink-muted">Base URL</label>
            <input
              value={form.base_url}
              onChange={(e) => setForm({ ...form, base_url: e.target.value })}
              placeholder="https://nessus.example.com:8834"
              className="w-full bg-paper-soft border border-hairline rounded-lg px-2.5 py-1.5 text-sm mt-1 outline-none focus:border-finder-blue font-mono"
            />
          </div>
          <div>
            <label className="text-xs text-ink-muted">Access key</label>
            <input
              value={form.access_key}
              onChange={(e) => setForm({ ...form, access_key: e.target.value })}
              className="w-full bg-paper-soft border border-hairline rounded-lg px-2.5 py-1.5 text-sm mt-1 outline-none focus:border-finder-blue font-mono"
            />
          </div>
          <div>
            <label className="text-xs text-ink-muted">Secret key</label>
            <input
              type="password"
              value={form.secret_key ?? ""}
              onChange={(e) => setForm({ ...form, secret_key: e.target.value })}
              className="w-full bg-paper-soft border border-hairline rounded-lg px-2.5 py-1.5 text-sm mt-1 outline-none focus:border-finder-blue font-mono"
            />
          </div>
          <div>
            <label className="text-xs text-ink-muted">Request timeout (s)</label>
            <input
              type="number"
              min={1}
              value={form.request_timeout}
              onChange={(e) =>
                setForm({ ...form, request_timeout: Number(e.target.value) })
              }
              className="w-full bg-paper-soft border border-hairline rounded-lg px-2.5 py-1.5 text-sm mt-1 outline-none focus:border-finder-blue"
            />
          </div>
          <div>
            <label className="text-xs text-ink-muted">Max concurrency</label>
            <input
              type="number"
              min={1}
              value={form.max_concurrency}
              onChange={(e) =>
                setForm({ ...form, max_concurrency: Number(e.target.value) })
              }
              className="w-full bg-paper-soft border border-hairline rounded-lg px-2.5 py-1.5 text-sm mt-1 outline-none focus:border-finder-blue"
            />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-4 pt-1">
          <label className="flex items-center gap-2 text-sm text-ink-muted">
            <input
              type="checkbox"
              className="accent-accent"
              checked={form.verify_ssl}
              onChange={(e) => setForm({ ...form, verify_ssl: e.target.checked })}
            />
            Verify SSL
          </label>
          <label className="flex items-center gap-2 text-sm text-ink-muted">
            <input
              type="checkbox"
              className="accent-accent"
              checked={form.only_completed_scans}
              onChange={(e) =>
                setForm({ ...form, only_completed_scans: e.target.checked })
              }
            />
            Only import completed scans
          </label>
        </div>
        <div className="flex justify-end gap-2 pt-2 border-t border-hairline">
          {server.data ? (
            <button
              onClick={() => savePatch.mutate()}
              disabled={savePatch.isPending}
              className="bg-paper-soft border border-hairline hover:border-finder-blue rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5 disabled:opacity-50"
            >
              <Save size={14} /> {savePatch.isPending ? "Updating…" : "Update"}
            </button>
          ) : (
            <button
              onClick={() => savePut.mutate()}
              disabled={savePut.isPending}
              className="bg-finder-blue hover:bg-folder-to text-white rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5 disabled:opacity-50"
            >
              <Save size={14} /> {savePut.isPending ? "Saving…" : "Save server"}
            </button>
          )}
        </div>
      </div>

      <div className="panel p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold">Sync status</h3>
          <button
            onClick={() => server.refetch()}
            className="text-xs text-ink-muted hover:text-finder-blue flex items-center gap-1"
          >
            <RotateCw size={12} /> Refresh
          </button>
        </div>
        {server.data ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm min-w-0">
            <div>
              <div className="text-xs text-ink-muted">Last sync</div>
              <div className="font-mono">{formatDate(server.data.last_sync_at)}</div>
            </div>
            <div>
              <div className="text-xs text-ink-muted">Status</div>
              <div>
                <span
                  className={cn(
                    "pill",
                    server.data.last_sync_status === "ok"
                      ? "bg-sev-low-soft text-sev-low-strong border-sev-low"
                      : server.data.last_sync_status === "error"
                      ? "bg-sev-critical-soft text-sev-critical-strong border-sev-critical"
                      : "bg-paper-soft text-ink-muted border-hairline"
                  )}
                >
                  {server.data.last_sync_status ?? "never"}
                </span>
              </div>
            </div>
            <div className="col-span-1">
              <div className="text-xs text-ink-muted">Message</div>
              <div className="text-ink-muted truncate">
                {server.data.last_sync_message ?? "—"}
              </div>
            </div>
          </div>
        ) : (
          <p className="text-sm text-ink-muted">No server configured yet.</p>
        )}
      </div>

      <div className="panel overflow-hidden">
        <div className="px-4 py-3 border-b border-hairline flex items-center justify-between">
          <h3 className="text-sm font-semibold">Cached scans</h3>
          <span className="text-xs text-ink-muted">{(scans.data ?? []).length} total</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-ink-muted text-xs bg-paper-soft">
              <tr className="text-left">
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Policy</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Target</th>
                <th className="px-3 py-2">Completed</th>
                <th className="px-3 py-2 text-right">Action</th>
              </tr>
            </thead>
            <tbody>
              {(scans.data ?? []).map((s) => {
                const imported = !!s.imported_engagement_id;
                return (
                  <tr
                    key={s.id}
                    className="border-t border-hairline hover:bg-paper-soft/40"
                  >
                    <td className="px-3 py-2 font-medium truncate max-w-xs">{s.name}</td>
                    <td className="px-3 py-2">
                      <span
                        className={cn(
                          "pill",
                          s.status === "completed"
                            ? "bg-sev-low-soft text-sev-low-strong border-sev-low"
                            : s.status === "running"
                            ? "bg-sev-medium-soft text-sev-medium-strong border-sev-medium"
                            : "bg-paper-soft text-ink-muted border-hairline"
                        )}
                      >
                        {s.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-ink-muted font-mono text-xs">
                      {s.policy ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-ink-muted">{s.scan_type ?? "—"}</td>
                    <td className="px-3 py-2 text-ink-muted font-mono text-xs truncate max-w-[16rem]">
                      {s.target ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-ink-muted text-xs">
                      {formatDate(s.completed_at)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      {imported ? (
                        <span className="pill bg-sev-low-soft text-sev-low-strong border-sev-low">
                          imported
                        </span>
                      ) : (
                        <button
                          onClick={() =>
                            setImportFor({
                              scanId: s.id,
                              engagementId: engs.data?.[0]?.id ?? "",
                            })
                          }
                          className="bg-finder-blue-soft hover:bg-finder-blue/25 text-finder-blue border border-finder-blue/30 rounded-lg px-2 py-1 text-xs flex items-center gap-1 ml-auto"
                        >
                          <Upload size={10} /> Import
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
              {(scans.data ?? []).length === 0 && (
                <tr>
                  <td colSpan={7} className="text-center text-ink-muted py-8">
                    No scans yet — run “Sync now” to fetch the latest list
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {importFor && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setImportFor(null)}
        >
          <div
            className="panel p-5 max-w-md w-full space-y-3"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-sm font-semibold">Import scan to engagement</h2>
            <select
              value={importFor.engagementId}
              onChange={(e) =>
                setImportFor({ ...importFor, engagementId: e.target.value })
              }
              className="w-full bg-paper-soft border border-hairline rounded-lg px-2.5 py-1.5 text-sm"
            >
              <option value="">Select engagement…</option>
              {(engs.data ?? []).map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name}
                </option>
              ))}
            </select>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setImportFor(null)}
                className="bg-paper-soft border border-hairline rounded-lg px-3 py-1.5 text-sm"
              >
                Cancel
              </button>
              <button
                onClick={() =>
                  importFor.engagementId &&
                  importScan.mutate({
                    scanId: importFor.scanId,
                    engagementId: importFor.engagementId,
                  })
                }
                disabled={!importFor.engagementId || importScan.isPending}
                className="bg-finder-blue hover:bg-folder-to text-white rounded-lg px-3 py-1.5 text-sm disabled:opacity-50"
              >
                {importScan.isPending ? "Importing…" : "Import"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
