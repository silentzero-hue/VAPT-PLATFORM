import { useParams, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import AppleIcon from "../../components/ui/AppleIcon";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { formatDate } from "../../lib/cn";
import type { Report } from "../../types";

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
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{d.title}</h1>
          <p className="text-sm text-ink-muted">
            <span className={`pill ${d.status === "approved" ? "bg-emerald-50 text-emerald-700 border-emerald-500/30" : d.status === "pending_review" ? "bg-amber-50 text-amber-700 border-amber-500/30" : "bg-paper-soft text-ink-muted border-hairline"}`}>
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
              <AppleIcon name="file-down" size={14} /> Download
            </a>
          ) : d.status === "pending_review" ? (
            <>
              <button
                onClick={() => navigate(`/workspaces/${wid}/reports/${d.id}/edit`)}
                className="bg-paper-soft border border-hairline hover:border-finder-blue rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5"
              >
                <AppleIcon name="edit" size={14} /> Edit
              </button>
              <button
                onClick={() => approve.mutate()}
                className="bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-500/30 rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5"
              >
                <AppleIcon name="check" size={14} /> Approve & Lock
              </button>
              <button
                onClick={() => requestChanges.mutate()}
                className="bg-paper-soft border border-hairline hover:border-finder-blue rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5"
              >
                <AppleIcon name="x-mark" size={14} /> Request changes
              </button>
            </>
          ) : d.status === "changes_requested" || d.status === "drafting" ? (
            <>
              <button
                onClick={() => navigate(`/workspaces/${wid}/reports/${d.id}/edit`)}
                className="bg-finder-blue-soft hover:bg-finder-blue/25 text-finder-blue border border-finder-blue/30 rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5"
              >
                <AppleIcon name="edit" size={14} /> Edit
              </button>
              <button
                onClick={() => render.mutate()}
                className="bg-finder-blue hover:bg-folder-to text-white rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5"
              >
                <AppleIcon name="sparkles" size={14} /> Render
              </button>
            </>
          ) : (
            <button
              onClick={() => render.mutate()}
              className="bg-finder-blue-soft hover:bg-finder-blue/25 text-finder-blue border border-finder-blue/30 rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5"
            >
              <AppleIcon name="sparkles" size={14} /> Render draft via agent
            </button>
          )}
        </div>
      </div>

      {d.locked && (
        <div className="panel p-3 bg-emerald-500/5 border-emerald-500/30 flex items-center gap-2 text-sm text-emerald-700">
          <AppleIcon name="lock" size={14} /> Locked at {formatDate(d.locked_at)} — content is signed and immutable
        </div>
      )}

      <div className="grid grid-cols-3 gap-4">
        <div className="panel p-4 col-span-2">
          <h3 className="text-sm font-semibold mb-3">Version history</h3>
          <ol className="space-y-2">
            {(d.versions ?? []).map((v) => (
              <li key={v.id} className="border border-hairline rounded-lg p-3 flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium">v{v.version_no}</div>
                  <div className="text-xs text-ink-muted">{v.note ?? "—"}</div>
                  <div className="text-xs text-ink-muted mt-1">SHA {v.sha256?.slice(0, 16)}… · {formatDate(v.created_at)}</div>
                </div>
                <span className={`pill ${v.status === "approved" ? "bg-emerald-50 text-emerald-700 border-emerald-500/30" : v.status === "pending_review" ? "bg-amber-50 text-amber-700 border-amber-500/30" : "bg-paper-soft text-ink-muted border-hairline"}`}>
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
