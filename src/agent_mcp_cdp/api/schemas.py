from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from ..config import DEFAULT_PRODUCT_NAME

JobStatus = Literal["queued", "running", "succeeded", "failed"]


class CrawlJobRequest(BaseModel):
    product_name: str = Field(default=DEFAULT_PRODUCT_NAME, min_length=1)
    url: str | None = None
    search: bool | None = None
    list_only: bool = False
    proofread: bool = False
    cdp_url: str | None = None
    browser_executable: str | None = None
    headed: bool | None = None
    wait_ms: int | None = Field(default=None, ge=0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class CrawlJobResponse(BaseModel):
    id: str
    status: JobStatus
    request: dict[str, Any]
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    output_dir: str | None = None
    error: str | None = None
    result: dict[str, Any] | None = None
    agent_response: dict[str, Any] | None = None


class RunSummary(BaseModel):
    id: str
    path: str
    updated_at: str
    has_result: bool
    has_agent_response: bool
    has_features: bool
    has_screenshot: bool
