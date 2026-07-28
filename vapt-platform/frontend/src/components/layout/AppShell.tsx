import { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
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
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { cn } from "../../lib/cn";

type AuthShape = ReturnType<typeof useAuth>;

const NAV: { to: string; label: string; icon: LucideIcon }[] = [
  { to: "", label: "Dashboard", icon: LayoutDashboard },
  { to: "engagements", label: "Engagements", icon: ClipboardList },
  { to: "assets", label: "Assets", icon: Building2 },
  { to: "findings", label: "Findings", icon: Bug },
  { to: "reports", label: "Reports", icon: FileText },
  { to: "agent", label: "Agent Review", icon: Sparkles },
  { to: "retests", label: "Retests", icon: RefreshCw },
  { to: "threat-intel", label: "Threat Intel", icon: Radar },
  { to: "sbom", label: "SBOM", icon: Workflow },
  { to: "nessus", label: "Nessus Live", icon: Shield },
  { to: "tableview", label: "Table View", icon: FileSpreadsheet },
  { to: "legacy", label: "Legacy Import", icon: Database },
  { to: "tokens", label: "API Tokens", icon: KeyRound },
  { to: "webhooks", label: "Webhooks", icon: Webhook },
  { to: "portal", label: "Portal Shares", icon: Share2 },
  { to: "ldap", label: "LDAP", icon: Plug },
  { to: "settings", label: "Settings", icon: Cog },
];

const COLLAPSE_KEY = "vapt_sidebar_collapsed";

export default function AppShell({ auth }: { auth: AuthShape }) {
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
      {/* Sidebar */}
      <aside
        className={cn(
          "shrink-0 sticky top-0 self-start h-screen border-r border-white/[0.08] glass",
          "flex flex-col transition-[width] duration-200 ease-out",
          collapsed ? "w-[60px]" : "w-[220px]"
        )}
      >
        <div
          className={cn(
            "h-14 flex items-center gap-2 border-b border-white/[0.08]",
            collapsed ? "justify-center px-0" : "px-4"
          )}
        >
          <Shield size={18} className="text-accent shrink-0" />
          {!collapsed && (
            <div className="font-semibold tracking-tight truncate">VAPT Platform</div>
          )}
        </div>

        <nav
          className={cn(
            "flex-1 py-3 space-y-0.5 text-sm scrollbar-thin overflow-y-auto",
            collapsed ? "px-1.5" : "px-2"
          )}
        >
          {NAV.map(({ to, label, icon: Icon }) => {
            const navTo = to === "" ? base : `${base}/${to}`;
            return (
              <NavItem
                key={to}
                Icon={Icon}
                label={label}
                active={isActive(to)}
                collapsed={collapsed}
                onClick={() => navigate(navTo)}
              />
            );
          })}
        </nav>

        <div className="border-t border-white/[0.08] p-2 space-y-1">
          {!collapsed && (
            <div className="px-2 py-1 text-[11px] text-fg-muted truncate">
              {auth.user?.email}
            </div>
          )}
          <button
            onClick={logout}
            aria-label="Logout"
            className={cn(
              "w-full flex items-center gap-2 rounded-md text-fg-muted hover:text-fg hover:bg-white/[0.05]",
              "transition-colors duration-200 ease-out",
              collapsed ? "justify-center h-8 w-full" : "px-2 h-8 text-sm"
            )}
            title={collapsed ? "Logout" : undefined}
          >
            <LogOut size={14} />
            {!collapsed && <span>Logout</span>}
          </button>
          <button
            onClick={() => setCollapsed((c) => !c)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={cn(
              "w-full flex items-center gap-2 rounded-md text-fg-muted hover:text-fg hover:bg-white/[0.05]",
              "transition-colors duration-200 ease-out",
              collapsed ? "justify-center h-8" : "px-2 h-8 text-sm"
            )}
            title={collapsed ? "Expand" : "Collapse"}
          >
            {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
            {!collapsed && <span>Collapse</span>}
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="sticky top-0 z-30 h-14 glass border-b border-white/[0.08] flex items-center gap-3 px-6">
          <WorkspaceSwitcher auth={auth} currentWid={wid} />
          <div className="flex-1 max-w-md relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-fg-muted" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search findings, assets, vulns…"
              className={cn(
                "w-full bg-white/[0.04] border border-white/[0.08] focus:border-accent/50",
                "rounded-full pl-9 pr-4 py-1.5 text-sm outline-none",
                "transition-colors duration-200 ease-out",
                "placeholder:text-fg-subtle"
              )}
            />
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="pill pill-success">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" /> Online
            </span>
          </div>
        </header>
        <main className="flex-1 min-w-0 overflow-y-auto px-8 py-6 pb-10">
          <Outlet />
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
  onClick,
}: {
  Icon: LucideIcon;
  label: string;
  active: boolean;
  collapsed: boolean;
  onClick: () => void;
}) {
  const ref = useRef<HTMLButtonElement | null>(null);
  const [tip, setTip] = useState<{ top: number; left: number } | null>(null);

  const showTip = () => {
    if (!collapsed || !ref.current) return;
    const r = ref.current.getBoundingClientRect();
    setTip({ top: r.top + r.height / 2, left: r.right + 8 });
  };

  return (
    <>
      <button
        ref={ref}
        onClick={onClick}
        onMouseEnter={showTip}
        onMouseLeave={() => setTip(null)}
        onFocus={showTip}
        onBlur={() => setTip(null)}
        aria-current={active ? "page" : undefined}
        aria-label={collapsed ? label : undefined}
        className={cn(
          "w-full flex items-center gap-2 rounded-lg text-left relative",
          "transition-all duration-200 ease-out",
          collapsed ? "justify-center h-9 w-full" : "px-3 py-2",
          active
            ? "bg-accent/15 text-fg border border-accent/30"
            : "text-fg-muted hover:text-fg hover:bg-white/[0.05] border border-transparent"
        )}
        title={collapsed ? label : undefined}
      >
        <Icon size={16} className="shrink-0" />
        {!collapsed && <span className="truncate">{label}</span>}
      </button>
      {collapsed && tip && (
        <div
          className="fixed z-50 px-2 py-1 rounded-md glass-strong text-xs text-fg whitespace-nowrap pointer-events-none animate-fade-in"
          style={{ top: tip.top, left: tip.left, transform: "translateY(-50%)" }}
        >
          {label}
        </div>
      )}
    </>
  );
}

function WorkspaceSwitcher({ auth, currentWid }: { auth: AuthShape; currentWid: string | undefined }) {
  const memberships = auth.user?.memberships ?? [];
  if (memberships.length === 0) return null;
  return (
    <select
      className={cn(
        "bg-white/[0.04] border border-white/[0.08] rounded-full",
        "px-3 py-1.5 text-sm outline-none",
        "transition-colors duration-200 ease-out focus:border-accent/50"
      )}
      value={currentWid ?? ""}
      onChange={(e) => auth.setActiveWorkspace(e.target.value)}
    >
      {memberships.map((m) => (
        <option key={m.workspace_id} value={m.workspace_id}>
          {m.workspace_name}
        </option>
      ))}
    </select>
  );
}
