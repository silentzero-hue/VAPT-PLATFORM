import AppleIcon from "../../components/ui/AppleIcon";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { cn } from "../../lib/cn";
import Card from "../../components/ui/Card";

export default function SettingsPage() {
  const auth = useAuth();
  const me = auth.user;
  const [code, setCode] = useState("");
  const [oldPwd, setOldPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const enroll = useMutation({
    mutationFn: async () => (await api.post<any>("/auth/me/totp/enroll")).data,
    onSuccess: () => toast.success("Scan the QR, then enter a code to confirm"),
  });
  const verify = useMutation({
    mutationFn: async () => api.post("/auth/me/totp/verify", { challenge_token: "enrollment", code }),
    onSuccess: () => { toast.success("TOTP enabled"); setCode(""); },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Bad code"),
  });
  const changePwd = useMutation({
    mutationFn: async () => api.post("/auth/me/password", { old_password: oldPwd, new_password: newPwd }),
    onSuccess: () => { toast.success("Password updated"); setOldPwd(""); setNewPwd(""); },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Failed"),
  });

  return (
    <div className="space-y-4 max-w-2xl">
      <h1 className="text-2xl font-semibold tracking-tight">Account settings</h1>

      <Card className="p-5">
        <div className="flex items-center gap-2 mb-3">
          <div className="h-8 w-8 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center">
            <AppleIcon name="user" size={14} className="text-accent" />
          </div>
          <h3 className="text-sm font-semibold">Profile</h3>
        </div>
        <dl className="space-y-2 text-sm">
          <div className="flex justify-between">
            <dt className="text-fg-muted">Email</dt>
            <dd className="font-mono">{me?.email ?? "—"}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-fg-muted">MFA</dt>
            <dd>
              {me?.totp_enabled ? (
                <span className="pill pill-success">enabled</span>
              ) : (
                <span className="pill pill-warning">not enabled</span>
              )}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-fg-muted">Role</dt>
            <dd className="text-xs text-right">
              {me?.memberships.map((m) => `${m.workspace_name}: ${m.role}`).join(", ") || "—"}
            </dd>
          </div>
        </dl>
      </Card>

      <Card className="p-5 space-y-3">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center">
            <AppleIcon name="shield-check" size={14} className="text-accent" />
          </div>
          <h3 className="text-sm font-semibold">Two-factor authentication</h3>
        </div>
        {!me?.totp_enabled && (
          <button
            onClick={() => enroll.mutate()}
            className={cn(
              "rounded-lg px-3 py-1.5 text-sm",
              "pill-info hover:brightness-125",
              "transition-all duration-200 ease-out"
            )}
          >
            Start enrollment
          </button>
        )}
        {enroll.data && (
          <div className="space-y-3">
            <img
              alt="QR"
              src={enroll.data.qr_data_uri}
              className="h-40 w-40 rounded-lg border border-white/[0.08]"
            />
            <div className="text-xs font-mono text-fg-muted break-all bg-white/[0.03] border border-white/[0.06] rounded-lg p-2">
              {enroll.data.secret}
            </div>
            <div className="flex gap-2 flex-wrap">
              <input
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="123456"
                className={cn(
                  "bg-white/[0.04] border border-white/[0.08] focus:border-accent/50",
                  "rounded-lg px-3 py-1.5 text-sm w-32 text-center font-mono outline-none",
                  "transition-colors duration-200 ease-out"
                )}
              />
              <button
                onClick={() => verify.mutate()}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-sm",
                  "bg-accent text-white hover:bg-accent-strong",
                  "transition-all duration-200 ease-out active:scale-[0.98]"
                )}
              >
                Verify
              </button>
            </div>
            <div className="text-xs text-fg-muted break-all">
              Backup codes: <span className="font-mono">{enroll.data.backup_codes.join(", ")}</span>
            </div>
          </div>
        )}
      </Card>

      <Card className="p-5 space-y-3">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center">
            <AppleIcon name="key" size={14} className="text-accent" />
          </div>
          <h3 className="text-sm font-semibold">Change password</h3>
        </div>
        <div className="space-y-2">
          <input
            type="password"
            value={oldPwd}
            onChange={(e) => setOldPwd(e.target.value)}
            placeholder="Current password"
            className={cn(
              "w-full bg-white/[0.04] border border-white/[0.08] focus:border-accent/50",
              "rounded-lg px-3 py-1.5 text-sm outline-none",
              "transition-colors duration-200 ease-out"
            )}
          />
          <input
            type="password"
            value={newPwd}
            onChange={(e) => setNewPwd(e.target.value)}
            placeholder="New password"
            className={cn(
              "w-full bg-white/[0.04] border border-white/[0.08] focus:border-accent/50",
              "rounded-lg px-3 py-1.5 text-sm outline-none",
              "transition-colors duration-200 ease-out"
            )}
          />
          <button
            onClick={() => changePwd.mutate()}
            disabled={!oldPwd || !newPwd || changePwd.isPending}
            className={cn(
              "rounded-lg px-3 py-1.5 text-sm",
              "bg-accent text-white hover:bg-accent-strong",
              "transition-all duration-200 ease-out active:scale-[0.98] disabled:opacity-50"
            )}
          >
            Update password
          </button>
        </div>
      </Card>
    </div>
  );
}
