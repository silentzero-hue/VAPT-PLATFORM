import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import AppleIcon from "../../components/ui/AppleIcon";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { formatDate } from "../../lib/cn";
import type { AgentEvent, AgentRun } from "../../types";

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
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <AppleIcon name="activity" size={20} className="text-accent" /> Agent live
          </h1>
          <p className="text-sm text-fg-muted">
            Replay the streaming trace of an agent run
          </p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="panel p-4 col-span-1">
          <h3 className="text-sm font-semibold mb-3">Recent runs</h3>
          <ul className="space-y-1.5">
            {(runs.data ?? []).map((r) => {
              const isActive = activeSession === r.session_id;
              return (
                <li
                  key={r.id}
                  className={
                    isActive
                      ? "border border-accent/30 rounded-lg p-2 bg-accent/5"
                      : "border border-border-soft rounded-lg p-2"
                  }
                >
                  <div className="flex items-center justify-between">
                    <div className="text-xs font-mono text-fg-muted truncate pr-2">
                      {r.session_id.slice(0, 12)}…
                    </div>
                    <span
                      className={
                        r.status === "completed"
                          ? "pill bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                          : r.status === "failed"
                            ? "pill bg-rose-500/15 text-rose-300 border-rose-500/30"
                            : r.status === "cancelled"
                              ? "pill bg-bg-soft text-fg-muted border-border-soft"
                              : "pill bg-amber-500/15 text-amber-300 border-amber-500/30"
                      }
                    >
                      {r.status}
                    </span>
                  </div>
                  <div className="text-[11px] text-fg-muted mt-1 flex gap-2">
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
                        className="text-xs px-2 py-1 bg-rose-500/15 text-rose-300 border border-rose-500/30 rounded hover:bg-rose-500/25 flex items-center gap-1"
                      >
                        <AppleIcon name="x-mark" size={10} /> Disconnect
                      </button>
                    ) : (
                      <button
                        onClick={() => connect(r.session_id)}
                        className="text-xs px-2 py-1 bg-accent/15 text-accent border border-accent/30 rounded hover:bg-accent/25 flex items-center gap-1"
                      >
                        <AppleIcon name="bolt" size={10} /> Connect
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
            {(runs.data ?? []).length === 0 && (
              <li className="text-fg-muted text-center py-6 text-sm">No runs yet</li>
            )}
          </ul>
        </div>

        <div className="panel p-4 col-span-2">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold flex items-center gap-1.5">
              <AppleIcon name="plug" size={14} /> Live stream
              {activeSession && (
                <span className="ml-2 font-mono text-[10px] text-fg-muted">
                  {activeSession.slice(0, 16)}…
                </span>
              )}
              {connected && (
                <span className="ml-2 pill bg-emerald-500/15 text-emerald-300 border-emerald-500/30">
                  connected
                </span>
              )}
            </h3>
            {meta.data && (
              <div className="text-[11px] text-fg-muted">
                started {formatDate(meta.data.started_at)} ·{" "}
                {meta.data.finished_at
                  ? `ended ${formatDate(meta.data.finished_at)}`
                  : "still running"}
              </div>
            )}
          </div>
          <div className="bg-bg-soft border border-border-soft rounded-lg p-2 max-h-[60vh] overflow-y-auto font-mono text-xs space-y-1">
            {events.length === 0 && (
              <div className="text-fg-muted text-center py-10">
                {activeSession
                  ? "Waiting for events…"
                  : "Pick a run on the left and press Connect."}
              </div>
            )}
            {events.map((e, i) => (
              <div
                key={i}
                className="border-t border-border-soft first:border-t-0 py-1.5 px-1"
              >
                {e.type === "tool_call" && (
                  <div>
                    <div className="text-accent flex items-center gap-1.5">
                      <AppleIcon name="wrench" size={10} /> mcp.{e.name}
                    </div>
                    <pre className="text-fg-muted whitespace-pre-wrap break-all ml-4">
                      {JSON.stringify(e.args, null, 2)}
                    </pre>
                  </div>
                )}
                {e.type === "tool_result" && (
                  <div>
                    <div className="text-emerald-300 flex items-center gap-1.5">
                      <AppleIcon name="wrench" size={10} /> ← {e.name}
                    </div>
                    <pre className="text-fg-muted whitespace-pre-wrap break-all ml-4">
                      {JSON.stringify(e.result, null, 2)}
                    </pre>
                  </div>
                )}
                {e.type === "message" && (
                  <div>
                    <span className="text-fg-muted">[{e.role}]</span> {e.content}
                  </div>
                )}
                {e.type === "status" && (
                  <div className="text-amber-300">status: {e.status}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
