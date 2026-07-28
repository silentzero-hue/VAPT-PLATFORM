import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  Bell,
  Bug,
  Building2,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Cog,
  Database,
  FileSpreadsheet,
  FileText,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Moon,
  Plug,
  Radar,
  RefreshCw,
  Search,
  Share2,
  Shield,
  Sparkles,
  Webhook,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import { Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { cn } from "../../lib/cn";
import NavArrows from "./NavArrows";
import StatusBar from "./StatusBar";

type NavGroup = {
  label: string;
  items: { to: string; label: string; icon: LucideIcon; badgeKey?: "engagements" | "findings" | "reports" | "tokens" }[];
};

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Workspace",
    items: [
      { to: "", label: "Dashboard", icon: LayoutDashboard },
      { to: "engagements", label: "Engagements", icon: ClipboardList, badgeKey: "engagements" },
      { to: "assets", label: "Assets", icon: Building2 },
      { to: "findings", label: "Findings", icon: Bug, badgeKey: "findings" },
      { to: "retests", label: "Retests", icon: RefreshCw },
    ],
  },
  {
    label: "Reporting",
    items: [
      { to: "reports", label: "Reports", icon: FileText, badgeKey: "reports" },
      { to: "tableview", label: "Table View", icon: FileSpreadsheet },
      { to: "threat-intel", label: "Threat Intel", icon: Radar },
      { to: "sbom", label: "SBOM", icon: Workflow },
    ],
  },
  {
    label: "Sources",
    items: [
      { to: "nessus", label: "Nessus Live", icon: Shield },
      { to: "agent", label: "Agent Review", icon: Sparkles },
      { to: "legacy", label: "Legacy Import", icon: Database },
    ],
  },
  {
    label: "Admin",
    items: [
      { to: "tokens", label: "API Tokens", icon: KeyRound, badgeKey: "tokens" },
      { to: "webhooks", label: "Webhooks", icon: Webhook },
      { to: "portal", label: "Portal Shares", icon: Share2 },
      { to: "ldap", label: "LDAP", icon: Plug },
      { to: "settings", label: "Settings", icon: Cog },
    ],
  },
];

const COLLAPSE_KEY = "vapt_sidebar_collapsed";

type BadgeCounts = Partial<Record<"engagements" | "findings" | "reports" | "tokens", number | undefined>>;

function useNavHistory() {
  const location = useLocation();
  const navigate = useNavigate();
  const [, setTick] = useState(0);
  const stackRef = useRef<string[]>([location.pathname]);
  const idxRef = useRef(0);
  const lastPathRef = useRef(location.pathname);

  useEffect(() => {
    const newPath = location.pathname;
    if (newPath === lastPathRef.current) return;
    lastPathRef.current = newPath;

    const stack = stackRef.current;
    const idx = idxRef.current;

    if (stack[idx + 1] === newPath) {
      idxRef.current = idx + 1;
    } else if (stack[idx - 1] === newPath) {
      idxRef.current = idx - 1;
    } else {
      stackRef.current = [...stack.slice(0, idx + 1), newPath];
      idxRef.current = idx + 1;
    }
    setTick((t) => t + 1);
  }, [location.pathname]);

  const canGoBack = idxRef.current > 0;
  const canGoForward = idxRef.current < stackRef.current.length - 1;

  const goBack = useCallback(() => {
    if (idxRef.current > 0) {
      const target = stackRef.current[idxRef.current - 1];
      navigate(target);
    }
  }, [navigate]);

  const goForward = useCallback(() => {
    if (idxRef.current < stackRef.current.length - 1) {
      const target = stackRef.current[idxRef.current + 1];
      navigate(target);
    }
  }, [navigate]);

  return { canGoBack, canGoForward, goBack, goForward };
}

function useBadgeCounts(wid: string | undefined): BadgeCounts {
  const engs = useQuery({
    queryKey: ["engagements", wid],
    queryFn: async () =>
      (await api.get<any[]>(`/workspaces/${wid}/engagements`)).data,
    enabled: !!wid,
    refetchInterval: 60_000,
  });

  const reports = useQuery({
    queryKey: ["reports", wid],
    queryFn: async () => (await api.get<any[]>(`/reports`)).data,
    enabled: !!wid,
    refetchInterval: 60_000,
  });

  const tokens = useQuery({
    queryKey: ["tokens", wid],
    queryFn: async () =>
      (await api.get<any[]>(`/workspaces/${wid}/tokens`)).data,
    enabled: !!wid,
    refetchInterval: 60_000,
  });

  const engCount = engs.data?.length;
  const findingsTotal = (engs.data ?? []).reduce(
    (acc, e) => acc + (e.findings_total ?? 0),
    0
  );
  const activeTokens = (tokens.data ?? []).filter((t) => !t.revoked).length;

  return {
    engagements: engCount,
    findings: findingsTotal,
    reports: reports.data?.length,
    tokens: activeTokens,
  };
}

export default function AppShell() {
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const wid = location.pathname.match(/^\/workspaces\/([^/]+)/)?.[1]
    ?? auth.activeWorkspace
    ?? auth.user?.memberships[0]?.workspace_id;
  const [query, setQuery] = useState("");
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(COLLAPSE_KEY) === "1";
  });

  useEffect(() => {
    localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0");
  }, [collapsed]);

  const { canGoBack, canGoForward, goBack, goForward } = useNavHistory();
  const badges = useBadgeCounts(wid);

  const base = `/workspaces/${wid}`;
  const isActive = (rel: string) => {
    if (rel === "") return location.pathname === base;
    return location.pathname.startsWith(`${base}/${rel}`);
  };

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch {}
    auth.clear();
    toast.success("Logged out");
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex bg-bg text-fg">
      <aside
        className={cn(
          "shrink-0 sticky top-0 self-start h-screen border-r border-white/[0.06]",
          "glass-strong flex flex-col",
          "transition-[width] duration-300 ease-out",
          collapsed ? "w-[68px]" : "w-[240px]"
        )}
      >
        <div
          className={cn(
            "h-14 flex items-center gap-3 border-b border-white/[0.06] shrink-0",
            collapsed ? "justify-center px-0" : "px-4"
          )}
        >
          <div className="h-7 w-7 rounded-md bg-gradient-to-br from-accent to-accent-strong flex items-center justify-center shrink-0 shadow-accent-glow">
            <Shield size={14} className="text-white" />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="font-semibold tracking-tight text-sm leading-none">VAPT Platform</div>
              <div className="text-[10px] text-fg-muted mt-0.5">Technovage Edition</div>
            </div>
          )}
        </div>

        {!collapsed && (
          <div className="px-3 pt-2.5">
            <WorkspaceSwitcher auth={auth} currentWid={wid} />
          </div>
        )}

        <nav className="flex-1 py-2 overflow-y-auto scrollbar-thin">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="mb-1">
              {!collapsed && (
                <div className="px-4 py-1.5 text-[10px] uppercase tracking-wider text-fg-subtle font-semibold">
                  {group.label}
                </div>
              )}
              {group.items.map((item) => {
                const navTo = item.to === "" ? base : `${base}/${item.to}`;
                const badgeValue = item.badgeKey ? badges[item.badgeKey] : undefined;
                return (
                  <NavItem
                    key={item.to}
                    Icon={item.icon}
                    label={item.label}
                    active={isActive(item.to)}
                    collapsed={collapsed}
                    badge={badgeValue}
                    onClick={() => navigate(navTo)}
                  />
                );
              })}
            </div>
          ))}
        </nav>

        <div className="border-t border-white/[0.06] p-2 space-y-1">
          <SystemHealthWidget collapsed={collapsed} />
          <UserWidget user={auth.user} collapsed={collapsed} onLogout={logout} />
          <CollapseToggle collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="sticky top-0 z-30 h-14 glass-soft border-b border-white/[0.06] flex items-center px-4 gap-3">
          <NavArrows
            canGoBack={canGoBack}
            canGoForward={canGoForward}
            onBack={goBack}
            onForward={goForward}
          />
          <Breadcrumb base={base} />
          <div className="flex-1 max-w-md mx-auto">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-fg-subtle" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                type="search"
                placeholder="Search reports, findings, hosts…"
                className={cn(
                  "w-full bg-white/[0.04] border border-white/[0.06] rounded-md",
                  "pl-9 pr-3 h-8 text-sm outline-none",
                  "transition-colors duration-200 ease-out",
                  "placeholder:text-fg-subtle",
                  "focus:border-accent/50 focus:bg-white/[0.06]"
                )}
              />
            </div>
          </div>
          <DarkModeToggle />
          <NotificationBell />
          <UserAvatar user={auth.user} />
        </header>
        <main className="flex-1 min-w-0 overflow-y-auto flex flex-col">
          <div className="flex-1 min-h-0">
            <Outlet />
          </div>
          <StatusBar />
        </main>
      </div>
    </div>
  );
}

function NavItem({
  Icon,
  label,
  active,
  collapsed,
  badge,
  onClick,
}: {
  Icon: LucideIcon;
  label: string;
  active: boolean;
  collapsed: boolean;
  badge?: number | undefined;
  onClick: () => void;
}) {
  const showBadge = !collapsed && typeof badge === "number" && badge > 0;
  return (
    <button
      onClick={onClick}
      title={collapsed ? label : undefined}
      aria-current={active ? "page" : undefined}
      aria-label={collapsed ? label : undefined}
      className={cn(
        "group relative w-full flex items-center gap-3 rounded-md",
        "transition-colors duration-150 ease-out text-left",
        collapsed ? "h-9 justify-center px-0 my-0.5 mx-1" : "h-8 px-3 my-0.5",
        active
          ? "bg-accent/15 text-accent"
          : "text-fg-muted hover:text-fg hover:bg-white/[0.04]"
      )}
    >
      {active && (
        <span
          className={cn(
            "absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-r-full bg-accent",
            collapsed && "hidden"
          )}
        />
      )}
      <Icon
        size={15}
        className={cn(
          "shrink-0",
          active ? "text-accent" : "text-fg-muted group-hover:text-fg"
        )}
      />
      {!collapsed && (
        <>
          <span className="text-[13px] truncate flex-1">{label}</span>
          {showBadge && (
            <span
              className={cn(
                "shrink-0 text-[10px] tabular-nums px-1.5 py-0.5 rounded-md min-w-[20px] text-center",
                active
                  ? "bg-accent/25 text-accent"
                  : "bg-white/[0.06] text-fg-muted group-hover:bg-white/[0.1] group-hover:text-fg"
              )}
            >
              {badge! >= 1000 ? `${(badge! / 1000).toFixed(1)}k` : badge}
            </span>
          )}
        </>
      )}
    </button>
  );
}

function Breadcrumb({ base }: { base: string }) {
  const loc = useLocation();
  const after = loc.pathname.replace(base, "").replace(/^\//, "");
  const parts = after.split("/").filter(Boolean);
  const titleize = (s: string) =>
    s
      .split("-")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");
  return (
    <div className="flex items-center gap-1.5 text-sm text-fg-muted min-w-0 flex-1">
      <span className="font-medium text-fg">Default Workspace</span>
      {parts.map((p, i) => (
        <span key={i} className="flex items-center gap-1.5 min-w-0">
          <ChevronRight size={12} className="text-fg-subtle shrink-0" />
          <span className={cn("truncate", i === parts.length - 1 ? "text-fg" : "")}>
            {titleize(p)}
          </span>
        </span>
      ))}
    </div>
  );
}

function WorkspaceSwitcher({
  auth,
  currentWid,
}: {
  auth: ReturnType<typeof useAuth>;
  currentWid: string | undefined;
}) {
  const memberships = auth.user?.memberships ?? [];
  const current = memberships.find((m) => m.workspace_id === currentWid);
  const name = current?.workspace_name ?? "Default Workspace";
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  if (memberships.length === 0) {
    return (
      <div className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md bg-white/[0.04] text-xs text-fg-muted">
        <Building2 size={12} className="text-accent shrink-0" />
        <span className="truncate flex-1 text-left">{name}</span>
      </div>
    );
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "w-full flex items-center gap-2 px-2 py-1.5 rounded-md",
          "bg-white/[0.04] hover:bg-white/[0.08] text-xs text-fg-muted hover:text-fg",
          "transition-colors duration-150"
        )}
      >
        <Building2 size={12} className="text-accent shrink-0" />
        <span className="truncate flex-1 text-left">{name}</span>
        <ChevronRight
          size={10}
          className={cn(
            "transition-transform duration-200",
            open && "rotate-90"
          )}
        />
      </button>
      {open && (
        <div
          className={cn(
            "absolute left-0 right-0 top-full mt-1 z-40",
            "rounded-md py-1 glass-strong shadow-glass-strong animate-fade-in"
          )}
        >
          {memberships.map((m) => (
            <button
              key={m.workspace_id}
              onClick={() => {
                auth.setActiveWorkspace(m.workspace_id);
                setOpen(false);
              }}
              className={cn(
                "w-full flex items-center gap-2 px-2 py-1.5 text-xs text-left",
                "transition-colors duration-150",
                m.workspace_id === currentWid
                  ? "bg-accent/15 text-accent"
                  : "text-fg-muted hover:bg-white/[0.06] hover:text-fg"
              )}
            >
              <Building2 size={11} className="shrink-0" />
              <span className="truncate flex-1">{m.workspace_name}</span>
              {m.workspace_id === currentWid && (
                <span className="h-1.5 w-1.5 rounded-full bg-accent shrink-0" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function SystemHealthWidget({ collapsed }: { collapsed: boolean }) {
  const { data } = useQuery({
    queryKey: ["system-health"],
    queryFn: async () => (await api.get("/health")).data,
    refetchInterval: 30_000,
    retry: false,
  });
  const ok = data?.status === "ok";
  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-md px-2 py-1.5 text-xs",
        ok ? "text-emerald-400" : "text-amber-400",
        collapsed && "justify-center"
      )}
      title={collapsed ? (ok ? "All systems operational" : "Issues detected") : undefined}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full shrink-0",
          ok ? "bg-emerald-400" : "bg-amber-400",
          ok && "animate-pulse"
        )}
      />
      {!collapsed && (ok ? "All systems operational" : data ? "Issues detected" : "Checking…")}
    </div>
  );
}

function UserWidget({
  user,
  collapsed,
  onLogout,
}: {
  user: ReturnType<typeof useAuth>["user"];
  collapsed: boolean;
  onLogout: () => void;
}) {
  if (!user) return null;
  return (
    <button
      onClick={onLogout}
      aria-label="Logout"
      className={cn(
        "w-full flex items-center gap-2 rounded-md text-fg-muted hover:text-fg hover:bg-white/[0.04]",
        "transition-colors duration-150",
        collapsed ? "justify-center h-8" : "px-2 h-8 text-xs"
      )}
      title={collapsed ? "Logout" : undefined}
    >
      {collapsed ? (
        <LogOut size={14} />
      ) : (
        <>
          <div className="h-5 w-5 rounded-full bg-accent/20 border border-accent/30 flex items-center justify-center text-[10px] font-semibold text-accent shrink-0">
            {(user.email?.[0] ?? "?").toUpperCase()}
          </div>
          <span className="truncate flex-1 text-left">{user.email}</span>
          <LogOut size={12} className="shrink-0" />
        </>
      )}
    </button>
  );
}

function CollapseToggle({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      onClick={onToggle}
      aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      className={cn(
        "w-full flex items-center gap-2 rounded-md text-fg-muted hover:text-fg hover:bg-white/[0.04]",
        "transition-colors duration-150",
        collapsed ? "justify-center h-8" : "px-2 h-8 text-xs"
      )}
      title={collapsed ? "Expand" : "Collapse"}
    >
      {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
      {!collapsed && <span>Collapse</span>}
    </button>
  );
}

function DarkModeToggle() {
  return (
    <button
      aria-label="Toggle theme"
      className={cn(
        "h-8 w-8 rounded-md flex items-center justify-center",
        "text-fg-muted hover:text-fg hover:bg-white/[0.04]",
        "transition-colors duration-150"
      )}
      title="Theme"
    >
      <Moon size={15} />
    </button>
  );
}

function NotificationBell() {
  return (
    <button
      aria-label="Notifications"
      className={cn(
        "relative h-8 w-8 rounded-md flex items-center justify-center",
        "text-fg-muted hover:text-fg hover:bg-white/[0.04]",
        "transition-colors duration-150"
      )}
      title="Notifications"
    >
      <Bell size={15} />
    </button>
  );
}

function UserAvatar({ user }: { user: ReturnType<typeof useAuth>["user"] }) {
  if (!user) return null;
  const initial = (user.email?.[0] ?? "?").toUpperCase();
  return (
    <div
      className={cn(
        "h-8 w-8 rounded-full flex items-center justify-center text-xs font-semibold",
        "bg-accent/20 border border-accent/30 text-accent shrink-0"
      )}
      title={user.email}
    >
      {initial}
    </div>
  );
}
