import { useParams, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { formatDate } from "../../lib/cn";
import type { Report } from "../../types";
import { Check, Pencil, FileDown, Lock, Sparkles, X } from "lucide-react";

export default function ReportDetailPage() {
  const { rid, wid } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const r = useQuery({
    queryKey: ["report", rid],
    queryFn: async () => (await api.get<Report>(`/reports/${rid}`)).data,
    enabled: !!rid,
    refetchInterval: 5_000,
  });

  const render = useMutation({
    mutationFn: async () => api.post(`/reports/${rid}/render`, {}),
    onSuccess: () => {
      toast.success("Draft rendered, awaiting human review");
      qc.invalidateQueries({ queryKey: ["report", rid] });
    },
  });
  const approve = useMutation({
    mutationFn: async () => api.post(`/reports/${rid}/approve`, {}),
    onSuccess: () => {
      toast.success("Approved & signed");
      qc.invalidateQueries({ queryKey: ["report", rid] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Forbidden"),
  });
  const requestChanges = useMutation({
    mutationFn: async () => api.post(`/reports/${rid}/request-changes`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["report", rid] }),
  });

  if (!r.data) return <div className="text-ink-muted">Loading…</div>;
  const d = r.data;
  const lastV = d.versions?.[d.versions.length - 1];

  return (
    <div className="space-y-4 max-w-[1400px] mx-auto p-4 min-w-0">
      <div className="flex items-end justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold">{d.title}</h1>
          <p className="text-sm text-ink-muted">
            <span className={`pill ${d.status === "approved" ? "bg-sev-low-soft text-sev-low-strong border-sev-low" : d.status === "pending_review" ? "bg-sev-medium-soft text-sev-medium-strong border-sev-medium" : "bg-paper-soft text-ink-muted border-hairline"}`}>
              {d.status}
            </span>
            {d.signed_sha256 && <span className="ml-2 font-mono text-xs text-ink-muted">SHA256 {d.signed_sha256.slice(0, 16)}…</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {d.status === "approved" ? (
            <a
              href={`/api/v1/reports/${d.id}/download`}
              className="bg-finder-blue hover:bg-folder-to text-white rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5"
            >
              <FileDown size={14} /> Download
            </a>
          ) : d.status === "pending_review" ? (
            <>
              <button
                onClick={() => navigate(`/workspaces/${wid}/reports/${d.id}/edit`)}
                className="bg-paper-soft border border-hairline hover:border-finder-blue rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5"
              >
                <Pencil size={14} /> Edit
              </button>
              <button
                onClick={() => approve.mutate()}
                className="bg-sev-low-soft hover:bg-sev-low/15 text-sev-low-strong border border-sev-low rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5"
              >
                <Check size={14} /> Approve & Lock
              </button>
              <button
                onClick={() => requestChanges.mutate()}
                className="bg-paper-soft border border-hairline hover:border-finder-blue rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5"
              >
                <X size={14} /> Request changes
              </button>
            </>
          ) : d.status === "changes_requested" || d.status === "drafting" ? (
            <>
              <button
                onClick={() => navigate(`/workspaces/${wid}/reports/${d.id}/edit`)}
                className="bg-finder-blue-soft hover:bg-finder-blue/25 text-finder-blue border border-finder-blue/30 rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5"
              >
                <Pencil size={14} /> Edit
              </button>
              <button
                onClick={() => render.mutate()}
                className="bg-finder-blue hover:bg-folder-to text-white rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5"
              >
                <Sparkles size={14} /> Render
              </button>
            </>
          ) : (
            <button
              onClick={() => render.mutate()}
              className="bg-finder-blue-soft hover:bg-finder-blue/25 text-finder-blue border border-finder-blue/30 rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5"
            >
              <Sparkles size={14} /> Render draft via agent
            </button>
          )}
        </div>
      </div>

      {d.locked && (
        <div className="panel p-3 bg-sev-low-soft border-sev-low flex items-center gap-2 text-sm text-sev-low-strong">
          <Lock size={14} /> Locked at {formatDate(d.locked_at)} — content is signed and immutable
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 min-w-0">
        <div className="panel p-4 md:col-span-2 min-w-0">
          <h3 className="text-sm font-semibold mb-3">Version history</h3>
          <ol className="space-y-2">
            {(d.versions ?? []).map((v) => (
              <li key={v.id} className="border border-hairline rounded-lg p-3 flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium">v{v.version_no}</div>
                  <div className="text-xs text-ink-muted">{v.note ?? "—"}</div>
                  <div className="text-xs text-ink-muted mt-1">SHA {v.sha256?.slice(0, 16)}… · {formatDate(v.created_at)}</div>
                </div>
                <span className={`pill ${v.status === "approved" ? "bg-sev-low-soft text-sev-low-strong border-sev-low" : v.status === "pending_review" ? "bg-sev-medium-soft text-sev-medium-strong border-sev-medium" : "bg-paper-soft text-ink-muted border-hairline"}`}>
                  {v.status}
                </span>
              </li>
            ))}
            {(d.versions ?? []).length === 0 && (
              <li className="text-center text-ink-muted py-6">No versions yet</li>
            )}
          </ol>
        </div>
        <div className="panel p-4">
          <h3 className="text-sm font-semibold mb-2">Metadata</h3>
          <dl className="text-xs space-y-1">
            <div className="flex justify-between"><dt className="text-ink-muted">Created</dt><dd>{formatDate(d.created_at)}</dd></div>
            <div className="flex justify-between"><dt className="text-ink-muted">Updated</dt><dd>{formatDate(d.updated_at)}</dd></div>
            <div className="flex justify-between"><dt className="text-ink-muted">Current version</dt><dd>{d.current_version_id ? "set" : "—"}</dd></div>
            <div className="flex justify-between"><dt className="text-ink-muted">Signed by</dt><dd>{d.signed_by ?? "—"}</dd></div>
          </dl>
        </div>
      </div>
    </div>
  );
}
