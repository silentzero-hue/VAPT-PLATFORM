import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import AppleIcon from "../../components/ui/AppleIcon";
import { toast } from "sonner";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { cn, formatDate } from "../../lib/cn";
import type {
  BulkSuggestResponse, FindingEdit, FindingSuggestion, Report,
  ReportEditRequest, ReportDraft, Severity,
} from "../../types";

type FindingRow = {
  finding_id: string;
  vuln_id: string;
  title: string;
  cve_id: string | null;
  severity: Severity;
  asset_value: string;
  port: number | null;
  protocol: string | null;
  impact: string;
  recommendation: string;
};

const SEV_OPTIONS: Severity[] = ["critical", "high", "medium", "low", "info"];
const SEV_PILL: Record<Severity, string> = {
  critical: "bg-red-50 text-red-700 border-red-200",
  high: "bg-orange-50 text-orange-700 border-orange-200",
  medium: "bg-amber-50 text-amber-700 border-amber-200",
  low: "bg-yellow-50 text-yellow-700 border-yellow-200",
  info: "bg-indigo-50 text-indigo-700 border-indigo-200",
};

const SUGGEST_DEBOUNCE_MS = 500;

const EDIT_MODE_STYLE_ID = "vapt-edit-mode-style";

const EDIT_MODE_CSS = `
[data-field][contenteditable="true"] {
  cursor: text;
  outline: 1px dashed transparent;
  transition: outline 0.15s, background 0.15s;
}
[data-field][contenteditable="true"]:hover {
  outline: 1px dashed #0a84ff;
  background: rgba(10, 132, 255, 0.06);
}
[data-field][contenteditable="true"]:focus {
  outline: 2px solid #0a84ff;
  outline-offset: -2px;
  background: #fbfaf8;
}
`;

// Read the analyst-narrative contenteditable div and produce the
// `\\n\\n`-separated paragraph text the docx renderer expects.
function extractParagraphText(el: HTMLElement): string {
  const blocks: string[] = [];
  for (const child of Array.from(el.children)) {
    const tag = child.tagName;
    if (tag === "P" || tag === "DIV" || /^H[1-6]$/.test(tag)) {
      blocks.push((child.textContent || "").replace(/\s+/g, " ").trim());
    } else {
      // Inline element: append to the current block, or start one.
      const text = (child.textContent || "").replace(/\s+/g, " ").trim();
      if (text) {
        if (blocks.length === 0) blocks.push("");
        blocks[blocks.length - 1] += (blocks[blocks.length - 1] ? " " : "") + text;
      }
    }
  }
  return blocks.filter((s) => s.length > 0).join("\n\n");
}

// Read a finding's impact/recommendation cell and produce the `\\n`-joined
// paragraph text the docx renderer's `_set_cell_multiline` expects.
function extractCellText(el: HTMLElement): string {
  const paragraphs = Array.from(el.querySelectorAll("p"));
  if (paragraphs.length > 0) {
    return paragraphs
      .map((p) => (p.textContent || "").replace(/\s+/g, " ").trim())
      .filter((s) => s.length > 0)
      .join("\n");
  }
  return (el.textContent || "").replace(/\s+/g, " ").trim();
}

// Enable/disable contenteditable on the preview's tagged regions and
// inject hover/focus CSS. The iframe is sandboxed (allow-same-origin)
// so this must be called from the parent; the iframe's own JS is off.
//
// `srcDoc` parsing is async: when the toggle fires the document body
// may not be parsed yet, so querySelectorAll returns 0 nodes. Retry
// briefly to cover that race.
function applyEditMode(doc: Document, on: boolean) {
  const doIt = (): boolean => {
    const existing = doc.getElementById(EDIT_MODE_STYLE_ID);
    if (existing) existing.remove();

    const tagged = doc.querySelectorAll<HTMLElement>("[data-field]");
    if (tagged.length === 0) return false;

    tagged.forEach((el) => {
      if (on) {
        el.setAttribute("contenteditable", "true");
        // Some browsers refuse contenteditable on bare <td>; lift it to
        // the wrapping <table> so cells in the findings grid still edit.
        const table = el.closest("table");
        if (table) {
          (table as HTMLElement).setAttribute("contenteditable", "true");
        }
      } else {
        el.removeAttribute("contenteditable");
        const table = el.closest("table");
        if (table) {
          (table as HTMLElement).removeAttribute("contenteditable");
        }
      }
    });

    if (on) {
      const style = doc.createElement("style");
      style.id = EDIT_MODE_STYLE_ID;
      style.textContent = EDIT_MODE_CSS;
      doc.head.appendChild(style);
    }
    return true;
  };

  if (doIt()) return;

  const win = doc.defaultView;
  if (!win) return;
  let attempts = 0;
  const interval = win.setInterval(() => {
    if (doIt() || ++attempts >= 10) {
      win.clearInterval(interval);
    }
  }, 50);
}

export default function ReportEditPage() {
  const { wid, rid } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const auth = useAuth();
  const workspaceId = wid ?? auth.activeWorkspace;

  const reportQ = useQuery({
    queryKey: ["report", rid],
    queryFn: async () => (await api.get<Report>(`/reports/${rid}`)).data,
    enabled: !!rid,
  });

  const ctxQ = useQuery({
    queryKey: ["report-context", rid],
    queryFn: async () => (await api.get<{
      findings: Array<{
        finding_id: string;
        vuln_id: string;
        title: string;
        cve_id: string | null;
        severity: string;
        asset_value: string;
        port: number | null;
        protocol: string | null;
        impact: string;
        recommendation: string;
        source_plugin?: string | null;
        source_plugin_id?: string | null;
        references?: string[];
        issues_text?: string;
      }>;
    }>(`/reports/${rid}/context`)).data,
    enabled: !!rid,
    retry: false,
  });

  // local edit state
  const [title, setTitle] = useState("");
  const [execSummary, setExecSummary] = useState("");
  const [overallRating, setOverallRating] = useState<Severity | "">("");
  const [overrides, setOverrides] = useState<Record<string, FindingEdit>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  // per-finding suggest loading + debounce timers
  const [loadingSuggest, setLoadingSuggest] = useState<Record<string, boolean>>({});
  const debounceRefs = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  // Stable handle to the latest setOverride so the WYSIWYG effect can
  // dispatch updates without re-binding on every render.
  const setOverrideRef = useRef<(fid: string, patch: Partial<FindingEdit>) => void>(
    () => {},
  );

  // preview modal state
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  // "pdf" is the default — the rendered PDF is a pixel-perfect match
  // of the DMC docx, while the mammoth HTML preview strips most docx
  // styling. "html" is a read-only HTML fallback; "edit" turns the
  // HTML into a WYSIWYG editor.
  type PreviewMode = "pdf" | "html" | "edit";
  const [previewMode, setPreviewMode] = useState<PreviewMode>("pdf");
  const [iframeReady, setIframeReady] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Sync editMode whenever the user picks a new preview mode from the
  // toggle. The legacy "Edit in place" button still flips editMode on
  // its own; this helper makes the new toggle a one-click shortcut.
  const selectPreviewMode = (m: PreviewMode) => {
    setPreviewMode(m);
    setEditMode(m === "edit");
  };

  // hydrate from server
  useEffect(() => {
    if (!reportQ.data) return;
    setTitle(reportQ.data.title);
    const draft: ReportDraft = reportQ.data.draft_payload || {};
    setExecSummary(draft.exec_summary ?? "");
    setOverallRating((draft.overall_rating as Severity) ?? "");
    const map: Record<string, FindingEdit> = {};
    for (const [fid, ov] of Object.entries(draft.finding_overrides || {})) {
      map[fid] = {
        finding_id: fid,
        severity_override: ov.severity_override,
        impact: ov.impact,
        recommendation: ov.recommendation,
        note: ov.note,
      };
    }
    setOverrides(map);
  }, [reportQ.data?.id]);

  // cleanup any pending debounce timers on unmount
  useEffect(() => {
    const timers = debounceRefs.current;
    return () => {
      for (const t of Object.values(timers)) clearTimeout(t);
    };
  }, []);

  // Ref-sync happens in render (cheap, idempotent). A defensive
  // useEffect is unnecessary because the ref is updated on every
  // render before any user interaction can dispatch from the iframe.

  // Reset the iframe-ready flag whenever a new preview is requested,
  // so we re-apply edit mode after `onLoad` fires for the new document.
  useEffect(() => {
    setIframeReady(false);
  }, [previewHtml]);

  // WYSIWYG: when the preview HTML changes (initial load or refresh),
  // re-attach the input event listeners on the tagged editable regions.
  // The DOM inside the iframe is rebuilt every time srcDoc changes, so
  // listeners must be re-bound on every HTML change. We wait for the
  // iframe's `onLoad` event because srcDoc parsing is async.
  useEffect(() => {
    if (!previewOpen || !previewHtml || !iframeReady || !iframeRef.current) return;
    const doc = iframeRef.current.contentDocument;
    if (!doc) return;

    const handleInput = (e: Event) => {
      let el = e.target as HTMLElement | null;
      while (el && !(el instanceof HTMLElement && el.dataset.field)) {
        el = el.parentElement;
      }
      if (!el) return;
      const field = el.dataset.field;
      const fid = el.dataset.findingId;
      if (field === "exec_summary") {
        setExecSummary(extractParagraphText(el));
      } else if (field === "finding.impact" && fid) {
        setOverrideRef.current(fid, { impact: extractCellText(el) });
      } else if (field === "finding.recommendation" && fid) {
        setOverrideRef.current(fid, { recommendation: extractCellText(el) });
      }
    };

    const tagged = doc.querySelectorAll<HTMLElement>("[data-field]");
    tagged.forEach((el) => el.addEventListener("input", handleInput));

    return () => {
      tagged.forEach((el) => el.removeEventListener("input", handleInput));
    };
  }, [previewOpen, previewHtml, iframeReady]);

  // WYSIWYG: toggle contenteditable + inject hover/focus CSS on the
  // tagged elements when the user enables Edit-in-place. Re-runs on
  // editMode change AND on iframe load, because srcDoc parsing is
  // async and the first effect can fire before the body is parsed.
  useEffect(() => {
    if (!previewOpen || !iframeReady || !iframeRef.current) return;
    const doc = iframeRef.current.contentDocument;
    if (!doc || !doc.body) return;
    applyEditMode(doc, editMode);
  }, [previewOpen, editMode, previewHtml, iframeReady]);

  const findingRows: FindingRow[] = useMemo(() => {
    if (!ctxQ.data?.findings?.length) return [];
    return ctxQ.data.findings.map((f) => ({
      finding_id: f.finding_id,
      vuln_id: f.vuln_id,
      title: f.title,
      cve_id: f.cve_id,
      severity: f.severity as Severity,
      asset_value: f.asset_value,
      port: f.port,
      protocol: f.protocol,
      impact: f.impact || "",
      recommendation: f.recommendation || "",
    }));
  }, [ctxQ.data]);

  // Compute "original" values for dirty tracking
  const originalDraft: ReportDraft = reportQ.data?.draft_payload || {};
  const originalTitle = reportQ.data?.title ?? "";

  // ---- mutations -----------------------------------------------------------

  // Shared apply: merge a set of suggestions into the override map,
  // dropping any finding that ends up with no override fields.
  const applySuggestions = (suggestions: Record<string, FindingSuggestion>) => {
    setOverrides((prev) => {
      const next = { ...prev };
      for (const [fid, sug] of Object.entries(suggestions)) {
        const cur = next[fid] || { finding_id: fid };
        const upd: FindingEdit = {
          ...cur,
          impact: sug.impact,
          recommendation: sug.recommendation,
        };
        if (
          !upd.severity_override && !upd.impact && !upd.recommendation && !upd.note
        ) {
          delete next[fid];
        } else {
          next[fid] = upd;
        }
      }
      return next;
    });
  };

  // Per-finding suggest (called by Auto-fill button and by the debounced
  // re-suggest triggered when the user changes the severity dropdown).
  const suggestMutation = useMutation({
    mutationFn: async ({ fid, severity }: { fid: string; severity: string | null }) => {
      const params = severity ? `?severity=${encodeURIComponent(severity)}` : "";
      return (await api.get<FindingSuggestion>(
        `/reports/${rid}/suggest/${fid}${params}`,
      )).data;
    },
    onMutate: ({ fid }) => {
      setLoadingSuggest((p) => ({ ...p, [fid]: true }));
    },
    onSettled: (_data, _err, vars) => {
      if (vars) setLoadingSuggest((p) => ({ ...p, [vars.fid]: false }));
    },
    onSuccess: (data, vars) => {
      applySuggestions({ [vars.fid]: data });
      toast.success(`Filled with ${data.category} suggestion`);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Suggest failed"),
  });

  // Bulk: Auto-fill all findings in the report.
  const bulkSuggestMutation = useMutation({
    mutationFn: async (findingIds: string[]) => {
      const sevMap: Record<string, Severity> = {};
      for (const fid of findingIds) {
        const ov = overrides[fid];
        if (ov?.severity_override) sevMap[fid] = ov.severity_override;
      }
      return (await api.post<BulkSuggestResponse>(
        `/reports/${rid}/suggest/bulk`,
        { finding_ids: findingIds, severity_overrides: sevMap },
      )).data;
    },
    onSuccess: (data) => {
      const count = Object.keys(data.suggestions).length;
      if (count === 0) {
        toast.info("No suggestions returned");
        return;
      }
      applySuggestions(data.suggestions);
      toast.success(`Auto-filled ${count} findings`);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Bulk suggest failed"),
  });

  // Apply to category: first detect the current finding's category via
  // the single suggest endpoint, then call bulk with category=<that>.
  const applyCategoryMutation = useMutation({
    mutationFn: async (fid: string) => {
      const f = findingRows.find((r) => r.finding_id === fid);
      if (!f) return null;
      const sev = overrides[fid]?.severity_override || f.severity;
      const params = sev ? `?severity=${encodeURIComponent(sev)}` : "";
      const sug = (await api.get<FindingSuggestion>(
        `/reports/${rid}/suggest/${fid}${params}`,
      )).data;
      const sevMap: Record<string, Severity> = {};
      for (const r of findingRows) {
        const ov = overrides[r.finding_id];
        if (ov?.severity_override) sevMap[r.finding_id] = ov.severity_override;
      }
      return (await api.post<BulkSuggestResponse>(
        `/reports/${rid}/suggest/bulk`,
        { category: sug.category, severity_overrides: sevMap },
      )).data;
    },
    onSuccess: (data) => {
      if (!data) return;
      const count = Object.keys(data.suggestions).length;
      const cat = Object.values(data.suggestions)[0]?.category || "this";
      if (count === 0) {
        toast.info("No findings in this category");
        return;
      }
      applySuggestions(data.suggestions);
      toast.success(`Applied to ${count} ${cat} findings`);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Apply failed"),
  });

  const buildBody = (): ReportEditRequest => {
    const body: ReportEditRequest = {};
    if (title !== originalTitle) body.title = title;
    if (overallRating) body.overall_rating = overallRating as Severity;
    body.exec_summary = execSummary;
    const edits: FindingEdit[] = Object.values(overrides);
    if (edits.length) body.findings = edits;
    return body;
  };

  const isDirty = useMemo(() => {
    const body = buildBody();
    if (body.title !== undefined) return true;
    if (body.overall_rating !== undefined) return true;
    if ((body.exec_summary ?? "") !== (originalDraft.exec_summary ?? "")) return true;
    const origLen = Object.keys(originalDraft.finding_overrides || {}).length;
    if (Object.keys(overrides).length !== origLen) return true;
    for (const [fid, ov] of Object.entries(overrides)) {
      const orig = (originalDraft.finding_overrides || {})[fid] || {};
      if ((ov.severity_override ?? undefined) !== (orig.severity_override ?? undefined)) return true;
      if ((ov.impact ?? "") !== (orig.impact ?? "")) return true;
      if ((ov.recommendation ?? "") !== (orig.recommendation ?? "")) return true;
      if ((ov.note ?? "") !== (orig.note ?? "")) return true;
    }
    return false;
  }, [title, execSummary, overallRating, overrides, originalDraft, originalTitle]);

  const save = useMutation({
    mutationFn: async () => api.patch<Report>(`/reports/${rid}`, buildBody()),
    onSuccess: () => {
      toast.success("Draft saved");
      qc.invalidateQueries({ queryKey: ["report", rid] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Save failed"),
  });

  const renderAndGo = useMutation({
    mutationFn: async () => api.post<Report>(`/reports/${rid}/render`, {}),
    onSuccess: () => {
      toast.success("Report rendered");
      qc.invalidateQueries({ queryKey: ["report", rid] });
      navigate(`/workspaces/${workspaceId}/reports/${rid}`);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Render failed"),
  });

  const previewMutation = useMutation({
    mutationFn: async () => (await api.get<string>(
      `/reports/${rid}/preview`,
      { responseType: "text" },
    )).data,
    onSuccess: (data) => {
      setPreviewHtml(data);
      setPreviewOpen(true);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Preview failed"),
  });

  // Edit the report by downloading the docx, editing it in Word/LibreOffice,
  // and uploading it back. The backend extracts the "Analyst Executive
  // Narrative" section and updates draft_payload; the user then sees the
  // change in the live preview.
  const uploadDocxMutation = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return (await api.post<{ ok: boolean; exec_summary: string | null; narrative_paragraphs: number }>(
        `/reports/${rid}/upload-docx`,
        form,
        { headers: { "Content-Type": "multipart/form-data" } },
      )).data;
    },
    onSuccess: (data) => {
      if (data.exec_summary) {
        setExecSummary(data.exec_summary);
        toast.success(`Docx imported — ${data.narrative_paragraphs} paragraph${data.narrative_paragraphs === 1 ? "" : "s"}`);
      } else {
        toast.info("No Analyst Executive Narrative found in the uploaded docx");
      }
      qc.invalidateQueries({ queryKey: ["report", rid] });
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Upload failed"),
  });

  // "View in PDF" / "Download PDF" use the same backend endpoint
  // (GET /reports/{rid}/preview.pdf). The browser displays it inline
  // when opened in a new tab; here we fetch as a blob and trigger a
  // download so the filename is preserved.
  const downloadPdfMutation = useMutation({
    mutationFn: async () => {
      const res = await api.get(`/reports/${rid}/preview.pdf`, { responseType: "blob" });
      const blob = new Blob([res.data], { type: "application/pdf" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `report-${rid}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },
    onSuccess: () => toast.success("PDF downloaded"),
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "PDF download failed"),
  });

  const handleGenerate = async () => {
    if (isDirty) {
      try { await save.mutateAsync(); } catch { return; }
    }
    renderAndGo.mutate();
  };

  if (reportQ.isLoading) {
    return <div className="text-ink-muted">Loading…</div>;
  }
  if (!reportQ.data) {
    return <div className="text-ink-muted">Report not found</div>;
  }
  const d = reportQ.data;
  if (d.locked) {
    return (
      <div className="space-y-3">
        <h1 className="text-2xl font-semibold">Edit report</h1>
        <div className="panel p-4 text-sm text-ink-muted">
          This report is locked and cannot be edited.
        </div>
      </div>
    );
  }

  const setOverride = (fid: string, patch: Partial<FindingEdit>) => {
    setOverrides((prev) => {
      const cur = prev[fid] || { finding_id: fid };
      const next = { ...cur, ...patch };
      if (
        !next.severity_override && !next.impact && !next.recommendation && !next.note
      ) {
        const { [fid]: _drop, ...rest } = prev;
        return rest;
      }
      return { ...prev, [fid]: next };
    });

    // When the user changes the severity override, debounce a re-suggest
    // so the impact / recommendation text follows the new severity.
    if ("severity_override" in patch) {
      if (debounceRefs.current[fid]) clearTimeout(debounceRefs.current[fid]);
      const newSev = patch.severity_override || null;
      debounceRefs.current[fid] = setTimeout(() => {
        suggestMutation.mutate({ fid, severity: newSev });
      }, SUGGEST_DEBOUNCE_MS);
    }
  };
  // Keep the ref pointed at the latest closure so the iframe input
  // handler always calls the freshest setOverride.
  setOverrideRef.current = setOverride;

  const allExpanded = findingRows.length > 0 &&
    findingRows.every((f) => expanded[f.finding_id]);

  return (
    <>
    <div className="space-y-4 pb-32">
      {/* Title */}
      <div className="flex items-end justify-between gap-3">
        <div className="flex-1">
          <label className="text-xs text-ink-muted">Title</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full bg-paper-soft border border-hairline rounded-lg px-3 py-2 text-lg font-semibold mt-1"
          />
        </div>
        <div className="text-xs text-ink-muted shrink-0">
          <div>Status: <span className="font-mono">{d.status}</span></div>
          <div>Updated: {formatDate(d.updated_at)}</div>
        </div>
      </div>

      {/* Executive Summary */}
      <div className="panel p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">Executive summary</h2>
          <div className="flex items-center gap-2 text-xs text-ink-muted">
            <span>Overall rating</span>
            <select
              value={overallRating}
              onChange={(e) => setOverallRating(e.target.value as Severity | "")}
              className="bg-paper-soft border border-hairline rounded-lg px-2 py-1 text-xs"
            >
              <option value="">Auto (from findings)</option>
              {SEV_OPTIONS.map((s) => (
                <option key={s} value={s}>{s.toUpperCase()}</option>
              ))}
            </select>
          </div>
        </div>
        <textarea
          value={execSummary}
          onChange={(e) => setExecSummary(e.target.value)}
          rows={6}
          placeholder="Write a narrative for the executive summary. This replaces the default auto-generated summary text in the docx."
          className="w-full bg-paper-soft border border-hairline rounded-lg px-3 py-2 text-sm font-mono leading-relaxed"
        />
      </div>

      {/* Findings */}
      <div className="panel p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">Findings ({findingRows.length})</h2>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={findingRows.length === 0 || bulkSuggestMutation.isPending}
              onClick={() => bulkSuggestMutation.mutate(findingRows.map((f) => f.finding_id))}
              className="text-xs bg-paper-soft border border-hairline rounded-lg px-2 py-1 flex items-center gap-1 disabled:opacity-50"
            >
              {bulkSuggestMutation.isPending
                ? <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                : <AppleIcon name="sparkles" size={12} />}
              {bulkSuggestMutation.isPending ? "Auto-filling…" : "Auto-fill all"}
            </button>
            <button
              type="button"
              onClick={() => {
                const next: Record<string, boolean> = {};
                findingRows.forEach((f) => (next[f.finding_id] = !allExpanded));
                setExpanded(next);
              }}
              className="text-xs bg-paper-soft border border-hairline rounded-lg px-2 py-1"
            >
              {allExpanded ? "Collapse all" : "Expand all"}
            </button>
          </div>
        </div>

        {ctxQ.isError && (
          <div className="text-xs text-amber-700 bg-amber-500/10 border border-amber-500/30 rounded-lg p-2">
            Findings preview unavailable (no rendered version yet). The list will populate after the first render.
          </div>
        )}

        {findingRows.length === 0 && !ctxQ.isError && (
          <div className="text-sm text-ink-muted text-center py-6">
            No findings to edit.
          </div>
        )}

        <div className="space-y-2">
          {findingRows.map((f) => {
            const ov = overrides[f.finding_id] || { finding_id: f.finding_id };
            const isOpen = expanded[f.finding_id] ?? false;
            const effSev = (ov.severity_override || f.severity) as Severity;
            const isSuggesting = !!loadingSuggest[f.finding_id];
            const isApplyingCat = applyCategoryMutation.isPending &&
              applyCategoryMutation.variables === f.finding_id;
            return (
              <div key={f.finding_id} className="border border-hairline rounded-lg overflow-hidden">
                <button
                  type="button"
                  onClick={() => setExpanded((p) => ({ ...p, [f.finding_id]: !isOpen }))}
                  className="w-full flex items-center gap-3 px-3 py-2 text-left bg-paper-soft/40 hover:bg-paper-soft/70"
                >
                  <span className={cn("pill border", SEV_PILL[effSev])}>
                    {effSev}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">
                      {f.cve_id ? <span className="font-mono text-ink-muted mr-2">{f.cve_id}</span> : null}
                      {f.title}
                    </div>
                    <div className="text-xs text-ink-muted truncate">
                      {f.asset_value}{f.port ? `:${f.port}` : ""}{f.protocol ? `/${f.protocol}` : ""}
                    </div>
                  </div>
                  {isOpen ? <AppleIcon name="chevron-up" size={14} /> : <AppleIcon name="chevron-down" size={14} />}
                </button>
                {isOpen && (
                  <div className="p-3 space-y-3">
                    <div className="grid grid-cols-2 gap-3 text-xs text-ink-muted">
                      <div><span className="text-ink-subtle">Finding ID:</span> <span className="font-mono">{f.finding_id}</span></div>
                      <div><span className="text-ink-subtle">Vuln ID:</span> <span className="font-mono">{f.vuln_id}</span></div>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs text-ink-muted">Severity override</span>
                      <select
                        value={ov.severity_override || ""}
                        onChange={(e) =>
                          setOverride(f.finding_id, {
                            severity_override: (e.target.value || undefined) as Severity | undefined,
                          })
                        }
                        className="bg-paper-soft border border-hairline rounded-lg px-2 py-1 text-xs"
                      >
                        <option value="">(use {f.severity})</option>
                        {SEV_OPTIONS.map((s) => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </select>
                      <button
                        type="button"
                        disabled={isSuggesting}
                        onClick={() => suggestMutation.mutate({
                          fid: f.finding_id,
                          severity: ov.severity_override || f.severity,
                        })}
                        className="text-xs bg-paper-soft border border-hairline rounded-lg px-2 py-1 flex items-center gap-1 disabled:opacity-50"
                      >
                        {isSuggesting
                          ? <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                          : <AppleIcon name="sparkles" size={12} />}
                        Auto-fill
                      </button>
                      <button
                        type="button"
                        disabled={isApplyingCat}
                        onClick={() => applyCategoryMutation.mutate(f.finding_id)}
                        className="text-xs bg-paper-soft border border-hairline rounded-lg px-2 py-1 flex items-center gap-1 disabled:opacity-50"
                      >
                        {isApplyingCat
                          ? <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                          : <AppleIcon name="sparkles" size={12} />}
                        Apply to category
                      </button>
                    </div>
                    <div>
                      <label className="text-xs text-ink-muted">Impact (overrides AI draft)</label>
                      <textarea
                        value={ov.impact ?? f.impact}
                        onChange={(e) =>
                          setOverride(f.finding_id, { impact: e.target.value })
                        }
                        rows={3}
                        className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-xs mt-1 font-mono"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-ink-muted">Recommendation (overrides AI draft)</label>
                      <textarea
                        value={ov.recommendation ?? f.recommendation}
                        onChange={(e) =>
                          setOverride(f.finding_id, { recommendation: e.target.value })
                        }
                        rows={3}
                        className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-xs mt-1 font-mono"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-ink-muted">Analyst note (internal, not in docx)</label>
                      <textarea
                        value={ov.note ?? ""}
                        onChange={(e) =>
                          setOverride(f.finding_id, { note: e.target.value })
                        }
                        rows={2}
                        placeholder="Notes for the reviewer / approver…"
                        className="w-full bg-paper-soft border border-hairline rounded-lg px-2 py-1.5 text-xs mt-1"
                      />
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Sticky action bar */}
      <div className="fixed bottom-0 left-0 right-0 z-30 border-t border-hairline bg-paper/90 backdrop-blur">
        <div className="max-w-[1400px] mx-auto px-4 py-3 flex items-center gap-2">
          <div className="flex-1 text-xs text-ink-muted flex items-center gap-2">
            {isDirty ? (
              <>
                <span className="h-2 w-2 rounded-full bg-amber-400" />
                Unsaved changes
              </>
            ) : (
              <>
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                All changes saved
              </>
            )}
          </div>
          <button
            type="button"
            onClick={() => navigate(`/workspaces/${workspaceId}/reports/${rid}`)}
            className="bg-paper-soft border border-hairline rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5"
          >
            <AppleIcon name="x-mark" size={14} /> Discard
          </button>
          <button
            type="button"
            onClick={() => save.mutate()}
            disabled={!isDirty || save.isPending}
            className="bg-paper-soft border border-finder-blue/30 text-finder-blue rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5 disabled:opacity-50"
          >
            <AppleIcon name="save" size={14} /> Save draft
          </button>
          <button
            type="button"
            onClick={() => previewMutation.mutate()}
            disabled={previewMutation.isPending}
            className="bg-paper-soft border border-hairline rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5 disabled:opacity-50"
          >
            {previewMutation.isPending
              ? <span className="inline-block w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
              : <AppleIcon name="eye" size={14} />}
            {previewMutation.isPending ? "Loading…" : "Preview"}
          </button>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadDocxMutation.isPending}
            className="bg-paper-soft border border-hairline rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5 disabled:opacity-50"
            title="Edit the report by downloading the docx, editing in Word, then uploading back here"
          >
            {uploadDocxMutation.isPending
              ? <span className="inline-block w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
              : <AppleIcon name="upload" size={14} />}
            {uploadDocxMutation.isPending ? "Importing…" : "Upload edited docx"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".docx"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              // Reset the input so the same file can be re-selected later.
              e.target.value = "";
              if (file) uploadDocxMutation.mutate(file);
            }}
          />
          <button
            type="button"
            onClick={handleGenerate}
            disabled={renderAndGo.isPending || save.isPending}
            className="bg-finder-blue hover:bg-folder-to text-white rounded-lg px-3 py-1.5 text-sm flex items-center gap-1.5 disabled:opacity-50"
          >
            {isDirty ? <AppleIcon name="save" size={14} /> : <AppleIcon name="sparkles" size={14} />}
            {isDirty ? "Save & generate" : "Generate report"}
          </button>
        </div>
      </div>
    </div>

    {previewOpen && previewHtml && (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
        onClick={() => { setPreviewOpen(false); setEditMode(false); setPreviewMode("pdf"); }}
      >
        <div
          className="panel w-full max-w-5xl h-[90vh] flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between px-4 py-2 border-b border-hairline">
            <div className="flex items-center gap-3">
              <h2 className="text-sm font-semibold">Report preview</h2>
              {editMode && (
                <span className="text-xs text-amber-700 bg-amber-500/10 border border-amber-500/30 rounded px-2 py-0.5">
                  Editing — changes flow into the editor and Save draft
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <div className="flex border border-hairline rounded-lg overflow-hidden text-xs">
                {(["pdf", "html", "edit"] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => selectPreviewMode(m)}
                    className={cn(
                      "px-2 py-1",
                      previewMode === m
                        ? "bg-finder-blue text-white"
                        : "bg-paper-soft text-ink-muted hover:text-ink"
                    )}
                    title={
                      m === "pdf"
                        ? "Pixel-perfect PDF match of the original DMC docx"
                        : m === "html"
                          ? "HTML preview (faster, but doesn't match docx exactly)"
                          : "Edit in place (changes flow into the editor)"
                    }
                  >
                    {m === "pdf" ? "PDF" : m === "html" ? "HTML" : "Edit"}
                  </button>
                ))}
              </div>
              <button
                type="button"
                onClick={() => {
                  // If we're in PDF view, "Edit in place" must also switch
                  // out of the PDF iframe (which has no editable DOM) into
                  // the Edit view. Otherwise just toggle contenteditable.
                  if (previewMode === "pdf" && !editMode) {
                    selectPreviewMode("edit");
                  } else {
                    setEditMode((v) => !v);
                  }
                }}
                className={cn(
                  "text-xs rounded-lg px-2 py-1 flex items-center gap-1",
                  editMode
                    ? "bg-finder-blue text-white border border-finder-blue"
                    : "bg-paper-soft border border-hairline"
                )}
                title="Make the preview's exec narrative and finding impact/recommendation cells editable in place"
              >
                {editMode ? "Done editing" : "Edit in place"}
              </button>
              <button
                type="button"
                onClick={() => window.open(`/api/v1/reports/${rid}/preview.pdf`, "_blank", "noopener")}
                className="text-xs bg-paper-soft border border-hairline rounded-lg px-2 py-1 flex items-center gap-1"
                title="Open the pixel-perfect PDF preview in a new tab"
              >
                <AppleIcon name="eye" size={12} /> View in PDF
              </button>
              <button
                type="button"
                onClick={() => downloadPdfMutation.mutate()}
                disabled={downloadPdfMutation.isPending}
                className="text-xs bg-paper-soft border border-hairline rounded-lg px-2 py-1 flex items-center gap-1 disabled:opacity-50"
                title="Download the pixel-perfect PDF"
              >
                {downloadPdfMutation.isPending
                  ? <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                  : <AppleIcon name="download" size={12} />}
                {downloadPdfMutation.isPending ? "Rendering…" : "Download PDF"}
              </button>
              <button
                type="button"
                onClick={() => previewMutation.mutate()}
                disabled={previewMutation.isPending}
                className="text-xs bg-paper-soft border border-hairline rounded-lg px-2 py-1 flex items-center gap-1 disabled:opacity-50"
              >
                {previewMutation.isPending
                  ? <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                  : <AppleIcon name="eye" size={12} />}
                Refresh
              </button>
              <button
                type="button"
                onClick={() => { setPreviewOpen(false); setEditMode(false); setPreviewMode("pdf"); }}
                className="text-ink-muted hover:text-ink"
                aria-label="Close preview"
              >
                <AppleIcon name="x-mark" size={16} />
              </button>
            </div>
          </div>
          {previewMode === "pdf" ? (
            <iframe
              src={`/api/v1/reports/${rid}/preview.pdf`}
              title="Report PDF preview"
              className="flex-1 w-full bg-gray-100 border-0"
            />
          ) : (
            <iframe
              ref={iframeRef}
              srcDoc={previewHtml}
              onLoad={() => setIframeReady(true)}
              title="Report preview"
              sandbox="allow-same-origin"
              className="flex-1 w-full bg-paper-strong border-0"
            />
          )}
        </div>
      </div>
    )}
    </>
  );
}
