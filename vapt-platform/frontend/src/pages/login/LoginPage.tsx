import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AppleIcon from "../../components/ui/AppleIcon";
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
    <div className="min-h-screen flex items-center justify-center bg-paper relative overflow-hidden">
      <div className="absolute inset-0 -z-10 opacity-40">
        <div className="absolute -top-40 -left-40 w-96 h-96 rounded-full bg-finder-blue/20 blur-3xl" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 rounded-full bg-folder-from/20 blur-3xl" />
      </div>
      <form
        onSubmit={submit}
        className="w-full max-w-sm panel p-7 space-y-5"
      >
        <div className="flex items-center gap-2">
          <div className="h-9 w-9 rounded-lg bg-finder-blue-soft border border-finder-blue/30 flex items-center justify-center">
            <AppleIcon name="shield" size={18} className="text-finder-blue" />
          </div>
          <div>
            <div className="font-semibold text-ink">VAPT Platform</div>
            <div className="text-xs text-ink-muted">Sign in to your workspace</div>
          </div>
        </div>
        <div>
          <label className="text-xs text-ink-muted">Email</label>
          <div className="relative mt-1">
            <AppleIcon name="envelope" size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-muted" />
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="w-full bg-paper-soft border border-hairline focus:border-finder-blue rounded-lg pl-8 pr-3 py-2 text-sm outline-none text-ink"
            />
          </div>
        </div>
        <div>
          <label className="text-xs text-ink-muted">Password</label>
          <div className="relative mt-1">
            <AppleIcon name="key" size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-muted" />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="current-password"
              className="w-full bg-paper-soft border border-hairline focus:border-finder-blue rounded-lg pl-8 pr-3 py-2 text-sm outline-none text-ink"
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-finder-blue hover:bg-folder-to text-white font-medium rounded-lg py-2 disabled:opacity-50 transition-colors"
        >
          {loading ? "Verifying…" : "Continue"}
        </button>
        <p className="text-[11px] text-ink-muted text-center">
          Multi-factor authentication is enforced for analyst and admin roles.
        </p>
        <div className="text-center text-xs text-ink-muted">
          <Link to="/forgot" className="text-finder-blue hover:underline">
            Forgot password?
          </Link>
        </div>
      </form>
    </div>
  );
}
