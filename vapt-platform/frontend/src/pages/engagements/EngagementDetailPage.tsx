import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import AppleIcon from "../../components/ui/AppleIcon";
import { api } from "../../lib/api";
import { useAuth } from "../../hooks/useAuth";
import { cn, formatDate } from "../../lib/cn";
import type { Engagement, Finding, IngestionJob } from "../../types";
import Card from "../../components/ui/Card";
import Toolbar from "../../components/ui/Toolbar";

type Tab = "overview" | "scans" | "reports";

const SUPPORTED_FORMATS = [
  { name: "Nessus", ext: ".nessus" },
  { name: "Nmap", ext: ".xml" },
  { name: "Burp Suite", ext: ".xml" },
  { name: "OWASP ZAP", ext: ".xml" },
  { name: "Nuclei", ext: ".jsonl" },
  { name: "OpenVAS / GVM", ext: ".xml" },
  { name: "Qualys", ext: ".xml" },
  { name: "Trivy", ext: ".json" },
  { name: "Snyk", ext: ".json" },
  { name: "Prowler (AWS)", ext: ".json" },
  { name: "testssl.sh", ext: ".json" },
  { name: "WPScan", ext: ".json" },
  { name: "Nikto", ext: ".csv/.json" },
  { name: "Metasploit", ext: ".xml" },
  { name: "AWS Inspector", ext: ".json" },
  { name: "kube-bench", ext: ".json" },
  { name: "SARIF", ext: ".sarif/.json" },
  { name: "CycloneDX SBOM", ext: ".cdx.json" },
  { name: "SPDX SBOM", ext: ".spdx.json" },
];

const ACCEPT_ATTR = [
  ".nessus",
  ".xml",
  ".json",
  ".jsonl",
  ".ndjson",
  ".csv",
  ".sarif",
  ".cdx.json",
  ".cyclonedx.json",
  ".spdx.json",
  ".txt",
].join(",");

export default function EngagementDetailPage() {
  const { wid, eid } = useParams();
  const auth = useAuth();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("overview");
  const [file, setFile] = useState<File | null>(null);

  const eng = useQuery({
    queryKey: ["engagement", eid],
    queryFn: async () => (await api.get<Engagement>(`/engagements/${eid}`)).data,
    enabled: !!eid,
  });
  const findings = useQuery({
    queryKey: ["findings", eid],
    queryFn: async () =>
      (await api.get<Finding[]>(`/engagements/${eid}/findings?limit=200`)).data,
    enabled: !!eid,
  });
  const jobs = useQuery({
    queryKey: ["ingestion-jobs", eid],
    queryFn: async () =>
      (await api.get<IngestionJob[]>(`/ingestion/engagements/${eid}/jobs`)).data,
    enabled: !!eid,
  });

  const upload = useMutation({
    mutationFn: async (f: File) => {
      const form = new FormData();
      form.append("file", f);
      form.append("engagement_id", eid!);
      return api.post("/ingestion/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
    },
    onSuccess: () => {
      toast.success("Ingested");
      qc.invalidateQueries({ queryKey: ["findings", eid] });
      qc.invalidateQueries({ queryKey: ["ingestion-jobs", eid] });
      qc.invalidateQueries({ queryKey: ["engagement", eid] });
      qc.invalidateQueries({ queryKey: ["engagements", wid] });
      qc.invalidateQueries({ queryKey: ["dashboard-findings", wid] });
      setFile(null);
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Upload failed"),
  });

  const runAgent = useMutation({
    mutationFn: async () => api.post("/agent/run", { engagement_id: eid }),
    onSuccess: () => toast.success("Agent started — check Agent Review tab"),
    onError: (e: any) => toast.error(e?.response?.data?.detail ?? "Agent start failed"),
  });

  const lock = useMutation({
    mutationFn: async () =>
      api.patch(`/engagements/${eid}`, { ingestion_locked: !eng.data?.ingestion_locked }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["engagement", eid] }),
  });

  return (
    <div className="space-y-5 max-w-[1400px] mx-auto">
      {/* Header */}
      <Card className="p-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-[11px] text-ink-muted font-mono mb-1.5">
              <span>{eng.data?.code}</span>
              <span className="text-ink-subtle">·</span>
              <span className="uppercase tracking-wider">{eng.data?.type}</span>
            </div>
            <h1 className="text-2xl font-semibold tracking-tight leading-tight">
              {eng.data?.name ?? "—"}
            </h1>
            <div className="text-sm text-ink-muted mt-1 flex flex-wrap gap-2">
              <span>{eng.data?.client}</span>
              <span className="text-ink-subtle">·</span>
              <span>{eng.data?.methodology}</span>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => runAgent.mutate()}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm",
                "bg-finder-blue-soft text-finder-blue border border-finder-blue/30",
                "hover:bg-finder-blue/25 transition-colors duration-200 ease-out"
              )}
            >
              <AppleIcon name="play" size={14} /> Run AI agent
            </button>
            <Link
              to={`/workspaces/${wid}/engagements/${eid}/multiscan`}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm",
                "bg-paper-soft border border-hairline-strong hover:border-finder-blue/40",
                "transition-colors duration-200 ease-out"
              )}
            >
              <AppleIcon name="check-shield" size={14} /> Multi-scan
            </Link>
            <Link
              to={`/workspaces/${wid}/tableview?engagement_id=${eid}`}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm",
                "bg-paper-soft border border-hairline-strong hover:border-finder-blue/40",
                "transition-colors duration-200 ease-out"
              )}
            >
              <AppleIcon name="table" size={14} /> Table view
            </Link>
            <button
              onClick={() => lock.mutate()}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm",
                "bg-paper-soft border border-hairline-strong hover:border-finder-blue/40",
                "transition-colors duration-200 ease-out"
              )}
            >
              <AppleIcon name="lock" size={14} /> {eng.data?.ingestion_locked ? "Unlock" : "Lock"} ingestion
            </button>
          </div>
        </div>
      </Card>

      {/* Tabs */}
      <div className="tabs">
        {(["overview", "scans", "reports"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn("tab", tab === t && "tab-active")}
          >
            {t === "overview" ? "Overview" : t === "scans" ? "Scans" : "Reports"}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card className="p-4">
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-1.5">
              <AppleIcon name="calendar" size={14} /> Scope
            </h3>
            <dl className="text-xs space-y-2">
              <div className="flex justify-between">
                <dt className="text-ink-muted">Start</dt>
                <dd className="font-mono">{formatDate(eng.data?.start_date)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-muted">End</dt>
                <dd className="font-mono">{formatDate(eng.data?.end_date)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-muted">Report due</dt>
                <dd className="font-mono">{formatDate(eng.data?.report_due_date)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-ink-muted">Status</dt>
                <dd>
                  <span className="pill pill-muted">{eng.data?.status}</span>
                </dd>
              </div>
            </dl>
          </Card>

          <Card className="p-4 lg:col-span-2">
            <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
              <AppleIcon name="upload" size={14} /> Ingest scan results
            </h3>
            <p className="text-xs text-ink-muted mb-3">
              Drop a scan export from any of the supported tools. The dedup
              engine collapses the same vulnerability across hosts into a
              single record.
            </p>
            <div className="flex items-center gap-2 flex-wrap">
              <input
                id="engagement-scan-file"
                type="file"
                accept={ACCEPT_ATTR}
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="sr-only"
              />
              <label
                htmlFor="engagement-scan-file"
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm cursor-pointer",
                  "bg-paper-soft border border-hairline-strong hover:border-finder-blue/40",
                  "transition-all duration-200 ease-out active:scale-[0.98]"
                )}
              >
                <AppleIcon name="table" size={14} />
                {file ? file.name : "Choose scan file…"}
              </label>
              {file && (
                <button
                  onClick={() => setFile(null)}
                  className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-ink-muted hover:text-rose-700 transition-colors duration-200"
                  title="Clear selection"
                >
                  <AppleIcon name="x-mark" size={12} /> clear
                </button>
              )}
              <button
                onClick={() => file && upload.mutate(file)}
                disabled={!file || upload.isPending}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm",
                  "bg-finder-blue text-white hover:bg-folder-to",
                  "transition-all duration-200 ease-out active:scale-[0.98] disabled:opacity-50"
                )}
              >
                <AppleIcon name="upload" size={14} /> Upload
              </button>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              <span className="text-[11px] text-ink-muted inline-flex items-center gap-1">
                <AppleIcon name="question" size={11} /> Supported formats:
              </span>
              {SUPPORTED_FORMATS.map((f) => (
                <span
                  key={f.name}
                  title={`${f.name} (${f.ext})`}
                  className="pill pill-muted text-[10px] font-mono cursor-help"
                >
                  {f.name}
                </span>
              ))}
            </div>
          </Card>

          <Card className="p-4 lg:col-span-3">
            <h3 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
              <AppleIcon name="shield" size={14} /> Findings at a glance
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <Stat label="Total" value={(findings.data ?? []).length} />
              <Stat label="Open" value={(findings.data ?? []).filter((f) => !["resolved", "false_positive", "accepted_risk", "deferred", "remediated_pending_confirmation"].includes(f.status)).length} />
              <Stat label="Critical" value={(findings.data ?? []).filter((f) => f.effective_severity === "critical").length} />
              <Stat label="High" value={(findings.data ?? []).filter((f) => f.effective_severity === "high").length} />
            </div>
          </Card>
        </div>
      )}

      {tab === "scans" && (
        <Card className="p-4 overflow-hidden">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold">Recent ingestions</h3>
            <span className="text-xs text-ink-muted">{(jobs.data ?? []).length} job{(jobs.data ?? []).length === 1 ? "" : "s"}</span>
          </div>
          <div className="overflow-x-auto -mx-4">
            <table className="w-full text-sm min-w-[760px]">
              <thead className="text-xs text-ink-muted">
                <tr className="text-left border-b border-hairline-strong">
                  <th className="px-4 py-2 font-medium">File</th>
                  <th className="px-4 py-2 font-medium">Format</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium text-right">New vulns</th>
                  <th className="px-4 py-2 font-medium text-right">New findings</th>
                  <th className="px-4 py-2 font-medium text-right">Regressed</th>
                  <th className="px-4 py-2 font-medium text-right">Remediated</th>
                  <th className="px-4 py-2 font-medium">When</th>
                </tr>
              </thead>
              <tbody>
                {(jobs.data ?? []).map((j) => (
                  <tr
                    key={j.id}
                    className="border-b border-hairline hover:bg-paper-soft transition-colors duration-200"
                  >
                    <td className="px-4 py-2.5 font-mono text-xs truncate max-w-[220px]">
                      {j.source_filename ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 text-ink-muted">{j.format}</td>
                    <td className="px-4 py-2.5">
                      <span
                        className={cn(
                          "pill",
                          j.status === "done"
                            ? "pill-success"
                            : j.status === "failed"
                            ? "pill-danger"
                            : "pill-muted"
                        )}
                      >
                        {j.status}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-right">{j.new_vulns}</td>
                    <td className="px-4 py-2.5 font-mono text-right">{j.new_findings}</td>
                    <td className="px-4 py-2.5 font-mono text-right">{j.regressed_findings}</td>
                    <td className="px-4 py-2.5 font-mono text-right">{j.remediated_findings}</td>
                    <td className="px-4 py-2.5 text-ink-muted text-xs">{formatDate(j.created_at)}</td>
                  </tr>
                ))}
                {(jobs.data ?? []).length === 0 && (
                  <tr>
                    <td colSpan={8} className="text-center text-ink-muted py-10">
                      No scans ingested yet
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {tab === "reports" && (
        <Card className="p-6 text-center text-sm text-ink-muted">
          Reports are managed in the{" "}
          <Link to={`/workspaces/${wid}/reports`} className="text-finder-blue hover:underline">
            Reports
          </Link>{" "}
          section.
        </Card>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-paper-soft border border-hairline p-3">
      <div className="text-[11px] uppercase tracking-wider text-ink-muted">{label}</div>
      <div className="text-2xl font-semibold mt-1 font-mono">{value}</div>
    </div>
  );
}
