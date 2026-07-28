import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { Download, Mail, Lock, Shield, ShieldOff } from "lucide-react";

interface PortalMeta {
  label: string | null;
  note: string | null;
  filename: string | null;
  require_password: boolean;
  allowed_emails: string[];
  watermark: boolean;
  expires_at: string | null;
  max_views: number | null;
  current_views: number;
}

export default function PortalLanding() {
  const { token } = useParams();
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");

  const meta = useQuery({
    queryKey: ["portal", token],
    queryFn: async () => (await api.get<PortalMeta>(`/portal/${token}`)).data,
    enabled: !!token,
    retry: false,
  });

  const download = useMutation({
    mutationFn: async () => {
      const fd = new FormData();
      if (password) fd.append("password", password);
      if (email) fd.append("email", email);
      const res = await api.post(`/portal/${token}/download`, fd, {
        responseType: "blob",
      });
      const blob = new Blob([res.data]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = meta.data?.filename ?? "report.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },
    onError: (e: any) => {
      const detail = e?.response?.data?.detail;
      if (e?.response?.data instanceof Blob) {
        e.response.data.text().then((t: string) => {
          try {
            const j = JSON.parse(t);
            toast.error(j.detail ?? "Download failed");
          } catch {
            toast.error("Download failed");
          }
        });
      } else {
        toast.error(detail ?? "Download failed");
      }
    },
    onSuccess: () => toast.success("Download started"),
  });

  if (meta.isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-ink-muted">
        Loading…
      </div>
    );
  }

  if (meta.isError || !meta.data) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="panel p-7 max-w-sm w-full text-center space-y-3">
          <ShieldOff size={28} className="text-rose-700 mx-auto" />
          <h1 className="text-lg font-semibold">Share unavailable</h1>
          <p className="text-sm text-ink-muted">
            This link is invalid, has expired, or been revoked.
          </p>
        </div>
      </div>
    );
  }

  const m = meta.data;
  const needsPassword = !!m.require_password;
  const needsEmail = Array.isArray(m.allowed_emails) && m.allowed_emails.length > 0;
  const expired =
    m.expires_at && new Date(m.expires_at).getTime() < Date.now();
  const exhausted = m.max_views != null && m.current_views >= m.max_views;

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-paper">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          download.mutate();
        }}
        className="panel p-7 w-full max-w-md space-y-4"
      >
        <div className="flex items-center gap-2">
          <div className="h-9 w-9 rounded-lg bg-finder-blue-soft border border-finder-blue/30 flex items-center justify-center">
            <Shield size={18} className="text-finder-blue" />
          </div>
          <div>
            <div className="font-semibold">{m.label ?? "Confidential report"}</div>
            <div className="text-xs text-ink-muted">Shared via VAPT platform</div>
          </div>
        </div>

        {m.note && (
          <p className="text-sm text-ink-muted whitespace-pre-wrap">{m.note}</p>
        )}

        {(expired || exhausted) && (
          <div className="text-xs text-rose-700 bg-rose-500/10 border border-rose-500/30 rounded-lg p-2">
            {expired ? "This share has expired." : "View limit reached."}
          </div>
        )}

        {!expired && !exhausted && (
          <>
            {needsPassword && (
              <div>
                <label className="text-xs text-ink-muted flex items-center gap-1.5">
                  <Lock size={12} /> Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoFocus
                  className="w-full bg-paper-soft border border-hairline focus:border-finder-blue rounded-lg px-3 py-2 text-sm outline-none mt-1"
                />
              </div>
            )}

            {needsEmail && (
              <div>
                <label className="text-xs text-ink-muted flex items-center gap-1.5">
                  <Mail size={12} /> Your email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full bg-paper-soft border border-hairline focus:border-finder-blue rounded-lg px-3 py-2 text-sm outline-none mt-1"
                />
                <div className="text-[10px] text-ink-muted mt-1">
                  {m.watermark
                    ? "Your email will be watermarked on the downloaded PDF."
                    : "Access is restricted to specific addresses."}
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={download.isPending}
              className="w-full bg-finder-blue hover:bg-folder-to text-white font-medium rounded-lg py-2 text-sm flex items-center justify-center gap-1.5 disabled:opacity-50"
            >
              <Download size={14} />
              {download.isPending ? "Preparing…" : "Download report"}
            </button>
          </>
        )}

        <div className="text-[10px] text-ink-subtle text-center pt-2 border-t border-hairline">
          {m.max_views != null
            ? `${m.current_views} / ${m.max_views} views used`
            : `${m.current_views} views`}
          {m.expires_at && (
            <> · expires {new Date(m.expires_at).toLocaleString()}</>
          )}
        </div>
      </form>
    </div>
  );
}
