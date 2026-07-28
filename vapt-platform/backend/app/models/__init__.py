"""SQLAlchemy ORM models - vulnerability-centric, multi-tenant."""

from app.models.user import (
    User,
    UserSession,
    WorkspaceMembership,
    AuditLog,
    LoginAttempt,
)
from app.models.workspace import Workspace
from app.models.engagement import Engagement, ScopeRule
from app.models.asset import Asset
from app.models.vulnerability import Vulnerability, VulnerabilityTag
from app.models.finding import Finding, FindingActivity, FindingEvidence
from app.models.report import Report, ReportTemplate, ReportVersion
from app.models.ingestion import IngestionJob

# v2 additions
from app.models.threat_intel import ThreatIntelCache
from app.models.comment import FindingComment, CommentMention
from app.models.retest import RetestCycle
from app.models.evidence_blob import EvidenceBlob
from app.models.api_token import ApiToken
from app.models.webhook import WebhookEndpoint, WebhookDelivery
from app.models.portal import PortalShare
from app.models.agent_run import AgentRun, AgentDraftDiff
from app.models.ldap import LdapConfig, LdapUserMapping
from app.models.notification import Notification, NotificationPreference
from app.models.nessus import NessusServer, NessusScanCache, MultiScanJob

__all__ = [
    "User",
    "UserSession",
    "WorkspaceMembership",
    "AuditLog",
    "LoginAttempt",
    "Workspace",
    "Engagement",
    "ScopeRule",
    "Asset",
    "Vulnerability",
    "VulnerabilityTag",
    "Finding",
    "FindingActivity",
    "FindingEvidence",
    "Report",
    "ReportTemplate",
    "ReportVersion",
    "IngestionJob",
    # v2
    "ThreatIntelCache",
    "FindingComment",
    "CommentMention",
    "RetestCycle",
    "EvidenceBlob",
    "ApiToken",
    "WebhookEndpoint",
    "WebhookDelivery",
    "PortalShare",
    "AgentRun",
    "AgentDraftDiff",
    "LdapConfig",
    "LdapUserMapping",
    "Notification",
    "NotificationPreference",
    "NessusServer",
    "NessusScanCache",
    "MultiScanJob",
]
