"""Pydantic v2 schemas - request/response DTOs."""

from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    TotpRequiredResponse,
    TotpVerifyRequest,
    RefreshRequest,
    AccessTokenResponse,
    PasswordChangeRequest,
    UserCreate,
    UserOut,
    MembershipOut,
    TotpEnrollResponse,
)
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceOut,
    MembershipCreate,
    MembershipUpdate,
)
from app.schemas.engagement import (
    EngagementCreate,
    EngagementUpdate,
    EngagementOut,
    ScopeRuleOut,
    ScopeRuleCreate,
)
from app.schemas.asset import (
    AssetCreate,
    AssetUpdate,
    AssetOut,
)
from app.schemas.vulnerability import (
    VulnerabilityOut,
    VulnerabilityTagOut,
    AiDraftUpdate,
)
from app.schemas.finding import (
    FindingOut,
    FindingUpdate,
    FindingActivityOut,
    FindingEvidenceOut,
    TriageAction,
    BulkTriageRequest,
)
from app.schemas.report import (
    ReportOut,
    ReportCreate,
    ReportVersionOut,
    ReportApproveRequest,
    RenderRequest,
)
from app.schemas.ingestion import (
    IngestionJobOut,
    IngestionUploadResponse,
)
from app.schemas.comment import CommentOut
from app.schemas.webhook import WebhookEndpointOut, WebhookDeliveryOut
from app.schemas.portal import PortalShareOut
from app.schemas.threat_intel import ThreatIntelOut
from app.schemas.token import ApiTokenOut, ApiTokenCreateOut
from app.schemas.agent import AgentRunOut
from app.schemas.common import (
    PageMeta,
    Page,
    IdResponse,
    ErrorResponse,
    HealthOut,
)

__all__ = [
    "LoginRequest",
    "LoginResponse",
    "TotpRequiredResponse",
    "TotpVerifyRequest",
    "RefreshRequest",
    "AccessTokenResponse",
    "PasswordChangeRequest",
    "UserCreate",
    "UserOut",
    "MembershipOut",
    "TotpEnrollResponse",
    "WorkspaceCreate",
    "WorkspaceUpdate",
    "WorkspaceOut",
    "MembershipCreate",
    "MembershipUpdate",
    "EngagementCreate",
    "EngagementUpdate",
    "EngagementOut",
    "ScopeRuleOut",
    "ScopeRuleCreate",
    "AssetCreate",
    "AssetUpdate",
    "AssetOut",
    "VulnerabilityOut",
    "VulnerabilityTagOut",
    "AiDraftUpdate",
    "FindingOut",
    "FindingUpdate",
    "FindingActivityOut",
    "FindingEvidenceOut",
    "TriageAction",
    "BulkTriageRequest",
    "ReportOut",
    "ReportCreate",
    "ReportVersionOut",
    "ReportApproveRequest",
    "RenderRequest",
    "IngestionJobOut",
    "IngestionUploadResponse",
    "CommentOut",
    "WebhookEndpointOut",
    "WebhookDeliveryOut",
    "PortalShareOut",
    "ThreatIntelOut",
    "ApiTokenOut",
    "ApiTokenCreateOut",
    "AgentRunOut",
    "PageMeta",
    "Page",
    "IdResponse",
    "ErrorResponse",
    "HealthOut",
]
