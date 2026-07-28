import { useQuery } from "@tanstack/react-query";
import AppleIcon, { type AppleIconName } from "../ui/AppleIcon";
import { useLocation, useParams } from "react-router-dom";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { cn } from "../../lib/cn";

interface StatusBarProps {
  className?: string;
  forceVisible?: boolean;
}

export default function StatusBar({ className, forceVisible = false }: StatusBarProps) {
  const { wid: paramWid } = useParams();
  const auth = useAuth();
  const location = useLocation();
  const wid = paramWid ?? auth.activeWorkspace ?? auth.user?.memberships[0]?.workspace_id;

  const engs = useQuery({
    queryKey: ["engagements", wid],
    queryFn: async () =>
      (await api.get<any[]>(`/workspaces/${wid}/engagements`)).data,
    enabled: !!wid,
    refetchInterval: 60_000,
  });

  const assets = useQuery({
    queryKey: ["assets-count", wid],
    queryFn: async () =>
      (await api.get<any[]>(`/workspaces/${wid}/assets?limit=1`)).data,
    enabled: !!wid,
    refetchInterval: 60_000,
  });

  const reports = useQuery({
    queryKey: ["reports", wid],
    queryFn: async () => (await api.get<any[]>(`/reports`)).data,
    enabled: !!wid,
    refetchInterval: 60_000,
  });

  // Hide on the report editor where vertical space is at a premium.
  if (!forceVisible && /\/reports\/[^/]+\/edit/.test(location.pathname)) {
    return null;
  }

  // For finding count we use the engagement aggregate (eng.findings_total)
  // rather than walking every engagement's findings, which scales poorly.
  const findingsTotal = (engs.data ?? []).reduce(
    (acc, e) => acc + (e.findings_total ?? 0),
    0
  );

  const formatCount = (n: number | undefined) => {
    if (n == null) return "—";
    if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
    return n.toString();
  };

  const items: { icon: AppleIconName; value: string; label: string }[] = [
    {
      icon: "rect-list",
      value: formatCount(engs.data?.length),
      label: "engagement" + (engs.data?.length === 1 ? "" : "s"),
    },
    {
      icon: "bug",
      value: formatCount(findingsTotal),
      label: "finding" + (findingsTotal === 1 ? "" : "s"),
    },
    {
      icon: "server",
      value: formatCount(assets.data?.length),
      label: "asset" + (assets.data?.length === 1 ? "" : "s"),
    },
    {
      icon: "activity",
      value: formatCount(reports.data?.length),
      label: "report" + (reports.data?.length === 1 ? "" : "s"),
    },
  ];

  const workspaceName = auth.activeWorkspace
    ? auth.user?.memberships.find((m) => m.workspace_id === auth.activeWorkspace)?.workspace_name ?? "Workspace"
    : "—";

  return (
    <div
      className={cn(
        "shrink-0 h-7 glass border-t border-white/[0.06]",
        "px-3 flex items-center gap-4 text-[11px] text-fg-muted",
        "select-none",
        className
      )}
      role="status"
      aria-label="Workspace summary"
    >
      <span className="flex items-center gap-1.5 text-fg-muted">
        <span
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            auth.user ? "bg-emerald-400" : "bg-amber-400"
          )}
        />
        {auth.user ? "Live" : "Idle"}
      </span>
      <span className="text-fg-subtle">·</span>
      {items.map((it, i) => {
        return (
          <span key={i} className="inline-flex items-center gap-1.5">
            <AppleIcon name={it.icon} size={11} className="text-fg-subtle" />
            <span className="text-fg font-medium tabular-nums">{it.value}</span>
            <span>{it.label}</span>
            {i < items.length - 1 && (
              <span className="text-fg-subtle ml-2.5">·</span>
            )}
          </span>
        );
      })}
      <span className="ml-auto text-fg-subtle font-mono text-[10px]">
        {workspaceName}
      </span>
    </div>
  );
}
