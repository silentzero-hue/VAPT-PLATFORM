import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import AppleIcon from "../ui/AppleIcon";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { cn } from "../../lib/cn";
import type { Comment } from "../../types";

export function CommentsPanel({ findingId }: { findingId: string }) {
  const qc = useQueryClient();
  const [body, setBody] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editBody, setEditBody] = useState("");

  const list = useQuery({
    queryKey: ["comments", findingId],
    queryFn: async () => (await api.get<Comment[]>(`/findings/${findingId}/comments`)).data,
  });

  const create = useMutation({
    mutationFn: async () => api.post(`/findings/${findingId}/comments`, { body }),
    onSuccess: () => { setBody(""); qc.invalidateQueries({ queryKey: ["comments", findingId] }); },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Post failed"),
  });
  const update = useMutation({
    mutationFn: async (vars: { id: string; body: string }) =>
      api.patch(`/comments/${vars.id}`, { body: vars.body }),
    onSuccess: () => { setEditing(null); qc.invalidateQueries({ queryKey: ["comments", findingId] }); },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Update failed"),
  });
  const del = useMutation({
    mutationFn: async (id: string) => api.delete(`/comments/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["comments", findingId] }),
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Delete failed"),
  });

  // highlight @mentions
  const renderBody = (text: string) => {
    const parts = text.split(/(@[a-zA-Z0-9._+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/g);
    return parts.map((p, i) =>
      p.startsWith("@") ? (
        <span key={i} className="text-finder-blue font-medium">{p}</span>
      ) : (
        <span key={i}>{p}</span>
      )
    );
  };

  return (
    <div className="panel p-4 space-y-3">
      <h3 className="text-sm font-semibold flex items-center gap-2">
        <AppleIcon name="message" size={14} /> Discussion
        <span className="text-ink-muted text-xs font-normal">({list.data?.length ?? 0})</span>
      </h3>

      <div className="space-y-2 max-h-96 overflow-y-auto">
        {(list.data ?? []).map((c) => (
          <div key={c.id} className="border-t border-hairline pt-2">
            <div className="flex items-start gap-2">
              <div className="h-7 w-7 rounded-full bg-finder-blue/20 border border-finder-blue/30 text-finder-blue text-xs flex items-center justify-center font-mono">
                {(c.author_id ?? "?").slice(0, 2)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs text-ink-muted flex items-center gap-2">
                  <span className="font-mono">{c.author_id?.slice(0, 8) ?? "system"}</span>
                  <span>·</span>
                  <span>{formatDistanceToNow(new Date(c.created_at), { addSuffix: true })}</span>
                  {c.edited_at && <span className="italic">(edited)</span>}
                </div>
                {editing === c.id ? (
                  <div className="mt-1 space-y-2">
                    <textarea
                      value={editBody}
                      onChange={(e) => setEditBody(e.target.value)}
                      className="w-full bg-paper-soft border border-hairline focus:border-finder-blue rounded p-2 text-sm outline-none"
                      rows={2}
                    />
                    <div className="flex gap-2">
                      <button onClick={() => update.mutate({ id: c.id, body: editBody })}
                        className="bg-finder-blue hover:bg-folder-to text-white rounded px-2 py-1 text-xs">Save</button>
                      <button onClick={() => setEditing(null)} className="text-ink-muted text-xs px-2">Cancel</button>
                    </div>
                  </div>
                ) : (
                  <div className={cn("text-sm whitespace-pre-wrap mt-1", c.deleted && "italic text-ink-muted")}>
                    {c.deleted ? "[deleted]" : renderBody(c.body)}
                  </div>
                )}
                {!c.deleted && editing !== c.id && (
                  <div className="mt-1 flex gap-2 text-xs">
                    <button onClick={() => { setEditing(c.id); setEditBody(c.body); }}
                      className="text-ink-muted hover:text-ink flex items-center gap-1">
                      <AppleIcon name="pencil" size={10} /> edit
                    </button>
                    <button onClick={() => del.mutate(c.id)}
                      className="text-ink-muted hover:text-rose-700 flex items-center gap-1">
                      <AppleIcon name="trash" size={10} /> delete
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
        {(list.data ?? []).length === 0 && (
          <div className="text-center text-ink-muted text-xs py-4">No comments yet</div>
        )}
      </div>

      <div className="border-t border-hairline pt-3">
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Write a comment. Use @user@email to mention."
          rows={2}
          className="w-full bg-paper-soft border border-hairline focus:border-finder-blue rounded p-2 text-sm outline-none"
        />
        <div className="flex items-center justify-between mt-2">
          <div className="text-[10px] text-ink-muted flex items-center gap-1">
            <AppleIcon name="at-symbol" size={10} /> mentions notify the user in-app + email
          </div>
          <button
            onClick={() => create.mutate()}
            disabled={!body.trim() || create.isPending}
            className="bg-finder-blue hover:bg-folder-to text-white rounded px-3 py-1 text-sm disabled:opacity-50"
          >
            Post
          </button>
        </div>
      </div>
    </div>
  );
}
