import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { formatDate } from "../../lib/cn";
import type { AgentEvent, AgentRun } from "../../types";
import { Activity, Zap, Plug, Wrench, X } from "lucide-react";

function wsUrl(sessionId: string) {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/api/v1/agent/ws/${sessionId}`;
}

export default function AgentLivePage() {
  const { wid } = useParams();
  const auth = useAuth();
  const workspaceId = wid ?? auth.activeWorkspace;

  const [activeSession, setActiveSession] = useState<string | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const connectIdRef = useRef(0);

  const runs = useQuery({
    queryKey: ["agent-runs", workspaceId],
    queryFn: async () => {
      const res = await api.get<AgentRun[]>(`/workspaces/${workspaceId}/agent/runs`);
      return res.data;
    },
    enabled: !!workspaceId,
    refetchInterval: 5_000,
  });

  const meta = useQuery({
    queryKey: ["agent-run", activeSession],
    queryFn: async () =>
      (await api.get<AgentRun>(`/agent/runs/${activeSession}`)).data,
    enabled: !!activeSession,
  });

  const connect = (sessionId: string) => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setEvents([]);
    setActiveSession(sessionId);
    setConnected(false);
    const myId = ++connectIdRef.current;
    const ws = new WebSocket(wsUrl(sessionId));
    wsRef.current = ws;
    ws.onopen = () => {
      if (myId !== connectIdRef.current) return;
      setConnected(true);
      toast.success("Stream connected");
    };
    ws.onmessage = (msg) => {
      if (myId !== connectIdRef.current) return;
      try {
        const evt: AgentEvent = JSON.parse(msg.data);
        setEvents((cur) => [...cur, evt]);
      } catch {
        /* ignore non-JSON frames */
      }
    };
    ws.onerror = () => {
      if (myId !== connectIdRef.current) return;
      toast.error("Stream error");
    };
    ws.onclose = () => {
      if (myId !== connectIdRef.current) return;
      setConnected(false);
      toast.info("Stream closed");
    };
  };

  const disconnect = () => {
    wsRef.current?.close();
    wsRef.current = null;
    setConnected(false);
  };

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  return (
    <div className="space-y-4 max-w-[1400px] mx-auto p-4 min-w-0">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <Activity size={20} className="text-finder-blue" /> Agent live
          </h1>
          <p className="text-sm text-ink-muted">
            Replay the streaming trace of an agent run
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 min-w-0">
        <div className="panel p-4 lg:col-span-1 min-w-0">
          <h3 className="text-sm font-semibold mb-3">Recent runs</h3>
          <ul className="space-y-1.5">
            {(runs.data ?? []).map((r) => {
              const isActive = activeSession === r.session_id;
              return (
                <li
                  key={r.id}
                  className={
                    isActive
                      ? "border border-finder-blue/30 rounded-lg p-2 bg-finder-blue/5"
                      : "border border-hairline rounded-lg p-2"
                  }
                >
                  <div className="flex items-center justify-between">
                    <div className="text-xs font-mono text-ink-muted truncate pr-2">
                      {r.session_id.slice(0, 12)}…
                    </div>
                    <span
                      className={
                        r.status === "completed"
                          ? "pill bg-sev-low-soft text-sev-low-strong border-sev-low"
                          : r.status === "failed"
                            ? "pill bg-sev-critical-soft text-sev-critical-strong border-sev-critical"
                            : r.status === "cancelled"
                              ? "pill bg-paper-soft text-ink-muted border-hairline"
                              : "pill bg-sev-medium-soft text-sev-medium-strong border-sev-medium"
                      }
                    >
                      {r.status}
                    </span>
                  </div>
                  <div className="text-[11px] text-ink-muted mt-1 flex gap-2">
                    <span>iter {r.iterations}</span>
                    <span>·</span>
                    <span>draft {r.vulns_drafted}</span>
                    <span>·</span>
                    <span>{formatDate(r.started_at)}</span>
                  </div>
                  <div className="mt-2">
                    {isActive && connected ? (
                      <button
                        onClick={disconnect}
                        className="text-xs px-2 py-1 bg-sev-critical-soft text-sev-critical-strong border border-sev-critical rounded hover:bg-sev-critical/15 flex items-center gap-1"
                      >
                        <X size={10} /> Disconnect
                      </button>
                    ) : (
                      <button
                        onClick={() => connect(r.session_id)}
                        className="text-xs px-2 py-1 bg-finder-blue-soft text-finder-blue border border-finder-blue/30 rounded hover:bg-finder-blue/25 flex items-center gap-1"
                      >
                        <Zap size={10} /> Connect
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
            {(runs.data ?? []).length === 0 && (
              <li className="text-ink-muted text-center py-6 text-sm">No runs yet</li>
            )}
          </ul>
        </div>

        <div className="panel p-4 lg:col-span-2 min-w-0">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold flex items-center gap-1.5">
              <Plug size={14} /> Live stream
              {activeSession && (
                <span className="ml-2 font-mono text-[10px] text-ink-muted">
                  {activeSession.slice(0, 16)}…
                </span>
              )}
              {connected && (
                <span className="ml-2 pill bg-sev-low-soft text-sev-low-strong border-sev-low">
                  connected
                </span>
              )}
            </h3>
            {meta.data && (
              <div className="text-[11px] text-ink-muted">
                started {formatDate(meta.data.started_at)} ·{" "}
                {meta.data.finished_at
                  ? `ended ${formatDate(meta.data.finished_at)}`
                  : "still running"}
              </div>
            )}
          </div>
          <div className="bg-paper-soft border border-hairline rounded-lg p-2 max-h-[60vh] overflow-y-auto font-mono text-xs space-y-1">
            {events.length === 0 && (
              <div className="text-ink-muted text-center py-10">
                {activeSession
                  ? "Waiting for events…"
                  : "Pick a run on the left and press Connect."}
              </div>
            )}
            {events.map((e, i) => (
              <div
                key={i}
                className="border-t border-hairline first:border-t-0 py-1.5 px-1"
              >
                {e.type === "tool_call" && (
                  <div>
                    <div className="text-finder-blue flex items-center gap-1.5">
                      <Wrench size={10} /> mcp.{e.name}
                    </div>
                    <pre className="text-ink-muted whitespace-pre-wrap break-all ml-4">
                      {JSON.stringify(e.args, null, 2)}
                    </pre>
                  </div>
                )}
                {e.type === "tool_result" && (
                  <div>
                    <div className="text-sev-low-strong flex items-center gap-1.5">
                      <Wrench size={10} /> ← {e.name}
                    </div>
                    <pre className="text-ink-muted whitespace-pre-wrap break-all ml-4">
                      {JSON.stringify(e.result, null, 2)}
                    </pre>
                  </div>
                )}
                {e.type === "message" && (
                  <div>
                    <span className="text-ink-muted">[{e.role}]</span> {e.content}
                  </div>
                )}
                {e.type === "status" && (
                  <div className="text-sev-medium-strong">status: {e.status}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
