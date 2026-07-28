import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import AppleIcon from "../../components/ui/AppleIcon";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { formatDate } from "../../lib/cn";
import type { PortalShare } from "../../types";

export default function PortalSharesPage() {
  const { wid } = useParams();
  const auth = useAuth();
  const workspaceId = wid ?? auth.activeWorkspace;
  const qc = useQueryClient();

  const [reportId, setReportId] = useState("");
  const [label, setLabel] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [maxViews, setMaxViews] = useState("");
  const [requirePassword, setRequirePassword] = useState(false);
  const [password, setPassword] = useState("");
  const [allowedEmails, setAllowedEmails] = useState("");
  const [watermark, setWatermark] = useState(true);
  const [note, setNote] = useState("");
  const [revealed, setRevealed] = useState<{ id: string; url: string } | null>(null);

  const shares = useQuery({
    queryKey: ["portal-shares", workspaceId],
    queryFn: async () =>
      (await api.get<PortalShare[]>(`/workspaces/${workspaceId}/portal-shares`)).data,
    enabled: !!workspaceId,
  });

  const create = useMutation({
    mutationFn: async () =>
      (
        await api.post(`/workspaces/${workspaceId}/portal-shares`, {
          report_id: reportId,
          label: label || null,
          expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
          max_views: maxViews ? Number(maxViews) : null,
          require_password: requirePassword,
          password: requirePassword ? password : null,
          allowed_emails: allowedEmails
            ? allowedEmails
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean)
            : [],
          watermark,
          note: note || null,
        })
      ).data,
    onSuccess: (data) => {
      setRevealed({ id: data.id, url: data.url });
      setReportId("");
      setLabel("");
      setExpiresAt("");
      setMaxViews("");
      setRequirePassword(false);
      setPassword("");
      setAllowedEmails("");
      setNote("");
      qc.invalidateQueries({ queryKey: ["portal-shares", workspaceId] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Failed"),
  });

  const revoke = useMutation({
    mutationFn: async (sid: string) => api.delete(`/portal-shares/${sid}`),
    onSuccess: () => {
      toast.success("Revoked");
      qc.invalidateQueries({ queryKey: ["portal-shares", workspaceId] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Revoke failed"),
  });

  const copy = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied");
  };

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <AppleIcon name="link" size={20} className="text-accent" /> Client portal
          </h1>
          <p className="text-sm text-fg-muted">
            Share signed reports via expiring, view-limited links
          </p>
        </div>
      </div>

      <div className="panel p-4">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-1.5">
          <AppleIcon name="plus" size={14} /> Create share
        </h3>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
          className="grid grid-cols-2 gap-3"
        >
          <div>
            <label className="text-xs text-fg-muted">Report ID</label>
            <input
              value={reportId}
              onChange={(e) => setReportId(e.target.value)}
              required
              placeholder="rpt_…"
              className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm mt-1"
            />
          </div>
          <div>
            <label className="text-xs text-fg-muted">Label</label>
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Acme Q2 report"
              className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm mt-1"
            />
          </div>
          <div>
            <label className="text-xs text-fg-muted">Expires at</label>
            <input
              type="datetime-local"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm mt-1"
            />
          </div>
          <div>
            <label className="text-xs text-fg-muted">Max views (blank = unlimited)</label>
            <input
              type="number"
              min={1}
              value={maxViews}
              onChange={(e) => setMaxViews(e.target.value)}
              className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm mt-1"
            />
          </div>
          <div>
            <label className="flex items-center gap-2 text-xs text-fg-muted">
              <input
                type="checkbox"
                checked={requirePassword}
                onChange={(e) => setRequirePassword(e.target.checked)}
                className="accent-accent"
              />
              Require password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={!requirePassword}
              placeholder={requirePassword ? "Required" : "Optional"}
              className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm mt-1 disabled:opacity-50"
            />
          </div>
          <div>
            <label className="text-xs text-fg-muted">
              Allowed emails (comma-separated, blank = open)
            </label>
            <input
              value={allowedEmails}
              onChange={(e) => setAllowedEmails(e.target.value)}
              placeholder="[email protected], [email protected]"
              className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm mt-1"
            />
          </div>
          <div className="col-span-2">
            <label className="flex items-center gap-2 text-xs text-fg-muted">
              <input
                type="checkbox"
                checked={watermark}
                onChange={(e) => setWatermark(e.target.checked)}
                className="accent-accent"
              />
              Apply viewer email watermark on downloaded PDF
            </label>
          </div>
          <div className="col-span-2">
            <label className="text-xs text-fg-muted">Note (shown to viewer)</label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm mt-1"
            />
          </div>
          <button
            type="submit"
            disabled={create.isPending || !reportId}
            className="col-span-2 bg-accent hover:bg-accent-strong text-white rounded-lg px-3 py-1.5 text-sm disabled:opacity-50"
          >
            {create.isPending ? "Creating…" : "Create share"}
          </button>
        </form>
      </div>

      <div className="panel overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-fg-muted text-xs bg-bg-soft">
            <tr className="text-left">
              <th className="px-3 py-2">Label</th>
              <th className="px-3 py-2">Report</th>
              <th className="px-3 py-2">Views</th>
              <th className="px-3 py-2">Expires</th>
              <th className="px-3 py-2">Last access</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {(shares.data ?? []).map((s) => (
              <tr key={s.id} className="border-t border-border-soft">
                <td className="px-3 py-2 font-medium">{s.label ?? "—"}</td>
                <td className="px-3 py-2 font-mono text-xs text-fg-muted">
                  {s.report_id.slice(0, 12)}…
                </td>
                <td className="px-3 py-2 font-mono text-xs">
                  {s.current_views}
                  {s.max_views != null ? ` / ${s.max_views}` : ""}
                </td>
                <td className="px-3 py-2 text-fg-muted text-xs">
                  {formatDate(s.expires_at)}
                </td>
                <td className="px-3 py-2 text-fg-muted text-xs">
                  {formatDate(s.last_access_at)}
                </td>
                <td className="px-3 py-2">
                  {s.revoked ? (
                    <span className="pill bg-rose-500/15 text-rose-300 border-rose-500/30">
                      revoked
                    </span>
                  ) : (
                    <span className="pill bg-emerald-500/15 text-emerald-300 border-emerald-500/30">
                      active
                    </span>
                  )}
                </td>
                <td className="px-3 py-2">
                  {!s.revoked && (
                    <button
                      onClick={() => revoke.mutate(s.id)}
                      disabled={revoke.isPending}
                      className="text-xs px-2 py-1 bg-rose-500/15 text-rose-300 border border-rose-500/30 rounded hover:bg-rose-500/25"
                    >
                      Revoke
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {(shares.data ?? []).length === 0 && (
              <tr>
                <td colSpan={7} className="text-center text-fg-muted py-8">
                  No shares yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {revealed && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setRevealed(null)}
        >
          <div
            className="panel p-5 w-full max-w-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 mb-3 text-amber-300">
              <AppleIcon name="exclamation-triangle" size={16} />
              <h2 className="text-sm font-semibold">
                Copy this URL now — it will not be shown again
              </h2>
            </div>
            <div className="bg-bg-soft border border-border-soft rounded-lg p-3 flex items-center gap-2">
              <code className="flex-1 font-mono text-xs break-all">{revealed.url}</code>
              <button
                onClick={() => copy(revealed.url)}
                className="bg-accent/15 text-accent border border-accent/30 rounded px-2 py-1 text-xs flex items-center gap-1"
              >
                <AppleIcon name="copy" size={10} /> Copy
              </button>
            </div>
            <p className="text-xs text-fg-muted mt-3">
              Send it to the client through a separate channel. The link can be revoked
              later, but anyone with it can download until then.
            </p>
            <div className="flex justify-end mt-4">
              <button
                onClick={() => setRevealed(null)}
                className="bg-accent hover:bg-accent-strong text-white rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5"
              >
                <AppleIcon name="x-mark" size={14} /> I have saved it
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
