import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import AppleIcon from "../../components/ui/AppleIcon";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { formatDate } from "../../lib/cn";
import type { Engagement, RetestCycle, RetestStatus } from "../../types";

interface RetestSummary {
  still_remediated: number;
  regressed: number;
  new_findings: number;
}

const STATUS_PILL: Record<RetestStatus, string> = {
  scheduled: "bg-bg-soft text-fg-muted border-border-soft",
  in_progress: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  completed: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  cancelled: "bg-rose-500/15 text-rose-300 border-rose-500/30",
};

export default function RetestsPage() {
  const { wid } = useParams();
  const auth = useAuth();
  const workspaceId = wid ?? auth.activeWorkspace;
  const qc = useQueryClient();

  const [title, setTitle] = useState("");
  const [engagementId, setEngagementId] = useState("");
  const [scheduledFor, setScheduledFor] = useState("");
  const [attachModal, setAttachModal] = useState<{ rcId: string; pickEng: string } | null>(null);
  const [summaryOf, setSummaryOf] = useState<Record<string, RetestSummary>>({});

  const engs = useQuery({
    queryKey: ["engagements", workspaceId],
    queryFn: async () =>
      (await api.get<Engagement[]>(`/workspaces/${workspaceId}/engagements`)).data,
    enabled: !!workspaceId,
  });

  const retests = useQuery({
    queryKey: ["retests", workspaceId],
    queryFn: async () =>
      (await api.get<RetestCycle[]>(`/workspaces/${workspaceId}/retests`)).data,
    enabled: !!workspaceId,
  });

  const schedule = useMutation({
    mutationFn: async () =>
      api.post(`/workspaces/${workspaceId}/retests`, {
        engagement_id: engagementId,
        title,
        scheduled_for: new Date(scheduledFor).toISOString(),
      }),
    onSuccess: () => {
      toast.success("Retest scheduled");
      setTitle("");
      setScheduledFor("");
      qc.invalidateQueries({ queryKey: ["retests", workspaceId] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Failed"),
  });

  const attach = useMutation({
    mutationFn: async (vars: { rcId: string; retestEngagementId: string }) =>
      api.post(`/workspaces/${workspaceId}/retests/${vars.rcId}/attach`, {
        retest_engagement_id: vars.retestEngagementId,
      }),
    onSuccess: () => {
      toast.success("Attached");
      setAttachModal(null);
      qc.invalidateQueries({ queryKey: ["retests", workspaceId] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Attach failed"),
  });

  const summarise = useMutation({
    mutationFn: async (rcId: string) =>
      (await api.post(`/workspaces/${workspaceId}/retests/${rcId}/summarise`)).data,
    onSuccess: (data, rcId) => {
      setSummaryOf((s) => ({ ...s, [rcId]: data }));
      qc.invalidateQueries({ queryKey: ["retests", workspaceId] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Summarise failed"),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <AppleIcon name="arrow-uturn-clockwise" size={20} className="text-accent" /> Retests
          </h1>
          <p className="text-sm text-fg-muted">
            Schedule follow-up testing and verify previous remediations hold
          </p>
        </div>
      </div>

      <div className="panel p-4">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-1.5">
          <AppleIcon name="plus" size={14} /> Schedule retest
        </h3>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            schedule.mutate();
          }}
          className="grid grid-cols-4 gap-3 items-end"
        >
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
            <label className="text-xs text-fg-muted">Title</label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              placeholder="Q2 retest — production"
              className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm mt-1"
            />
          </div>
          <div className="col-span-1">
            <label className="text-xs text-fg-muted">Scheduled for</label>
            <input
              type="datetime-local"
              value={scheduledFor}
              onChange={(e) => setScheduledFor(e.target.value)}
              required
              className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm mt-1"
            />
          </div>
          <button
            type="submit"
            disabled={schedule.isPending}
            className="col-span-4 sm:col-span-1 sm:col-start-4 bg-accent hover:bg-accent-strong text-white rounded-lg px-3 py-1.5 text-sm disabled:opacity-50"
          >
            {schedule.isPending ? "Scheduling…" : "Schedule"}
          </button>
        </form>
      </div>

      <div className="panel overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-fg-muted text-xs bg-bg-soft">
            <tr className="text-left">
              <th className="px-3 py-2">Title</th>
              <th className="px-3 py-2">Engagement</th>
              <th className="px-3 py-2">Scheduled</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Summary</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {(retests.data ?? []).map((r) => {
              const eng = (engs.data ?? []).find((e) => e.id === r.engagement_id);
              const attached = (engs.data ?? []).find(
                (e) => e.id === r.retest_engagement_id,
              );
              const sum = summaryOf[r.id];
              return (
                <tr key={r.id} className="border-t border-border-soft">
                  <td className="px-3 py-2 font-medium">{r.title}</td>
                  <td className="px-3 py-2 text-fg-muted">{eng?.name ?? "—"}</td>
                  <td className="px-3 py-2 text-fg-muted">{formatDate(r.scheduled_for)}</td>
                  <td className="px-3 py-2">
                    <span className={`pill ${STATUS_PILL[r.status]}`}>{r.status}</span>
                  </td>
                  <td className="px-3 py-2 text-xs">
                    {sum ? (
                      <span className="flex gap-2 font-mono">
                        <span className="text-emerald-300">✓{sum.still_remediated}</span>
                        <span className="text-rose-300">↻{sum.regressed}</span>
                        <span className="text-amber-300">+{sum.new_findings}</span>
                      </span>
                    ) : (
                      <span className="text-fg-subtle">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex gap-1">
                      <button
                        onClick={() => summarise.mutate(r.id)}
                        disabled={summarise.isPending}
                        className="text-xs px-2 py-1 bg-bg-soft border border-border-soft rounded hover:border-accent flex items-center gap-1"
                      >
                        <AppleIcon name="check" size={10} /> Summarise
                      </button>
                      <button
                        onClick={() =>
                          setAttachModal({ rcId: r.id, pickEng: "" })
                        }
                        className="text-xs px-2 py-1 bg-accent/15 text-accent border border-accent/30 rounded hover:bg-accent/25 flex items-center gap-1"
                      >
                        <AppleIcon name="link" size={10} />
                        {attached ? "Re-attach" : "Attach engagement"}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {(retests.data ?? []).length === 0 && (
              <tr>
                <td colSpan={6} className="text-center text-fg-muted py-8">
                  No retest cycles yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {attachModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setAttachModal(null)}
        >
          <div
            className="panel p-5 w-full max-w-md"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold">Attach retest engagement</h2>
              <button
                onClick={() => setAttachModal(null)}
                className="text-fg-muted hover:text-fg"
              >
                <AppleIcon name="x-mark" size={16} />
              </button>
            </div>
            <p className="text-xs text-fg-muted mb-3">
              Pick the engagement that performed this retest.
            </p>
            <select
              value={attachModal.pickEng}
              onChange={(e) =>
                setAttachModal({ ...attachModal, pickEng: e.target.value })
              }
              className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm"
            >
              <option value="">Select…</option>
              {(engs.data ?? []).map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name}
                </option>
              ))}
            </select>
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => setAttachModal(null)}
                className="bg-bg-soft border border-border-soft rounded-lg px-3 py-1.5 text-sm"
              >
                Cancel
              </button>
              <button
                onClick={() =>
                  attach.mutate({
                    rcId: attachModal.rcId,
                    retestEngagementId: attachModal.pickEng,
                  })
                }
                disabled={!attachModal.pickEng || attach.isPending}
                className="bg-accent hover:bg-accent-strong text-white rounded-lg px-3 py-1.5 text-sm disabled:opacity-50"
              >
                Attach
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
