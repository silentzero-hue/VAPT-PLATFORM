import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router-dom";
import AppleIcon from "../../components/ui/AppleIcon";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { cn, formatDate } from "../../lib/cn";
import type { Report, ReportStatus } from "../../types";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import Toolbar from "../../components/ui/Toolbar";

const STATUS_PILL: Record<string, string> = {
  approved: "pill-success",
  published: "pill-success",
  pending_review: "pill-warning",
  changes_requested: "pill-warning",
  rejected: "pill-danger",
  drafting: "pill-muted",
};

const STATUS_LABEL: Record<string, string> = {
  approved: "Approved",
  published: "Published",
  pending_review: "Pending review",
  changes_requested: "Changes requested",
  rejected: "Rejected",
  drafting: "Drafting",
};

export default function ReportsPage() {
  const { wid } = useParams();
  const auth = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const workspaceId = wid ?? auth.activeWorkspace;
  const reports = useQuery({
    queryKey: ["reports", workspaceId],
    queryFn: async () => (await api.get<Report[]>(`/reports`)).data,
    enabled: !!workspaceId,
  });

  const engs = useQuery({
    queryKey: ["engagements-for-report", workspaceId],
    queryFn: async () => (await api.get<any[]>(`/workspaces/${workspaceId}/engagements`)).data,
    enabled: !!workspaceId,
  });

  const createReport = useMutation({
    mutationFn: async (vars: { engagement_id: string; title?: string }) =>
      (
        await api.post<Report>(`/reports`, {
          engagement_id: vars.engagement_id,
          title: vars.title,
        })
      ).data,
    onSuccess: (r) => {
      toast.success("Report created");
      qc.invalidateQueries({ queryKey: ["reports", workspaceId] });
      navigate(`/workspaces/${workspaceId}/reports/${r.id}`);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Create failed"),
  });

  const [newReportOpen, setNewReportOpen] = useState(false);
  const [newReportEng, setNewReportEng] = useState("");
  const [newReportTitle, setNewReportTitle] = useState("VAPT Report");

  const handleNewReport = () => {
    if (!engs.data?.length) {
      toast.error("Create an engagement first");
      return;
    }
    setNewReportEng(engs.data[0].id);
    setNewReportTitle("VAPT Report");
    setNewReportOpen(true);
  };

  const submitNewReport = () => {
    if (!newReportEng) return;
    createReport.mutate({
      engagement_id: newReportEng,
      title: newReportTitle.trim() || undefined,
    });
    setNewReportOpen(false);
  };

  const downloadReport = useMutation({
    mutationFn: async (rid: string) => {
      const res = await api.get(`/reports/${rid}/download`, { responseType: "blob" });
      const blob = new Blob([res.data], {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `report-${rid}.docx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },
    onSuccess: () => toast.success("Report downloaded"),
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Download failed"),
  });

  const approveReport = useMutation({
    mutationFn: async (rid: string) =>
      (await api.post<Report>(`/reports/${rid}/approve`, { note: "Approved from reports list" })).data,
    onSuccess: () => {
      toast.success("Report approved & locked");
      qc.invalidateQueries({ queryKey: ["reports", workspaceId] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Approval failed"),
  });

  return (
    <div className="space-y-4 max-w-[1400px] mx-auto">
      <Toolbar
        left={
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Reports</h1>
            <p className="text-sm text-ink-muted">
              Drafts, in-review, and approved reports.
            </p>
          </div>
        }
        right={
          <button
            onClick={handleNewReport}
            disabled={createReport.isPending}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-sm",
              "bg-finder-blue text-white hover:bg-folder-to",
              "transition-all duration-200 ease-out active:scale-[0.98]",
              "disabled:opacity-50"
            )}
          >
            <AppleIcon name="plus" size={14} /> New report
          </button>
        }
      />

      {(reports.data ?? []).length === 0 ? (
        <Card>
          <EmptyState
            iconName="doc"
            title="No reports yet"
            description="Reports generated from your engagements will appear here."
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {(reports.data ?? []).map((r) => (
            <Card
              key={r.id}
              onClick={() => navigate(`/workspaces/${workspaceId}/reports/${r.id}`)}
              className="card-hover p-5"
              ariaLabel={`Open report ${r.title}`}
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="h-9 w-9 rounded-lg bg-finder-blue-soft border border-finder-blue/20 flex items-center justify-center shrink-0">
                  <AppleIcon name="doc" size={16} className="text-finder-blue" />
                </div>
                <span className={cn("pill shrink-0", STATUS_PILL[r.status] ?? "pill-muted")}>
                  {STATUS_LABEL[r.status] ?? r.status}
                </span>
              </div>
              <div className="text-base font-semibold leading-snug line-clamp-2">{r.title}</div>
              {r.engagement_id && (
                <div className="text-[10px] font-mono text-ink-muted mt-1 truncate">
                  {r.engagement_id}
                </div>
              )}

              <div className="mt-4 flex items-center gap-3 text-[11px] text-ink-muted">
                <span>
                  <span className="font-mono text-ink">{r.versions?.length ?? 0}</span> version
                  {(r.versions?.length ?? 0) === 1 ? "" : "s"}
                </span>
                {r.signed_sha256 ? (
                  <span className="inline-flex items-center gap-1 text-emerald-700">
                    <AppleIcon name="shield-check" size={12} /> Signed
                  </span>
                ) : (
                  <span className="text-ink-subtle">Unsigned</span>
                )}
              </div>

              <div className="mt-3 text-[10px] text-ink-subtle font-mono">
                Updated {formatDate(r.updated_at)}
              </div>

              <div className="mt-4 flex items-center gap-2">
                {r.signed_sha256 ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      downloadReport.mutate(r.id);
                    }}
                    disabled={downloadReport.isPending}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs",
                      "bg-finder-blue text-white hover:bg-folder-to",
                      "transition-all duration-200 ease-out active:scale-[0.98]",
                      "disabled:opacity-50"
                    )}
                  >
                    <AppleIcon name="download" size={12} /> Download
                  </button>
                ) : r.status === "pending_review" ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      approveReport.mutate(r.id);
                    }}
                    disabled={approveReport.isPending}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs",
                      "pill-success hover:brightness-125",
                      "transition-all duration-200 ease-out",
                      "disabled:opacity-50"
                    )}
                  >
                    <AppleIcon name="circle-check" size={12} /> Approve & Lock
                  </button>
                ) : (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(`/workspaces/${workspaceId}/reports/${r.id}`);
                    }}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs",
                      "bg-paper-soft border border-hairline-strong hover:border-finder-blue/40",
                      "transition-colors duration-200 ease-out"
                    )}
                  >
                    Open
                  </button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {newReportOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setNewReportOpen(false)}
        >
          <div
            className="panel p-5 w-full max-w-md"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold">New report</h2>
              <button
                onClick={() => setNewReportOpen(false)}
                className="text-ink-muted hover:text-ink"
              >
                <AppleIcon name="x-mark" size={16} />
              </button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-ink-muted">Engagement</label>
                <select
                  value={newReportEng}
                  onChange={(e) => setNewReportEng(e.target.value)}
                  className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-sm mt-1"
                >
                  {(engs.data ?? []).map((e: any) => (
                    <option key={e.id} value={e.id}>
                      {e.name} {e.code ? `(${e.code})` : ""}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-ink-muted">Title (optional)</label>
                <input
                  value={newReportTitle}
                  onChange={(e) => setNewReportTitle(e.target.value)}
                  placeholder="VAPT Report"
                  className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-sm mt-1"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => setNewReportOpen(false)}
                className="bg-paper-soft border border-hairline rounded-lg px-3 py-1.5 text-sm"
              >
                Cancel
              </button>
              <button
                onClick={submitNewReport}
                disabled={!newReportEng || createReport.isPending}
                className="bg-finder-blue hover:bg-folder-to text-white rounded-lg px-3 py-1.5 text-sm disabled:opacity-50"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
