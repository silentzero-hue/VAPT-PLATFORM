import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import AppleIcon, { type AppleIconName } from "../../components/ui/AppleIcon";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { cn, formatDate } from "../../lib/cn";
import type { Asset } from "../../types";
import Card from "../../components/ui/Card";
import EmptyState from "../../components/ui/EmptyState";
import Toolbar from "../../components/ui/Toolbar";

const TYPE_ICON: Record<string, AppleIconName> = {
  host: "server",
  domain: "globe",
  url: "link",
  ip: "server",
  cloud: "cloud",
  database: "server",
  mobile: "smartphone",
  person: "user",
  app: "building",
};

const CRIT_PILL: Record<string, string> = {
  critical: "chip-critical",
  high: "chip-high",
  medium: "chip-medium",
  low: "chip-low",
};

export default function AssetsPage() {
  const { wid } = useParams();
  const auth = useAuth();
  const workspaceId = wid ?? auth.activeWorkspace;
  const a = useQuery({
    queryKey: ["assets", workspaceId],
    queryFn: async () =>
      (await api.get<Asset[]>(`/workspaces/${workspaceId}/assets?limit=200`)).data,
    enabled: !!workspaceId,
  });

  return (
    <div className="space-y-4 max-w-[1400px] mx-auto">
      <Toolbar
        left={
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Assets</h1>
            <p className="text-sm text-fg-muted">
              Hosts, URLs, apps, and people in scope.
            </p>
          </div>
        }
        right={
          <span className="text-xs text-fg-muted">
            {(a.data ?? []).length} item{(a.data ?? []).length === 1 ? "" : "s"}
          </span>
        }
      />

      {(a.data ?? []).length === 0 ? (
        <Card>
          <EmptyState
            iconName="server"
            title="No assets yet"
            description="Ingest a scan to populate your asset inventory."
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {(a.data ?? []).map((x) => {
            const iconName = TYPE_ICON[x.type] ?? "building";
            return (
              <Card key={x.id} className="card-hover p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="h-9 w-9 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center shrink-0">
                    <AppleIcon name={iconName} size={16} className="text-accent" />
                  </div>
                  <span className={cn("chip", CRIT_PILL[x.criticality] ?? "chip-muted")}>
                    {x.criticality}
                  </span>
                </div>
                <div className="mt-3 font-mono text-xs truncate" title={x.value}>
                  {x.value}
                </div>
                <div className="text-[10px] text-fg-muted uppercase tracking-wider mt-0.5">
                  {x.type}
                </div>
                <div className="mt-3 flex items-center justify-between text-[10px] text-fg-muted">
                  {x.port ? (
                    <span className="font-mono">
                      :{x.port}/{x.protocol ?? "tcp"}
                    </span>
                  ) : (
                    <span className="font-mono text-fg-subtle">—</span>
                  )}
                  <span className="font-mono">{formatDate(x.last_seen)}</span>
                </div>
                {x.owner && (
                  <div className="mt-2 text-[10px] text-fg-muted truncate">owner: {x.owner}</div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
