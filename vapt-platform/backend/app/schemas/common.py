"""Common schemas."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class IdResponse(BaseModel):
    id: str


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None
    extra: dict = Field(default_factory=dict)


class HealthOut(BaseModel):
    status: str = "ok"
    db: bool = True
    redis: bool = True
    s3: bool = True
    version: str = "0.1.0"


class PageMeta(BaseModel):
    total: int
    page: int
    page_size: int


class Page(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta
