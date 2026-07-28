"""Auth schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=200)


class TotpRequiredResponse(BaseModel):
    totp_required: bool = True
    challenge_token: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserOut"


class TotpVerifyRequest(BaseModel):
    challenge_token: str
    code: str = Field(min_length=6, max_length=8)


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    expires_in: int


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=200)


class TotpEnrollResponse(BaseModel):
    secret: str
    otpauth_url: str
    qr_data_uri: str
    backup_codes: list[str]


class UserCreate(BaseModel):
    """Schema for platform-admin user creation. Note: `is_platform_admin` is
    NOT exposed — elevation must go through a separate, audited path."""

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=200)


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    is_active: bool
    is_platform_admin: bool
    totp_enabled: bool
    last_login_at: datetime | None
    created_at: datetime
    memberships: list["MembershipOut"] = []


class MembershipOut(BaseModel):
    workspace_id: UUID
    workspace_name: str
    role: str


LoginResponse.model_rebuild()
UserOut.model_rebuild()
