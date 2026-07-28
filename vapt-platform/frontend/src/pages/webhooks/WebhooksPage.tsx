import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { formatDate } from "../../lib/cn";
import type { WebhookDelivery, WebhookEndpoint } from "../../types";
import { Link2, Plus, Send, Zap } from "lucide-react";

const EVENT_OPTIONS = [
  "ingestion.completed",
  "finding.created",
  "finding.triaged",
  "report.rendered",
  "report.approved",
  "retest.completed",
];

export default function WebhooksPage() {
  const { wid } = useParams();
  const auth = useAuth();
  const workspaceId = wid ?? auth.activeWorkspace;
  const qc = useQueryClient();

  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [events, setEvents] = useState<string[]>([]);

  const endpoints = useQuery({
    queryKey: ["webhooks", workspaceId],
    queryFn: async () =>
      (await api.get<WebhookEndpoint[]>(`/workspaces/${workspaceId}/webhooks`)).data,
    enabled: !!workspaceId,
  });

  const deliveries = useQuery({
    queryKey: ["webhook-deliveries", workspaceId],
    queryFn: async () =>
      (await api.get<WebhookDelivery[]>(`/workspaces/${workspaceId}/webhooks/deliveries`)).data,
    enabled: !!workspaceId,
    refetchInterval: 10_000,
  });

  const create = useMutation({
    mutationFn: async () =>
      api.post(`/workspaces/${workspaceId}/webhooks`, { name, url, events }),
    onSuccess: () => {
      toast.success("Webhook created");
      setName("");
      setUrl("");
      setEvents([]);
      qc.invalidateQueries({ queryKey: ["webhooks", workspaceId] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Failed"),
  });

  const del = useMutation({
    mutationFn: async (eid: string) =>
      api.delete(`/workspaces/${workspaceId}/webhooks/${eid}`),
    onSuccess: () => {
      toast.success("Deleted");
      qc.invalidateQueries({ queryKey: ["webhooks", workspaceId] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Delete failed"),
  });

  const test = useMutation({
    mutationFn: async (eid: string) =>
      api.post(`/workspaces/${workspaceId}/webhooks/${eid}/test`),
    onSuccess: () => {
      toast.success("Test event sent");
      qc.invalidateQueries({ queryKey: ["webhook-deliveries", workspaceId] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Test failed"),
  });

  return (
    <div className="space-y-4 max-w-[1400px] mx-auto p-4 min-w-0">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <Link2 size={20} className="text-finder-blue" /> Webhooks
          </h1>
          <p className="text-sm text-ink-muted">
            Push platform events to your CI / SIEM / Slack
          </p>
        </div>
      </div>

      <div className="panel p-4">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-1.5">
          <Plus size={14} /> New webhook
        </h3>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
          className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 items-end"
        >
          <div>
            <label className="text-xs text-ink-muted">Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="slack-alerts"
              className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-sm mt-1"
            />
          </div>
          <div>
            <label className="text-xs text-ink-muted">URL</label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
              placeholder="https://hooks.slack.com/…"
              className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-sm mt-1"
            />
          </div>
          <div className="col-span-3">
            <label className="text-xs text-ink-muted">Events</label>
            <div className="mt-1 flex flex-wrap gap-1">
              {EVENT_OPTIONS.map((ev) => {
                const on = events.includes(ev);
                return (
                  <button
                    type="button"
                    key={ev}
                    onClick={() =>
                      setEvents((cur) => (on ? cur.filter((x) => x !== ev) : [...cur, ev]))
                    }
                    className={
                      on
                        ? "chip chip-info border-finder-blue/30"
                        : "chip chip-muted hover:border-finder-blue font-mono"
                    }
                  >
                    {ev}
                  </button>
                );
              })}
            </div>
          </div>
          <button
            type="submit"
            disabled={create.isPending || !name || !url}
            className="col-span-3 sm:col-span-1 sm:col-start-3 bg-finder-blue hover:bg-folder-to text-white rounded-lg px-3 py-1.5 text-sm disabled:opacity-50"
          >
            {create.isPending ? "Creating…" : "Create"}
          </button>
        </form>
      </div>

      <div className="panel overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-ink-muted text-xs bg-paper-soft">
            <tr className="text-left">
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">URL</th>
              <th className="px-3 py-2">Events</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Last delivery</th>
              <th className="px-3 py-2">Failures</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {(endpoints.data ?? []).map((ep) => (
              <tr key={ep.id} className="border-t border-hairline">
                <td className="px-3 py-2 font-medium">{ep.name}</td>
                <td className="px-3 py-2 font-mono text-xs text-ink-muted truncate max-w-xs">
                  {ep.url}
                </td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-1">
                    {ep.events.map((ev) => (
                      <span key={ev} className="chip chip-muted font-mono text-[10px]">
                        {ev}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-3 py-2">
                  {ep.active ? (
                    <span className="pill bg-emerald-50 text-emerald-700 border-emerald-500/30">
                      active
                    </span>
                  ) : (
                    <span className="pill bg-paper-soft text-ink-muted border-hairline">
                      paused
                    </span>
                  )}
                </td>
                <td className="px-3 py-2 text-ink-muted text-xs">
                  {formatDate(ep.last_delivery_at)}
                </td>
                <td className="px-3 py-2 font-mono text-xs">
                  {ep.failure_count > 0 ? (
                    <span className="text-rose-700">{ep.failure_count}</span>
                  ) : (
                    <span className="text-ink-subtle">0</span>
                  )}
                </td>
                <td className="px-3 py-2">
                  <div className="flex gap-1">
                    <button
                      onClick={() => test.mutate(ep.id)}
                      disabled={test.isPending}
                      className="text-xs px-2 py-1 bg-finder-blue-soft text-finder-blue border border-finder-blue/30 rounded hover:bg-finder-blue/25 flex items-center gap-1"
                    >
                      <Zap size={10} /> Test
                    </button>
                    <button
                      onClick={() => del.mutate(ep.id)}
                      className="text-xs px-2 py-1 bg-rose-50 text-rose-700 border border-rose-500/30 rounded hover:bg-rose-100"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {(endpoints.data ?? []).length === 0 && (
              <tr>
                <td colSpan={7} className="text-center text-ink-muted py-8">
                  No webhook endpoints yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="panel p-4">
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-1.5">
          <Send size={14} /> Recent deliveries
        </h3>
        <table className="w-full text-sm">
          <thead className="text-ink-muted text-xs bg-paper-soft">
            <tr className="text-left">
              <th className="px-2 py-2">Event</th>
              <th className="px-2 py-2">Status</th>
              <th className="px-2 py-2">HTTP</th>
              <th className="px-2 py-2">Attempts</th>
              <th className="px-2 py-2">Sent at</th>
            </tr>
          </thead>
          <tbody>
            {(deliveries.data ?? []).slice(0, 30).map((d) => (
              <tr key={d.id} className="border-t border-hairline">
                <td className="px-2 py-2 font-mono text-xs">{d.event}</td>
                <td className="px-2 py-2">
                  <span
                    className={
                      d.status === "success"
                        ? "pill bg-emerald-50 text-emerald-700 border-emerald-500/30"
                        : d.status === "failed"
                          ? "pill bg-rose-50 text-rose-700 border-rose-500/30"
                          : "pill bg-amber-50 text-amber-700 border-amber-500/30"
                    }
                  >
                    {d.status}
                  </span>
                </td>
                <td className="px-2 py-2 font-mono text-xs">
                  {d.response_status ?? "—"}
                </td>
                <td className="px-2 py-2 font-mono text-xs">{d.attempts}</td>
                <td className="px-2 py-2 text-ink-muted text-xs">
                  {formatDate(d.created_at)}
                </td>
              </tr>
            ))}
            {(deliveries.data ?? []).length === 0 && (
              <tr>
                <td colSpan={5} className="text-center text-ink-muted py-6">
                  No deliveries yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
