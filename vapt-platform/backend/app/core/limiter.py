"""Shared slowapi Limiter instance.

Imported by every router that wants to add a per-endpoint rate limit.
Kept in its own module to avoid the main.py import cycle.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Default `key_func` is per-IP (the standard). Per-account quotas are added
# in the auth router via custom in-memory counters.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_default],
)
