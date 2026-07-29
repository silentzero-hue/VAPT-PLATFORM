import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { formatDate } from "../../lib/cn";
import type { LdapConfig } from "../../types";
import { RotateCw, Save, Server } from "lucide-react";

export default function LdapPage() {
  const { wid } = useParams();
  const auth = useAuth();
  const workspaceId = wid ?? auth.activeWorkspace;
  const qc = useQueryClient();

  const [serverUrl, setServerUrl] = useState("");
  const [useTls, setUseTls] = useState(true);
  const [bindDn, setBindDn] = useState("");
  const [bindPassword, setBindPassword] = useState("");
  const [userSearchBase, setUserSearchBase] = useState("");
  const [userSearchFilter, setUserSearchFilter] = useState("(uid={username})");
  const [defaultRole, setDefaultRole] = useState("viewer");
  const [groupRoleMap, setGroupRoleMap] = useState("");

  const cfg = useQuery({
    queryKey: ["ldap", workspaceId],
    queryFn: async () =>
      (await api.get<LdapConfig>(`/workspaces/${workspaceId}/ldap`)).data,
    enabled: !!workspaceId,
    retry: false,
  });

  useEffect(() => {
    if (cfg.data) {
      setServerUrl(cfg.data.server_url ?? "");
      setUseTls(cfg.data.use_tls ?? true);
      setBindDn(cfg.data.bind_dn ?? "");
      setUserSearchBase(cfg.data.user_search_base ?? "");
      setUserSearchFilter(cfg.data.user_search_filter ?? "(uid={username})");
      setDefaultRole(cfg.data.default_role ?? "viewer");
      const map = cfg.data.group_role_map ?? {};
      setGroupRoleMap(Object.entries(map).map(([g, r]) => `${g}=${r}`).join("\n"));
    }
  }, [cfg.data]);

  const save = useMutation({
    mutationFn: async () => {
      const map: Record<string, string> = {};
      for (const line of groupRoleMap.split("\n")) {
        const [g, r] = line.split("=").map((s) => s.trim());
        if (g && r) map[g] = r;
      }
      return api.put(`/workspaces/${workspaceId}/ldap`, {
        server_url: serverUrl,
        use_tls: useTls,
        bind_dn: bindDn,
        bind_password: bindPassword || null,
        user_search_base: userSearchBase,
        user_search_filter: userSearchFilter,
        default_role: defaultRole,
        group_role_map: map,
      });
    },
    onSuccess: () => {
      toast.success("Saved");
      setBindPassword("");
      qc.invalidateQueries({ queryKey: ["ldap", workspaceId] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Save failed"),
  });

  const sync = useMutation({
    mutationFn: async () =>
      (await api.post(`/workspaces/${workspaceId}/ldap/sync`)).data,
    onSuccess: (data) => {
      toast.success(`Sync done — ${data?.created ?? 0} created, ${data?.updated ?? 0} updated`);
      qc.invalidateQueries({ queryKey: ["ldap", workspaceId] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Sync failed"),
  });

  return (
    <div className="space-y-4 max-w-3xl mx-auto p-4 min-w-0">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <Server size={20} className="text-finder-blue" /> LDAP / Active Directory
          </h1>
          <p className="text-sm text-ink-muted">
            Provision and sync users from your corporate directory
          </p>
        </div>
        <button
          onClick={() => sync.mutate()}
          disabled={sync.isPending || !cfg.data}
          className="bg-finder-blue hover:bg-folder-to text-white rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5 disabled:opacity-50"
        >
          <RotateCw size={14} /> {sync.isPending ? "Syncing…" : "Sync now"}
        </button>
      </div>

      {cfg.data?.last_sync_at && (
        <div className="panel p-3 text-xs flex items-center gap-3">
          <span className="text-ink-muted">Last sync:</span>
          <span>{formatDate(cfg.data.last_sync_at)}</span>
          {cfg.data.last_sync_status && (
            <span
              className={
                cfg.data.last_sync_status === "ok"
                  ? "pill bg-sev-low-soft text-sev-low-strong border-sev-low"
                  : "pill bg-sev-critical-soft text-sev-critical-strong border-sev-critical"
              }
            >
              {cfg.data.last_sync_status}
            </span>
          )}
          {cfg.data.last_sync_message && (
            <span className="text-ink-muted truncate">{cfg.data.last_sync_message}</span>
          )}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
        className="panel p-4 space-y-3"
      >
        <h3 className="text-sm font-semibold">Connection</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="col-span-2">
            <label className="text-xs text-ink-muted">Server URL</label>
            <input
              value={serverUrl}
              onChange={(e) => setServerUrl(e.target.value)}
              required
              placeholder="ldaps://ldap.example.com:636"
              className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-sm mt-1"
            />
          </div>
          <div>
            <label className="text-xs text-ink-muted">TLS</label>
            <label className="flex items-center gap-2 mt-1 text-sm">
              <input
                type="checkbox"
                checked={useTls}
                onChange={(e) => setUseTls(e.target.checked)}
                className="accent-accent"
              />
              use_tls (ldaps://)
            </label>
          </div>
          <div className="col-span-2">
            <label className="text-xs text-ink-muted">Bind DN</label>
            <input
              value={bindDn}
              onChange={(e) => setBindDn(e.target.value)}
              required
              placeholder="cn=svc-vapt,ou=services,dc=example,dc=com"
              className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-sm mt-1"
            />
          </div>
          <div>
            <label className="text-xs text-ink-muted">Bind password</label>
            <input
              type="password"
              value={bindPassword}
              onChange={(e) => setBindPassword(e.target.value)}
              placeholder={cfg.data?.bind_password ? "••••••" : "set"}
              className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-sm mt-1"
            />
          </div>
        </div>

        <h3 className="text-sm font-semibold pt-2">User search</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-ink-muted">Search base</label>
            <input
              value={userSearchBase}
              onChange={(e) => setUserSearchBase(e.target.value)}
              required
              placeholder="ou=people,dc=example,dc=com"
              className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-sm mt-1"
            />
          </div>
          <div>
            <label className="text-xs text-ink-muted">Search filter</label>
            <input
              value={userSearchFilter}
              onChange={(e) => setUserSearchFilter(e.target.value)}
              required
              className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-sm mt-1 font-mono"
            />
          </div>
        </div>

        <h3 className="text-sm font-semibold pt-2">Role mapping</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-ink-muted">Default role (no group match)</label>
            <select
              value={defaultRole}
              onChange={(e) => setDefaultRole(e.target.value)}
              className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-sm mt-1"
            >
              <option value="viewer">viewer</option>
              <option value="analyst">analyst</option>
              <option value="senior_analyst">senior_analyst</option>
              <option value="admin">admin</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-ink-muted">Group → role (one per line)</label>
            <textarea
              value={groupRoleMap}
              onChange={(e) => setGroupRoleMap(e.target.value)}
              rows={3}
              placeholder={"cn=pentesters,ou=groups,dc=example,dc=com=analyst\ncn=sec-leads,...=senior_analyst"}
              className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-sm mt-1 font-mono"
            />
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={save.isPending}
            className="bg-finder-blue hover:bg-folder-to text-white rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5 disabled:opacity-50"
          >
            <Save size={14} /> {save.isPending ? "Saving…" : "Save config"}
          </button>
        </div>
      </form>
    </div>
  );
}
