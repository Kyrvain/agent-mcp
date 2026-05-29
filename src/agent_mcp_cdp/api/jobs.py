from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from ..config import DEFAULT_TARGET_URL, Settings
from ..schemas.payloads import build_search_response
from ..services.crawl_workflow import CrawlWorkflow, CrawlWorkflowResult
from ..services.output_writer import default_run_dir
from .schemas import CrawlJobRequest, CrawlJobResponse, JobStatus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _model_to_dict(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


@dataclass(slots=True)
class CrawlJob:
    id: str
    request: CrawlJobRequest
    status: JobStatus = "queued"
    created_at: str = field(default_factory=_now)
    started_at: str | None = None
    finished_at: str | None = None
    output_dir: Path | None = None
    error: str | None = None
    result: dict[str, Any] | None = None
    agent_response: dict[str, Any] | None = None
    task: asyncio.Task[None] | None = field(default=None, repr=False)

    def to_response(self, include_result: bool = True) -> CrawlJobResponse:
        return CrawlJobResponse(
            id=self.id,
            status=self.status,
            request=_model_to_dict(self.request),
            created_at=self.created_at,
            started_at=self.started_at,
            finished_at=self.finished_at,
            output_dir=str(self.output_dir) if self.output_dir else None,
            error=self.error,
            result=self.result if include_result else None,
            agent_response=self.agent_response if include_result else None,
        )


class CrawlJobManager:
    def __init__(
        self,
        workflow_factory: Callable[[Settings], Any] = CrawlWorkflow,
        run_dir_factory: Callable[[], Path] | None = None,
    ) -> None:
        self.workflow_factory = workflow_factory
        self.run_dir_factory = run_dir_factory or (
            lambda: default_run_dir(prefix="api-")
        )
        self._jobs: dict[str, CrawlJob] = {}
        self._run_lock = asyncio.Lock()

    async def create_job(self, request: CrawlJobRequest) -> CrawlJob:
        job = CrawlJob(
            id=uuid4().hex,
            request=request,
            output_dir=self.run_dir_factory() if not request.list_only else None,
        )
        self._jobs[job.id] = job
        job.task = asyncio.create_task(self._run_job(job))
        return job

    def list_jobs(self) -> list[CrawlJob]:
        return sorted(
            self._jobs.values(),
            key=lambda item: item.created_at,
            reverse=True,
        )

    def get_job(self, job_id: str) -> CrawlJob | None:
        return self._jobs.get(job_id)

    async def _run_job(self, job: CrawlJob) -> None:
        async with self._run_lock:
            job.status = "running"
            job.started_at = _now()
            try:
                settings = self._settings_from_request(job.request, job.output_dir)
                workflow = self.workflow_factory(settings)
                use_search = (
                    job.request.search
                    if job.request.search is not None
                    else job.request.url is None or job.request.list_only
                )
                result: CrawlWorkflowResult = await workflow.run(
                    use_search=use_search,
                    list_only=job.request.list_only,
                    proofread=job.request.proofread,
                    output_dir=job.output_dir,
                )
                if job.request.list_only or result.crawl is None:
                    search_response = build_search_response(result.search_result)
                    job.result = search_response
                    job.agent_response = search_response
                else:
                    job.result = result.result_payload
                    job.agent_response = result.agent_response
                job.status = "succeeded"
            except Exception as exc:
                detail = str(exc) or repr(exc)
                job.error = f"{type(exc).__name__}: {detail}"
                job.status = "failed"
            finally:
                job.finished_at = _now()

    def _settings_from_request(
        self,
        request: CrawlJobRequest,
        output_dir: Path | None,
    ) -> Settings:
        settings = Settings.from_env(
            target_url=request.url or DEFAULT_TARGET_URL,
            product_name=request.product_name,
            cdp_url=request.cdp_url,
            browser_executable=request.browser_executable,
            browser_headless=None if request.headed is None else not request.headed,
            wait_after_load_ms=request.wait_ms,
            output_dir=output_dir,
        )
        if request.confidence is not None:
            settings.search_confidence_threshold = request.confidence
        return settings
