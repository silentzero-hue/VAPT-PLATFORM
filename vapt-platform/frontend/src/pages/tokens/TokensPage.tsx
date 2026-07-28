import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, Copy, KeyRound, Plus, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { formatDate } from "../../lib/cn";
import type { ApiToken } from "../../types";

const SCOPE_PRESETS = ["ingest:write", "findings:read", "findings:write", "reports:read", "admin"];

export default function TokensPage() {
  const { wid } = useParams();
  const auth = useAuth();
  const workspaceId = wid ?? auth.activeWorkspace;
  const qc = useQueryClient();

  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<string[]>([]);
  const [expiresAt, setExpiresAt] = useState("");
  const [revealed, setRevealed] = useState<{ id: string; raw: string } | null>(null);

  const tokens = useQuery({
    queryKey: ["tokens", workspaceId],
    queryFn: async () =>
      (await api.get<ApiToken[]>(`/workspaces/${workspaceId}/tokens`)).data,
    enabled: !!workspaceId,
  });

  const create = useMutation({
    mutationFn: async () =>
      (
        await api.post(`/workspaces/${workspaceId}/tokens`, {
          name,
          scopes,
          expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
        })
      ).data,
    onSuccess: (data) => {
      setRevealed({ id: data.id, raw: data.raw_token });
      setName("");
      setScopes([]);
      setExpiresAt("");
      qc.invalidateQueries({ queryKey: ["tokens", workspaceId] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Failed"),
  });

  const revoke = useMutation({
    mutationFn: async (tid: string) => api.delete(`/workspaces/${workspaceId}/tokens/${tid}`),
    onSuccess: () => {
      toast.success("Revoked");
      qc.invalidateQueries({ queryKey: ["tokens", workspaceId] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Revoke failed"),
  });

  const copy = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  };

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <KeyRound size={20} className="text-accent" /> API tokens
          </h1>
          <p className="text-sm text-fg-muted">
            Long-lived credentials for CI scanners and automation. Treat as secrets.
          </p>
        </div>
      </div>

      <div className="panel p-4">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-1.5">
          <Plus size={14} /> Create token
        </h3>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
          className="grid grid-cols-4 gap-3 items-end"
        >
          <div className="col-span-1">
            <label className="text-xs text-fg-muted">Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="ci-scanner-prod"
              className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm mt-1"
            />
          </div>
          <div className="col-span-2">
            <label className="text-xs text-fg-muted">Scopes</label>
            <div className="mt-1 flex flex-wrap gap-1">
              {SCOPE_PRESETS.map((s) => {
                const on = scopes.includes(s);
                return (
                  <button
                    type="button"
                    key={s}
                    onClick={() =>
                      setScopes((cur) =>
                        on ? cur.filter((x) => x !== s) : [...cur, s],
                      )
                    }
                    className={
                      on
                        ? "chip chip-info border-accent/30"
                        : "chip chip-muted hover:border-accent"
                    }
                  >
                    {on && <Check size={10} />} {s}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="col-span-1">
            <label className="text-xs text-fg-muted">Expires (optional)</label>
            <input
              type="datetime-local"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm mt-1"
            />
          </div>
          <button
            type="submit"
            disabled={create.isPending || !name}
            className="col-span-4 sm:col-span-1 sm:col-start-4 bg-accent hover:bg-accent-strong text-white rounded-lg px-3 py-1.5 text-sm disabled:opacity-50"
          >
            {create.isPending ? "Creating…" : "Create"}
          </button>
        </form>
      </div>

      <div className="panel overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-fg-muted text-xs bg-bg-soft">
            <tr className="text-left">
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Prefix</th>
              <th className="px-3 py-2">Scopes</th>
              <th className="px-3 py-2">Last used</th>
              <th className="px-3 py-2">Uses</th>
              <th className="px-3 py-2">Expires</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {(tokens.data ?? []).map((t) => (
              <tr key={t.id} className="border-t border-border-soft">
                <td className="px-3 py-2 font-medium">{t.name}</td>
                <td className="px-3 py-2 font-mono text-xs text-fg-muted">
                  {t.prefix}…
                </td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-1">
                    {t.scopes.map((s) => (
                      <span key={s} className="chip chip-muted font-mono">
                        {s}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-3 py-2 text-fg-muted text-xs">
                  {formatDate(t.last_used_at)}
                </td>
                <td className="px-3 py-2 font-mono text-xs">{t.use_count}</td>
                <td className="px-3 py-2 text-fg-muted text-xs">
                  {formatDate(t.expires_at)}
                </td>
                <td className="px-3 py-2">
                  {t.revoked ? (
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
                  {!t.revoked && (
                    <button
                      onClick={() => revoke.mutate(t.id)}
                      disabled={revoke.isPending}
                      className="text-xs px-2 py-1 bg-rose-500/15 text-rose-300 border border-rose-500/30 rounded hover:bg-rose-500/25"
                    >
                      Revoke
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {(tokens.data ?? []).length === 0 && (
              <tr>
                <td colSpan={8} className="text-center text-fg-muted py-8">
                  No tokens yet
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
              <AlertTriangle size={16} />
              <h2 className="text-sm font-semibold">
                Copy this token now — it will not be shown again
              </h2>
            </div>
            <div className="bg-bg-soft border border-border-soft rounded-lg p-3 flex items-center gap-2">
              <code className="flex-1 font-mono text-xs break-all">{revealed.raw}</code>
              <button
                onClick={() => copy(revealed.raw)}
                className="bg-accent/15 text-accent border border-accent/30 rounded px-2 py-1 text-xs flex items-center gap-1"
              >
                <Copy size={10} /> Copy
              </button>
            </div>
            <p className="text-xs text-fg-muted mt-3">
              Store it in your secret manager. The prefix shown in the list is the only
              hint you'll get later.
            </p>
            <div className="flex justify-end mt-4">
              <button
                onClick={() => setRevealed(null)}
                className="bg-accent hover:bg-accent-strong text-white rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5"
              >
                <X size={14} /> I have saved it
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
