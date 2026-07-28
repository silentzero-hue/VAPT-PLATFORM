import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Shield, KeyRound, Mail } from "lucide-react";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const nav = useNavigate();
  const auth = useAuth();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.post("/auth/login", { email, password });
      if (res.data.totp_required) {
        sessionStorage.setItem("vapt_totp_challenge", res.data.challenge_token);
        nav("/login/totp");
        return;
      }
      // No TOTP — re-validate the session into the shared context,
      // then navigate. The single refreshMe() also runs on the
      // AppRouter mount, but we want a hard refresh here so the
      // user lands on /workspaces with user already populated.
      await auth.refreshMe();
      toast.success("Welcome back");
      nav("/workspaces");
    } catch (e: any) {
      toast.error(e?.response?.data?.detail ?? "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg relative overflow-hidden">
      <div className="absolute inset-0 -z-10 opacity-30">
        <div className="absolute -top-40 -left-40 w-96 h-96 rounded-full bg-accent/30 blur-3xl" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 rounded-full bg-purple-500/20 blur-3xl" />
      </div>
      <form
        onSubmit={submit}
        className="w-full max-w-sm panel p-7 space-y-5"
      >
        <div className="flex items-center gap-2">
          <div className="h-9 w-9 rounded-lg bg-accent/15 border border-accent/30 flex items-center justify-center">
            <Shield size={18} className="text-accent" />
          </div>
          <div>
            <div className="font-semibold">VAPT Platform</div>
            <div className="text-xs text-fg-muted">Sign in to your workspace</div>
          </div>
        </div>
        <div>
          <label className="text-xs text-fg-muted">Email</label>
          <div className="relative mt-1">
            <Mail size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-fg-muted" />
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="w-full bg-bg-soft border border-border-soft focus:border-accent rounded-lg pl-8 pr-3 py-2 text-sm outline-none"
            />
          </div>
        </div>
        <div>
          <label className="text-xs text-fg-muted">Password</label>
          <div className="relative mt-1">
            <KeyRound size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-fg-muted" />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="current-password"
              className="w-full bg-bg-soft border border-border-soft focus:border-accent rounded-lg pl-8 pr-3 py-2 text-sm outline-none"
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-accent hover:bg-accent-strong text-white font-medium rounded-lg py-2 disabled:opacity-50"
        >
          {loading ? "Verifying…" : "Continue"}
        </button>
        <p className="text-[11px] text-fg-muted text-center">
          Multi-factor authentication is enforced for analyst and admin roles.
        </p>
        <div className="text-center text-xs text-fg-muted">
          <Link to="/forgot" className="text-accent hover:underline">
            Forgot password?
          </Link>
        </div>
      </form>
    </div>
  );
}
