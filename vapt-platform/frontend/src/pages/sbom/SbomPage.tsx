import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import AppleIcon from "../../components/ui/AppleIcon";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import type { Engagement, SbomResult } from "../../types";

export default function SbomPage() {
  const { wid } = useParams();
  const auth = useAuth();
  const workspaceId = wid ?? auth.activeWorkspace;

  const [engagementId, setEngagementId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<SbomResult | null>(null);

  const engs = useQuery({
    queryKey: ["engagements", workspaceId],
    queryFn: async () =>
      (await api.get<Engagement[]>(`/workspaces/${workspaceId}/engagements`)).data,
    enabled: !!workspaceId,
  });

  const upload = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error("Pick a file first");
      const fd = new FormData();
      fd.append("engagement_id", engagementId);
      fd.append("file", file);
      return (
        await api.post<SbomResult>(`/ingestion/sbom/upload`, fd, {
          headers: { "Content-Type": "multipart/form-data" },
        })
      ).data;
    },
    onSuccess: (data) => {
      toast.success(`Parsed ${data.components.length} components`);
      setResult(data);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Upload failed"),
  });

  return (
    <div className="space-y-4 max-w-4xl">
      <div>
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <AppleIcon name="package" size={20} className="text-accent" /> SBOM ingestion
        </h1>
        <p className="text-sm text-fg-muted">
          Upload a CycloneDX or SPDX JSON to attach components and known CVEs to an engagement
        </p>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          upload.mutate();
        }}
        className="panel p-4 space-y-3"
      >
        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-1">
            <label className="text-xs text-fg-muted">Engagement</label>
            <select
              value={engagementId}
              onChange={(e) => setEngagementId(e.target.value)}
              required
              className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm mt-1"
            >
              <option value="">Select…</option>
              {(engs.data ?? []).map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name}
                </option>
              ))}
            </select>
          </div>
          <div className="col-span-2">
            <label className="text-xs text-fg-muted">SBOM file (.cdx.json or .spdx.json)</label>
            <input
              type="file"
              accept=".json,.cdx.json,.spdx.json,application/json"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              required
              className="block w-full mt-1 text-sm file:mr-3 file:bg-accent/15 file:text-accent file:border file:border-accent/30 file:rounded-lg file:px-3 file:py-1.5 file:text-sm file:cursor-pointer bg-bg-soft border border-border-soft rounded-lg"
            />
            {file && (
              <div className="text-xs text-fg-muted mt-1 font-mono">
                {file.name} · {(file.size / 1024).toFixed(1)} KB
              </div>
            )}
          </div>
        </div>
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={upload.isPending || !file || !engagementId}
            className="bg-accent hover:bg-accent-strong text-white rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5 disabled:opacity-50"
          >
            <AppleIcon name="upload" size={14} /> {upload.isPending ? "Uploading…" : "Upload & parse"}
          </button>
        </div>
      </form>

      {result && (
        <div className="panel p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold">
              Parsed components ({result.format})
            </h3>
            <div className="text-xs text-fg-muted">
              {result.stats.total} components ·{" "}
              <span className="text-rose-300">{result.stats.with_vulns} with CVEs</span>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-fg-muted text-xs bg-bg-soft">
                <tr className="text-left">
                  <th className="px-2 py-2">Name</th>
                  <th className="px-2 py-2">Version</th>
                  <th className="px-2 py-2">PURL</th>
                  <th className="px-2 py-2">Licenses</th>
                  <th className="px-2 py-2">CVEs</th>
                </tr>
              </thead>
              <tbody>
                {result.components.map((c, i) => (
                  <tr key={i} className="border-t border-border-soft">
                    <td className="px-2 py-2 font-medium">{c.name}</td>
                    <td className="px-2 py-2 font-mono text-xs text-fg-muted">
                      {c.version ?? "—"}
                    </td>
                    <td className="px-2 py-2 font-mono text-xs text-fg-muted truncate max-w-xs">
                      {c.purl ?? "—"}
                    </td>
                    <td className="px-2 py-2">
                      <div className="flex flex-wrap gap-1">
                        {c.licenses.map((l) => (
                          <span key={l} className="chip chip-muted font-mono text-[10px]">
                            {l}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-2 py-2 font-mono text-xs">
                      {c.vulnerabilities > 0 ? (
                        <span className="text-rose-300">{c.vulnerabilities}</span>
                      ) : (
                        <span className="text-fg-subtle">0</span>
                      )}
                    </td>
                  </tr>
                ))}
                {result.components.length === 0 && (
                  <tr>
                    <td colSpan={5} className="text-center text-fg-muted py-6">
                      No components in this SBOM
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
