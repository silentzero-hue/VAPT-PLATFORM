import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from "react";
import { api } from "../lib/api";
import type { User } from "../types";

const STORAGE_KEY = "vapt_active_workspace";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  activeWorkspace: string | null;
  setActiveWorkspace: (wid: string) => void;
  refreshMe: () => Promise<void>;
  clear: () => void;
  setLoading: (b: boolean) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeWorkspace, setActiveWorkspaceState] = useState<string | null>(
    () => (typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null)
  );

  const refreshMe = useCallback(async () => {
    try {
      const res = await api.get<User>("/auth/me");
      setUser(res.data);
      if (res.data.memberships.length > 0) {
        const validIds = new Set(res.data.memberships.map((m) => m.workspace_id));
        setActiveWorkspaceState((current) => {
          const wid = current && validIds.has(current)
            ? current
            : res.data.memberships[0].workspace_id;
          localStorage.setItem(STORAGE_KEY, wid);
          return wid;
        });
      }
    } catch {
      setUser(null);
    }
  }, []);

  const switchWorkspace = useCallback((wid: string) => {
    localStorage.setItem(STORAGE_KEY, wid);
    setActiveWorkspaceState(wid);
  }, []);

  const clear = useCallback(() => {
    setUser(null);
    setActiveWorkspaceState(null);
    try { localStorage.removeItem(STORAGE_KEY); } catch {}
  }, []);

  // On mount: check if a session cookie is still valid.
  useEffect(() => {
    refreshMe();
  }, [refreshMe]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user, loading, activeWorkspace,
      setActiveWorkspace: switchWorkspace,
      refreshMe, clear, setLoading,
    }),
    [user, loading, activeWorkspace, switchWorkspace, refreshMe, clear]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
