import { useParams } from "react-router-dom";
import { Link } from "react-router-dom";
import AppleIcon from "../../components/ui/AppleIcon";
import { cn } from "../../lib/cn";

export default function LegacyHelpPage() {
  const { wid } = useParams();
  const back = `/workspaces/${wid}/legacy`;

  return (
    <div className="space-y-5 max-w-3xl mx-auto p-4 min-w-0">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <AppleIcon name="question" size={20} className="text-finder-blue" /> Legacy import help
          </h1>
          <p className="text-sm text-ink-muted">
            How to migrate data from the old <code className="font-mono">vulnerabilities.db</code>{" "}
            into this platform
          </p>
        </div>
        <Link
          to={back}
          className="bg-paper-soft border border-hairline hover:border-finder-blue rounded-lg px-3 py-1.5 text-sm"
        >
          ← Back to importer
        </Link>
      </div>

      <Section icon={<AppleIcon name="server" size={14} />} title="1. Locating the legacy file">
        <p>
          The old automation tool stores all of its findings in a single SQLite file called{" "}
          <code className="font-mono text-ink">vulnerabilities.db</code>. It usually lives next to
          the legacy CLI binary or under the tool's data directory. Common paths:
        </p>
        <ul className="list-disc pl-5 space-y-1 text-ink-muted">
          <li>
            <code className="font-mono">/opt/old-vapt/data/vulnerabilities.db</code>
          </li>
          <li>
            <code className="font-mono">~/vapt-legacy/vulnerabilities.db</code>
          </li>
          <li>
            <code className="font-mono">C:\vapt\data\vulnerabilities.db</code>{" "}
            (Windows agents)
          </li>
        </ul>
        <p>
          The full path must be reachable by the platform server (shared volume, mounted path,
          or accessible UNC). Provide the absolute path on the importer page.
        </p>
      </Section>

      <Section icon={<AppleIcon name="rect-grid" size={14} />} title="2. Expected schema">
        <p>
          The legacy DB is expected to expose a single <code className="font-mono">findings</code>{" "}
          table with the following columns. Missing columns are tolerated and filled with{" "}
          <code className="font-mono">NULL</code>; extra columns are ignored.
        </p>
        <pre className="text-xs bg-paper-soft border border-hairline rounded-lg p-3 overflow-x-auto">
{`CREATE TABLE findings (
  id          INTEGER PRIMARY KEY,
  name        TEXT NOT NULL,        -- vulnerability title
  host        TEXT NOT NULL,        -- asset value (FQDN or IP)
  port        INTEGER,              -- TCP/UDP port, NULL if N/A
  plugin_id   TEXT,                 -- scanner plugin id (e.g. Nessus)
  cve         TEXT,                 -- CVE id, may be NULL
  severity    TEXT NOT NULL,        -- critical | high | medium | low | info
  description TEXT,
  solution    TEXT,
  scan_id     TEXT,
  scan_name   TEXT,
  first_seen  TEXT,                 -- ISO-8601 timestamp
  last_seen   TEXT                  -- ISO-8601 timestamp
);`}
        </pre>
        <ColumnMapping />
      </Section>

      <Section icon={<AppleIcon name="rect-grid" size={14} />} title="3. Migration path">
        <ol className="list-decimal pl-5 space-y-2 text-ink-muted">
          <li>
            On the importer page, pick the target <span className="text-ink">engagement</span> and
            paste the absolute path of the legacy <code className="font-mono">vulnerabilities.db</code>{" "}
            file.
          </li>
          <li>
            Click <span className="text-ink">Preview</span> — the platform opens the file
            read-only, counts the rows, and shows three sample titles so you can sanity-check
            that you pointed at the right database.
          </li>
          <li>
            Click <span className="text-ink">Import</span>. Rows are normalized, deduplicated
            against existing vulnerabilities by (CVE / title + host + port), and inserted as
            findings. You will see counts for <em>rows processed</em>,{" "}
            <em>new vulnerabilities</em>, and <em>new findings</em>.
          </li>
          <li>
            Open <span className="text-ink">Multi-scan compare</span> for the engagement, pick the
            legacy ingestion job as the <em>baseline</em> and your latest scan as the{" "}
            <em>current</em> job, then run the compare to see what was fixed and what regressed.
          </li>
          <li>
            (Optional) Ingest a fresh Nessus / Qualys / OpenVAS scan into the same engagement to
            detect new regressions that the legacy DB cannot show.
          </li>
        </ol>
      </Section>

      <Section icon={<AppleIcon name="shield-check" size={14} />} title="4. Security note">
        <p>
          The legacy importer is{" "}
          <span className="text-emerald-700 font-medium">strictly read-only</span> on the source
          SQLite file. The platform opens the database with{" "}
          <code className="font-mono">mode=ro</code>, executes only a bounded set of read
          queries (<code className="font-mono">SELECT COUNT(*)</code> and{" "}
          <code className="font-mono">SELECT … LIMIT</code>), and writes nothing back. The file
          is never copied or modified on disk.
        </p>
        <p>
          Because the path is a host filesystem path, treat it like any other secret-bearing
          asset: do not commit it, do not log it, and rotate the database if the host is
          re-provisioned.
        </p>
      </Section>
    </div>
  );
}

function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="panel p-4 space-y-2">
      <h2 className="text-sm font-semibold flex items-center gap-2">
        <span className="text-finder-blue">{icon}</span>
        {title}
      </h2>
      <div className="text-sm text-ink-muted space-y-2 [&_p]:text-ink-muted">{children}</div>
    </section>
  );
}

function ColumnMapping() {
  const rows: { source: string; target: string; notes: string }[] = [
    { source: "id", target: "—", notes: "Discarded (new UUIDs are assigned)" },
    { source: "name", target: "vulnerability.title", notes: "" },
    { source: "host", target: "asset.value", notes: "Auto-created if missing" },
    { source: "port", target: "finding.port", notes: "" },
    { source: "plugin_id", target: "vulnerability.source_plugin_id", notes: "" },
    { source: "cve", target: "vulnerability.cve_id", notes: "Also used for dedup" },
    { source: "severity", target: "vulnerability.severity", notes: "Normalized to enum" },
    { source: "description", target: "vulnerability.description", notes: "" },
    { source: "solution", target: "vulnerability.solution", notes: "" },
    { source: "scan_id", target: "ingestion_job.external_id", notes: "" },
    { source: "scan_name", target: "ingestion_job.source_filename", notes: "" },
    { source: "first_seen", target: "finding.first_seen", notes: "" },
    { source: "last_seen", target: "finding.last_seen", notes: "" },
  ];
  return (
    <div className="overflow-x-auto mt-2">
      <table className="w-full text-sm">
        <thead className="text-ink-muted text-xs bg-paper-soft">
          <tr className="text-left">
            <th className="px-3 py-2">Legacy column</th>
            <th className="px-3 py-2">→ Target field</th>
            <th className="px-3 py-2">Notes</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.source} className="border-t border-hairline">
              <td className={cn("px-3 py-2 font-mono text-xs")}>{r.source}</td>
              <td className="px-3 py-2 font-mono text-xs text-finder-blue">{r.target}</td>
              <td className="px-3 py-2 text-ink-muted">{r.notes || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
