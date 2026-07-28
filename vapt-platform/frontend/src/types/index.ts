export type Role =
  | "platform_admin"
  | "admin"
  | "senior_analyst"
  | "analyst"
  | "viewer";

export interface Membership {
  workspace_id: string;
  workspace_name: string;
  role: Role;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_platform_admin: boolean;
  totp_enabled: boolean;
  last_login_at: string | null;
  created_at: string;
  memberships: Membership[];
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  default_sla_days: Record<string, number>;
  created_at: string;
}

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export type FindingStatus =
  | "new"
  | "confirmed"
  | "in_remediation"
  | "resolved"
  | "remediated_pending_confirmation"
  | "regressed"
  | "false_positive"
  | "accepted_risk"
  | "deferred";

export type EngagementStatus =
  | "planned"
  | "active"
  | "in_reporting"
  | "delivered"
  | "closed"
  | "cancelled";

export type EngagementType =
  | "webapp"
  | "network"
  | "wireless"
  | "mobile"
  | "cloud"
  | "redteam"
  | "social"
  | "other";

export interface Engagement {
  id: string;
  workspace_id: string;
  code: string;
  name: string;
  client: string;
  description: string | null;
  type: EngagementType;
  status: EngagementStatus;
  start_date: string | null;
  end_date: string | null;
  report_due_date: string | null;
  methodology: string;
  test_types: string[];
  lead_id: string | null;
  ingestion_locked: boolean;
  created_at: string;
  updated_at: string;
  severity_breakdown?: Record<string, number>;
  findings_total?: number;
}

export interface Asset {
  id: string;
  type: string;
  value: string;
  port: number | null;
  protocol: string | null;
  fqdn: string | null;
  ip: string | null;
  environment: string | null;
  criticality: "low" | "medium" | "high" | "critical";
  owner: string | null;
  business_unit: string | null;
  tags: string[];
  first_seen: string;
  last_seen: string;
  findings_count?: number;
}

export interface LinkedAsset {
  asset_id: string;
  asset_value: string;
  asset_type: string;
  port: number | null;
  finding_id: string;
  finding_status: FindingStatus;
  engagement_id: string;
}

export interface Vulnerability {
  id: string;
  title: string;
  description: string;
  cve_id: string | null;
  cwe_id: string | null;
  cwe_category: string;
  severity: Severity;
  cvss_score: number | null;
  cvss_vector: string | null;
  confidence: string;
  references: string[];
  tags: string[];
  source_plugin: string | null;
  source_plugin_id: string | null;
  occurrence_count: number;
  linked_assets: LinkedAsset[];
  ai_draft_impact: string | null;
  ai_draft_recommendation: string | null;
  ai_drafted_at: string | null;
  ai_draft_reviewed_at: string | null;
  ai_draft_approved: boolean;
  created_at: string;
  updated_at: string;
}

export interface Finding {
  id: string;
  workspace_id: string;
  engagement_id: string;
  vulnerability_id: string;
  asset_id: string;
  port: number | null;
  protocol: string | null;
  evidence_ref: string | null;
  status: FindingStatus;
  severity: Severity;
  effective_severity: Severity;
  cvss_score: number | null;
  risk_score: number | null;
  risk_components: Record<string, number> | null;
  sla_due_at: string | null;
  sla_breached: boolean;
  first_seen: string;
  last_seen: string;
  resolved_at: string | null;
  assigned_to: string | null;
  asset_value: string | null;
  asset_type: string | null;
  vuln_title: string | null;
  vuln_cve_id: string | null;
  vuln_description: string | null;
}

export type ReportStatus =
  | "drafting"
  | "pending_review"
  | "changes_requested"
  | "approved"
  | "published"
  | "rejected";

export interface ReportVersion {
  id: string;
  version_no: number;
  status: ReportStatus;
  author_id: string | null;
  agent_session_id: string | null;
  note: string | null;
  s3_key: string | null;
  sha256: string | null;
  size: number | null;
  created_at: string;
}

export interface Report {
  id: string;
  engagement_id: string;
  title: string;
  status: ReportStatus;
  current_version_id: string | null;
  signed_sha256: string | null;
  signed_at: string | null;
  signed_by: string | null;
  locked: boolean;
  locked_at: string | null;
  created_at: string;
  updated_at: string;
  draft_payload: ReportDraft;
  versions: ReportVersion[];
}

export interface FindingOverride {
  severity_override?: Severity;
  impact?: string;
  recommendation?: string;
  note?: string;
}

export interface ReportDraft {
  overall_rating?: Severity;
  exec_summary?: string;
  finding_overrides?: Record<string, FindingOverride>;
}

export interface FindingEdit {
  finding_id: string;
  severity_override?: Severity | null;
  impact?: string | null;
  recommendation?: string | null;
  note?: string | null;
  source_plugin?: string | null;
  source_plugin_id?: string | null;
}

export interface ReportEditRequest {
  title?: string | null;
  overall_rating?: Severity | null;
  exec_summary?: string | null;
  findings?: FindingEdit[] | null;
}

export interface FindingSuggestion {
  finding_id: string;
  impact: string;
  recommendation: string;
  action_urgency: string;
  category: string;
}

export interface BulkSuggestRequest {
  finding_ids?: string[] | null;
  category?: string | null;
  severity_overrides?: Record<string, Severity> | null;
}

export interface BulkSuggestResponse {
  suggestions: Record<string, FindingSuggestion>;
}

export interface IngestionJob {
  id: string;
  engagement_id: string;
  source: string;
  source_filename: string | null;
  format: string;
  status:
    | "queued"
    | "parsing"
    | "deduping"
    | "done"
    | "failed"
    | "partial";
  started_at: string | null;
  finished_at: string | null;
  raw_items: number;
  parsed_items: number;
  new_vulns: number;
  merged_vulns: number;
  new_findings: number;
  updated_findings: number;
  regressed_findings: number;
  remediated_findings: number;
  error: string | null;
  log: { ts: string; msg: string }[];
  created_at: string;
}

export interface DiffRow {
  finding_id: string;
  vulnerability_id: string;
  asset_id: string;
  asset_value: string | null;
  port: number | null;
  title: string;
  severity: Severity;
  cvss_score: number | null;
  cve_id: string | null;
  status: string;
  first_seen: string;
  last_seen: string;
}

export interface CompareResult {
  baseline_job_id: string;
  current_job_id: string;
  still_present: DiffRow[];
  new_findings: DiffRow[];
  fixed: DiffRow[];
  stats: {
    still_present: number;
    new_findings: number;
    fixed: number;
  };
}

export interface TableRow {
  cve_id: string | null;
  title: string;
  cvss_score: number | null;
  hosts: string[];
  ports: (number | string)[];
  sample_asset: string | null;
}

export interface TableViewPayload {
  engagement: { id: string; name: string; code: string; client: string };
  generated_at: string;
  by_severity: Record<Severity, TableRow[]>;
  totals: Record<Severity, number>;
}

export type VulnWithIntel = {
  id: string;
  title: string;
  cve_id: string | null;
  severity: string;
  cvss_score: number | null;
  confidence: string;
  occurrence_count: number;
  epss_score?: number | null;
  epss_percentile?: number | null;
  kev?: boolean;
  fetched_at?: string | null;
};

export interface NessusServer {
  id: string;
  workspace_id: string;
  name: string;
  base_url: string;
  access_key: string;
  secret_key: string | null;
  verify_ssl: boolean;
  request_timeout: number;
  max_concurrency: number;
  only_completed_scans: boolean;
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_message: string | null;
}

export interface NessusScan {
  id: string;
  name: string;
  status: string;
  policy: string;
  scan_type: string;
  target: string;
  completed_at: string | null;
  imported_engagement_id: string | null;
  imported_ingestion_job_id: string | null;
}

export interface SbomComponent {
  name: string;
  version: string | null;
  purl: string | null;
  licenses: string[];
  vulnerabilities: number;
}

export interface SbomResult {
  format: "cyclonedx" | "spdx";
  components: SbomComponent[];
  stats: { total: number; with_vulns: number };
}

export interface PreviewResult {
  rows: number;
  first_3: string[];
  db_path: string;
  db_size_bytes: number | null;
  db_mtime: string | null;
}

export interface ImportResult {
  rows: number;
  new_vulns: number;
  new_findings: number;
  merged_findings: number;
  db_path: string;
  imported_at: string;
}

export interface AgentRun {
  id: string;
  session_id: string;
  status: "running" | "completed" | "failed" | "cancelled";
  started_at: string;
  finished_at: string | null;
  iterations: number;
  vulns_drafted: number;
  report_rendered: boolean;
}

export type AgentEvent =
  | { type: "tool_call"; name: string; args: any; ts: string }
  | { type: "tool_result"; name: string; result: any; ts: string }
  | { type: "message"; role: string; content: string; ts: string }
  | { type: "status"; status: string; ts: string };

export interface ApiToken {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  last_used_at: string | null;
  use_count: number;
  revoked: boolean;
  expires_at: string | null;
  created_at: string;
}

export interface WebhookEndpoint {
  id: string;
  name: string;
  url: string;
  events: string[];
  active: boolean;
  last_delivery_at: string | null;
  failure_count: number;
}

export interface WebhookDelivery {
  id: string;
  endpoint_id: string;
  event: string;
  status: "success" | "failed" | "pending";
  attempts: number;
  response_status: number | null;
  created_at: string;
}

export interface LdapConfig {
  id: string;
  workspace_id: string;
  server_url: string;
  use_tls: boolean;
  bind_dn: string;
  bind_password: string | null;
  user_search_base: string;
  user_search_filter: string;
  default_role: string;
  group_role_map: Record<string, string>;
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_message: string | null;
}

export interface PortalShare {
  id: string;
  report_id: string;
  label: string | null;
  current_views: number;
  max_views: number | null;
  expires_at: string | null;
  revoked: boolean;
  last_access_at: string | null;
  created_at: string;
}

export type RetestStatus =
  | "scheduled"
  | "in_progress"
  | "completed"
  | "cancelled";

export interface RetestCycle {
  id: string;
  workspace_id: string;
  engagement_id: string | null;
  retest_engagement_id: string | null;
  title: string;
  scheduled_for: string;
  status: RetestStatus;
  created_at: string;
}

export interface Comment {
  id: string;
  body: string;
  author_id: string | null;
  parent_id: string | null;
  mentions: string[];
  created_at: string;
  edited_at: string | null;
  deleted: boolean;
}
