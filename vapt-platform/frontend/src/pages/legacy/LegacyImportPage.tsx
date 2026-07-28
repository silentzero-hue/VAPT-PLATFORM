import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { formatDate } from "../../lib/cn";
import type { Engagement, ImportResult, PreviewResult } from "../../types";
import { Eye, FileInput, CircleHelp, Server } from "lucide-react";

export default function LegacyImportPage() {
  const { wid } = useParams();
  const auth = useAuth();
  const qc = useQueryClient();
  const workspaceId = wid ?? auth.activeWorkspace;

  const [engagementId, setEngagementId] = useState("");
  const [dbPath, setDbPath] = useState("");

  const engs = useQuery({
    queryKey: ["engagements", workspaceId],
    queryFn: async () =>
      (await api.get<Engagement[]>(`/workspaces/${workspaceId}/engagements`)).data,
    enabled: !!workspaceId,
  });

  const preview = useQuery({
    queryKey: ["legacy-preview", workspaceId, dbPath],
    queryFn: async () =>
      (
        await api.get<PreviewResult>(
          `/workspaces/${workspaceId}/legacy/preview?db_path=${encodeURIComponent(dbPath)}`
        )
      ).data,
    enabled: false,
  });

  const importRun = useMutation({
    mutationFn: async () => {
      const body = new URLSearchParams();
      body.set("engagement_id", engagementId);
      body.set("db_path", dbPath);
      return api.post<ImportResult>(`/workspaces/${workspaceId}/legacy/import`, body, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
    },
    onSuccess: (data) => {
      toast.success(`Imported ${data.data.rows} rows`);
      qc.removeQueries({ queryKey: ["legacy-preview", workspaceId, dbPath] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Import failed"),
  });

  return (
    <div className="space-y-4 max-w-3xl mx-auto p-4 min-w-0">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <Server size={20} className="text-finder-blue" /> Legacy importer
          </h1>
          <p className="text-sm text-ink-muted">
            Pull findings from an old <code className="font-mono">vulnerabilities.db</code> SQLite
            file into this engagement
          </p>
        </div>
        <Link
          to={`/workspaces/${workspaceId}/legacy/help`}
          className="bg-paper-soft border border-hairline hover:border-finder-blue rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5"
        >
          <CircleHelp size={14} /> Help
        </Link>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (engagementId && dbPath) importRun.mutate();
        }}
        className="panel p-4 space-y-3"
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-ink-muted">Engagement</label>
            <select
              value={engagementId}
              onChange={(e) => setEngagementId(e.target.value)}
              required
              className="w-full bg-paper-soft border border-hairline rounded-lg px-2.5 py-1.5 text-sm mt-1"
            >
              <option value="">Select…</option>
              {(engs.data ?? []).map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-ink-muted">
              Legacy <code className="font-mono">vulnerabilities.db</code> path
            </label>
            <input
              value={dbPath}
              onChange={(e) => setDbPath(e.target.value)}
              required
              placeholder="/opt/old-vapt/data/vulnerabilities.db"
              className="w-full bg-paper-soft border border-hairline rounded-lg px-2.5 py-1.5 text-sm mt-1 outline-none focus:border-finder-blue font-mono"
            />
          </div>
        </div>
        <div className="flex justify-between items-center pt-1">
          <button
            type="button"
            onClick={() => preview.refetch()}
            disabled={!dbPath || preview.isFetching}
            className="bg-paper-soft border border-hairline hover:border-finder-blue rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5 disabled:opacity-50"
          >
            <Eye size={14} /> {preview.isFetching ? "Previewing…" : "Preview"}
          </button>
          <button
            type="submit"
            disabled={
              !engagementId || !dbPath || importRun.isPending || preview.data?.rows === 0
            }
            className="bg-finder-blue hover:bg-folder-to text-white rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5 disabled:opacity-50"
          >
            <FileInput size={14} /> {importRun.isPending ? "Importing…" : "Import"}
          </button>
        </div>
      </form>

      {preview.data && (
        <div className="panel p-4 space-y-2">
          <h3 className="text-sm font-semibold">Preview</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
            <div>
              <div className="text-xs text-ink-muted">Total rows</div>
              <div className="text-lg font-semibold font-mono">
                {preview.data.rows}
              </div>
            </div>
            <div>
              <div className="text-xs text-ink-muted">DB size</div>
              <div className="font-mono text-ink-muted">
                {preview.data.db_size_bytes != null
                  ? `${(preview.data.db_size_bytes / 1024).toFixed(1)} KB`
                  : "—"}
              </div>
            </div>
            <div>
              <div className="text-xs text-ink-muted">Last modified</div>
              <div className="font-mono text-ink-muted">
                {formatDate(preview.data.db_mtime)}
              </div>
            </div>
          </div>
          {preview.data.first_3.length > 0 && (
            <div>
              <div className="text-xs text-ink-muted mt-2">Sample titles</div>
              <ul className="text-sm space-y-1 mt-1">
                {preview.data.first_3.map((t, i) => (
                  <li
                    key={i}
                    className="border-t border-hairline py-1 truncate"
                  >
                    {t}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {importRun.data && (
        <div className="panel p-4">
          <h3 className="text-sm font-semibold mb-3">Import result</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
            <Stat label="Rows processed" value={importRun.data.data.rows} />
            <Stat
              label="New vulnerabilities"
              value={importRun.data.data.new_vulns}
              accent="text-finder-blue"
            />
            <Stat
              label="New findings"
              value={importRun.data.data.new_findings}
              accent="text-rose-700"
            />
            <Stat
              label="Merged findings"
              value={importRun.data.data.merged_findings}
              accent="text-emerald-700"
            />
            <div className="col-span-2">
              <div className="text-xs text-ink-muted">Imported at</div>
              <div className="font-mono text-ink-muted">
                {formatDate(importRun.data.data.imported_at)}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent?: string;
}) {
  return (
    <div>
      <div className="text-xs text-ink-muted">{label}</div>
      <div className={`text-lg font-semibold font-mono ${accent ?? ""}`}>
        {value}
      </div>
    </div>
  );
}
