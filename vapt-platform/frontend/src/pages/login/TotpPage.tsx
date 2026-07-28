import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { Key, Shield } from "lucide-react";

export default function TotpPage() {
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const nav = useNavigate();
  const auth = useAuth();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const challenge = sessionStorage.getItem("vapt_totp_challenge");
    if (!challenge) {
      toast.error("No challenge. Please log in again.");
      nav("/login");
      return;
    }
    setLoading(true);
    try {
      await api.post("/auth/login/totp", { challenge_token: challenge, code });
      sessionStorage.removeItem("vapt_totp_challenge");
      // refreshMe writes to the shared AuthProvider context, so App.tsx's
      // Protected route sees the user as set on next render.
      await auth.refreshMe();
      toast.success("Verified");
      nav("/workspaces");
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? "Invalid code");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-paper">
      <form onSubmit={submit} className="w-full max-w-sm panel p-7 space-y-5">
        <div className="flex items-center gap-2">
          <div className="h-9 w-9 rounded-lg bg-finder-blue-soft border border-finder-blue/30 flex items-center justify-center">
            <Shield size={18} className="text-finder-blue" />
          </div>
          <div>
            <div className="font-semibold text-ink">Two-factor authentication</div>
            <div className="text-xs text-ink-muted">Enter the 6-digit code from your authenticator</div>
          </div>
        </div>
        <div>
          <label className="text-xs text-ink-muted">Authenticator code</label>
          <div className="relative mt-1">
            <Key size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-muted" />
            <input
              autoFocus
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/[^0-9]/g, "").slice(0, 8))}
              required
              inputMode="numeric"
              pattern="[0-9]{6,8}"
              placeholder="123456"
              className="w-full tracking-[0.4em] text-center bg-paper-soft border border-hairline focus:border-finder-blue rounded-lg pl-8 pr-3 py-2 text-lg outline-none font-mono text-ink"
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={loading || code.length < 6}
          className="w-full bg-finder-blue hover:bg-folder-to text-white font-medium rounded-lg py-2 disabled:opacity-50 transition-colors"
        >
          {loading ? "Verifying…" : "Verify"}
        </button>
      </form>
    </div>
  );
}
