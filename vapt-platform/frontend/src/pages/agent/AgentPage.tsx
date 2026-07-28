import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Activity, Bot, Check, Sparkles, Workflow } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import type { Engagement } from "../../types";

/**
 * Agent Review — shows the streaming log of an agent run alongside
 * the AI-drafted vulnerabilities. Human-approval action lives on the
 * Report detail page; this view is the post-run review board.
 */
export default function AgentPage() {
  const { wid } = useParams();
  const auth = useAuth();
  const workspaceId = wid ?? auth.activeWorkspace;
  const engs = useQuery({
    queryKey: ["engagements", workspaceId],
    queryFn: async () => (await api.get<Engagement[]>(`/workspaces/${workspaceId}/engagements`)).data,
    enabled: !!workspaceId,
  });
  const [selected, setSelected] = useState<string | null>(null);
  const eid = selected ?? engs.data?.[0]?.id;

  const vulns = useQuery({
    queryKey: ["vulns", workspaceId, "ai-drafted"],
    queryFn: async () => {
      const r = await api.get<any[]>(`/workspaces/${workspaceId}/vulnerabilities?limit=200`);
      return r.data.filter((v: any) => v.ai_draft_impact || v.ai_draft_recommendation);
    },
    enabled: !!workspaceId,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2"><Sparkles size={20} className="text-accent" /> Agent Review</h1>
          <p className="text-sm text-fg-muted">
            The agent drafts via MCP tools. It never reaches <code>approved</code> on its own — that's your job.
          </p>
        </div>
        <Link
          to={`/workspaces/${workspaceId}/agent/live`}
          className="bg-accent/15 hover:bg-accent/25 text-accent border border-accent/30 rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5"
        >
          <Activity size={14} /> Live run feed
        </Link>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="panel p-4 col-span-1">
          <h3 className="text-sm font-semibold mb-2">Engagement</h3>
          <select
            value={eid ?? ""}
            onChange={(e) => setSelected(e.target.value)}
            className="w-full bg-bg-soft border border-border-soft rounded-lg px-2 py-1.5 text-sm"
          >
            {(engs.data ?? []).map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
          <h3 className="text-sm font-semibold mt-4 mb-2 flex items-center gap-1.5"><Bot size={14} /> AI-drafted vulnerabilities</h3>
          <div className="text-xs text-fg-muted mb-2">{vulns.data?.length ?? 0} have a draft</div>
          <ul className="space-y-1 max-h-[60vh] overflow-y-auto">
            {(vulns.data ?? []).map((v) => (
              <li key={v.id} className="text-sm flex items-center justify-between border-t border-border-soft py-1.5">
                <div className="truncate pr-2">{v.title}</div>
                {v.ai_draft_approved ? (
                  <span className="pill bg-emerald-500/15 text-emerald-300 border-emerald-500/30"><Check size={10} /> approved</span>
                ) : (
                  <span className="pill bg-amber-500/15 text-amber-300 border-amber-500/30">pending</span>
                )}
              </li>
            ))}
          </ul>
        </div>
        <div className="panel p-4 col-span-2">
          <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5"><Workflow size={14} /> Agent workflow</h3>
          <p className="text-xs text-fg-muted mb-4">
            Read-only trace of the deterministic agent loop. Use the per-vulnerability page
            to edit / approve drafts; the report page is the only path to <code>approved</code>.
          </p>
          <ol className="space-y-2 text-sm">
            {[
              ["list_findings", "Fetch findings for the engagement."],
              ["get_vulnerability", "Pull full vuln details, including linked_assets."],
              ["check_duplicate", "Sanity pass on each vuln's wording."],
              ["draft_finding_narrative", "Persist Impact + Recommendation per unique vuln."],
              ["generate_exec_summary_stats", "Aggregate severity counts & top-risk assets."],
              ["render_report", "Render the docx into S3 (status=draft)."],
              ["flag_for_human_review", "Hand off. Agent terminates here."],
            ].map(([t, d], i) => (
              <li key={t} className="flex items-start gap-3 border-t border-border-soft py-2">
                <span className="h-5 w-5 rounded-full bg-accent/15 border border-accent/30 text-accent text-[11px] font-mono flex items-center justify-center">{i + 1}</span>
                <div>
                  <div className="font-mono text-xs text-accent">mcp.{t}</div>
                  <div className="text-fg-muted text-xs">{d}</div>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  );
}
