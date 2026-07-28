import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import AppleIcon, { type AppleIconName } from "../../components/ui/AppleIcon";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useParams } from "react-router-dom";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { cn, formatDate, getDominantSeverity, SEVERITY_BAR, SEVERITY_TEXT } from "../../lib/cn";
import type { Engagement, Finding, Severity } from "../../types";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";

const SEV_COLORS: Record<string, string> = {
  critical: "#ff3b30",
  high: "#ff9500",
  medium: "#ffcc00",
  low: "#34c759",
  info: "#5e5ce6",
};

const SEV_ORDER: Severity[] = ["critical", "high", "medium", "low", "info"];

export default function DashboardPage() {
  const { wid } = useParams();
  const auth = useAuth();
  const navigate = useNavigate();
  const workspaceId = wid ?? auth.activeWorkspace;
  const workspaceName = auth.user?.memberships.find((m) => m.workspace_id === workspaceId)?.workspace_name ?? "Workspace";

  const engs = useQuery({
    queryKey: ["engagements", workspaceId],
    queryFn: async () =>
      (await api.get<Engagement[]>(`/workspaces/${workspaceId}/engagements`)).data,
    enabled: !!workspaceId,
  });

  const allFindings = useQuery({
    queryKey: ["dashboard-findings", workspaceId],
    queryFn: async () => {
      if (!engs.data) return [] as Finding[];
      const results = await Promise.all(
        engs.data.map((e) =>
          api.get<Finding[]>(`/engagements/${e.id}/findings?limit=5000`)
        )
      );
      return results.flatMap((r) => r.data);
    },
    enabled: !!engs.data,
  });

  const sevCounts = (allFindings.data ?? []).reduce<Record<string, number>>((acc, f) => {
    const s = f.effective_severity;
    acc[s] = (acc[s] ?? 0) + 1;
    return acc;
  }, {});
  const sevData = SEV_ORDER
    .map((s) => ({ name: s, value: sevCounts[s] ?? 0 }))
    .filter((d) => d.value > 0);

  const slaBreached = (allFindings.data ?? []).filter((f) => f.sla_breached).length;
  const open = (allFindings.data ?? []).filter(
    (f) =>
      !["resolved", "false_positive", "accepted_risk", "deferred", "remediated_pending_confirmation"].includes(
        f.status
      )
  ).length;
  const regressed = (allFindings.data ?? []).filter((f) => f.status === "regressed").length;
  const recent = (allFindings.data ?? [])
    .slice()
    .sort((a, b) => (b.last_seen ?? "").localeCompare(a.last_seen ?? ""))
    .slice(0, 6);

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl bg-paper-strong border border-hairline shadow-card p-6">
        <div
          className="absolute inset-0 opacity-40 pointer-events-none"
          style={{
            background:
              "radial-gradient(120% 100% at 100% 0%, rgba(10,132,255,0.10) 0%, transparent 60%)",
          }}
        />
        <div className="relative flex items-end justify-between gap-4 flex-wrap">
          <div className="min-w-0">
            <div className="text-xs uppercase tracking-wider text-ink-muted mb-1">
              Workspace overview
            </div>
            <h1 className="text-3xl font-semibold tracking-tight truncate text-ink">{workspaceName}</h1>
            <p className="text-sm text-ink-muted mt-1">
              Live posture across {(engs.data ?? []).length} engagement
              {(engs.data ?? []).length === 1 ? "" : "s"} in this workspace.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => navigate(`/workspaces/${workspaceId}/engagements`)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-sm",
                "bg-finder-blue text-white hover:bg-folder-to",
                "transition-all duration-200 ease-out active:scale-[0.98]"
              )}
            >
              <AppleIcon name="rect-list" size={14} /> View engagements
            </button>
          </div>
        </div>
      </div>

      {/* Stat row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatTile
          label="Open findings"
          value={open}
          accent="text-finder-blue"
          icon="bug"
          gradient="from-finder-blue/15 to-transparent"
        />
        <StatTile
          label="SLA breached"
          value={slaBreached}
          accent="text-sev-high"
          icon="exclamation-triangle"
          gradient="from-sev-high/15 to-transparent"
        />
        <StatTile
          label="Regressed"
          value={regressed}
          accent="text-sev-critical"
          icon="activity"
          gradient="from-sev-critical/15 to-transparent"
        />
        <StatTile
          label="Engagements"
          value={(engs.data ?? []).length}
          accent="text-sev-low"
          icon="shield"
          gradient="from-sev-low/15 to-transparent"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="p-4 lg:col-span-1">
          <h2 className="text-sm font-semibold mb-3">Severity distribution</h2>
          <div className="h-64">
            {sevData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-ink-muted">
                No findings yet
              </div>
            ) : (
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={sevData} dataKey="value" nameKey="name" outerRadius={90} innerRadius={50} paddingAngle={2}>
                    {sevData.map((d) => <Cell key={d.name} fill={SEV_COLORS[d.name] ?? "#666"} />)}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: "#ffffff", border: "1px solid rgba(0,0,0,0.10)", borderRadius: 8, color: "#26251f" }}
                    itemStyle={{ color: "#26251f" }}
                    labelStyle={{ color: "#26251f" }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11, color: "#6b6a63" }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
        <Card className="p-4 lg:col-span-2">
          <h2 className="text-sm font-semibold mb-3 flex items-center gap-1.5">
            <AppleIcon name="trending-up" size={14} /> Findings by engagement
          </h2>
          <div className="h-64">
            {((engs.data ?? []).length === 0) ? (
              <div className="h-full flex items-center justify-center text-xs text-ink-muted">
                No engagements to chart
              </div>
            ) : (
              <ResponsiveContainer>
                <BarChart
                  data={(engs.data ?? []).map((e) => ({
                    name: e.code,
                    total: e.findings_total ?? 0,
                  }))}
                >
                  <CartesianGrid stroke="rgba(0,0,0,0.08)" strokeDasharray="3 3" />
                  <XAxis dataKey="name" stroke="#9c9a92" tick={{ fontSize: 11 }} />
                  <YAxis stroke="#9c9a92" tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ background: "#ffffff", border: "1px solid rgba(0,0,0,0.10)", borderRadius: 8, color: "#26251f" }}
                    itemStyle={{ color: "#26251f" }}
                    labelStyle={{ color: "#26251f" }}
                  />
                  <Bar dataKey="total" fill="#0a84ff" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Card>
      </div>

      {/* Engagements grid + recent activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">Engagements</h2>
            <span className="text-xs text-ink-muted">
              {(engs.data ?? []).length} item{(engs.data ?? []).length === 1 ? "" : "s"}
            </span>
          </div>
          {(engs.data ?? []).length === 0 ? (
            <Card>
              <EmptyState
                iconName="rect-list"
                title="No engagements yet"
                description="Create an engagement to start ingesting scans and tracking findings."
                cta={
                  <button
                    onClick={() => navigate(`/workspaces/${workspaceId}/engagements`)}
                    className="rounded-full bg-finder-blue hover:bg-folder-to text-white px-4 py-1.5 text-sm transition-colors duration-200"
                  >
                    Browse engagements
                  </button>
                }
              />
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {(engs.data ?? []).map((e) => {
                const dom = getDominantSeverity(e.severity_breakdown);
                return (
                  <Card
                    key={e.id}
                    onClick={() =>
                      navigate(`/workspaces/${workspaceId}/engagements/${e.id}`)
                    }
                    className="card-hover p-4"
                    ariaLabel={`Open ${e.name}`}
                  >
                    {dom && (
                      <div className={cn("sev-bar", SEVERITY_BAR[dom] ?? "bg-sev-info")} />
                    )}
                    <div className="flex items-center justify-between gap-2">
                      <div className="font-mono text-[11px] text-ink-muted truncate">
                        {e.code}
                      </div>
                      <span className="pill pill-muted shrink-0">{e.status}</span>
                    </div>
                    <div className="mt-1 text-base font-semibold leading-tight line-clamp-2">
                      {e.name}
                    </div>
                    <div className="text-xs text-ink-muted truncate">{e.client}</div>
                    <div className="mt-3 flex items-center gap-3 text-[11px] text-ink-muted">
                      <span className="uppercase tracking-wider">{e.type}</span>
                      <span className="text-ink-subtle">·</span>
                      <span className="font-mono">{e.findings_total ?? 0} findings</span>
                    </div>
                    {e.severity_breakdown && (
                      <div className="mt-3 flex gap-1 flex-wrap">
                        {Object.entries(e.severity_breakdown)
                          .filter(([, n]) => n > 0)
                          .map(([sev, n]) => (
                            <span key={sev} className={cn("chip", `chip-${sev}`)}>
                              {sev} {n}
                            </span>
                          ))}
                      </div>
                    )}
                  </Card>
                );
              })}
            </div>
          )}
        </div>

        <Card className="p-4 self-start">
          <h2 className="text-sm font-semibold mb-3 flex items-center gap-1.5">
            <AppleIcon name="clock" size={14} /> Recent activity
          </h2>
          {recent.length === 0 ? (
            <div className="text-xs text-ink-muted py-4 text-center">No activity yet</div>
          ) : (
            <ul className="space-y-3">
              {recent.map((f) => (
                <li
                  key={f.id}
                  className={cn(
                    "relative pl-3 py-1.5 border-l-2",
                    SEVERITY_BAR[f.effective_severity]?.replace("bg-", "border-") ??
                      "border-fg-subtle"
                  )}
                >
                  <div className="text-xs font-medium truncate">
                    {f.vuln_title ?? f.vuln_cve_id ?? "—"}
                  </div>
                  <div className="text-[11px] text-ink-muted flex items-center gap-1.5 mt-0.5">
                    <span className={cn("font-mono", SEVERITY_TEXT[f.effective_severity])}>
                      {f.effective_severity}
                    </span>
                    <span className="text-ink-subtle">·</span>
                    <span className="font-mono truncate">{f.asset_value ?? "—"}</span>
                  </div>
                  <div className="text-[10px] text-ink-subtle mt-0.5">
                    {formatDate(f.last_seen)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

function StatTile({
  label,
  value,
  accent,
  icon,
  gradient,
}: {
  label: string;
  value: number;
  accent: string;
  icon: AppleIconName;
  gradient: string;
}) {
  return (
    <Card className="p-4 relative overflow-hidden">
      <div
        className={cn(
          "absolute inset-0 bg-gradient-to-br opacity-60 pointer-events-none",
          gradient
        )}
      />
      <div className="relative flex items-center justify-between">
        <div className="text-[11px] uppercase tracking-wider text-ink-muted">{label}</div>
        <AppleIcon name={icon} size={14} className={accent} />
      </div>
      <div className={cn("relative text-3xl font-semibold mt-2 tracking-tight", accent)}>
        {value}
      </div>
    </Card>
  );
}
