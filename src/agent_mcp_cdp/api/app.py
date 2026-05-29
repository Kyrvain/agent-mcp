from __future__ import annotations

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse, PlainTextResponse

from .jobs import CrawlJobManager
from .run_store import RunStore
from .schemas import CrawlJobRequest, CrawlJobResponse, RunSummary


def create_app(
    job_manager: CrawlJobManager | None = None,
    run_store: RunStore | None = None,
) -> FastAPI:
    app = FastAPI(
        title="agent-mcp-cdp API",
        version="0.1.0",
        description="HTTP API for product crawling, extraction, and proofreading.",
    )
    app.state.job_manager = job_manager or CrawlJobManager()
    app.state.run_store = run_store or RunStore()

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(
        "/api/crawl-jobs",
        response_model=CrawlJobResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_crawl_job(request: CrawlJobRequest) -> CrawlJobResponse:
        job = await app.state.job_manager.create_job(request)
        return job.to_response(include_result=False)

    @app.get("/api/crawl-jobs", response_model=list[CrawlJobResponse])
    async def list_crawl_jobs() -> list[CrawlJobResponse]:
        return [
            job.to_response(include_result=False)
            for job in app.state.job_manager.list_jobs()
        ]

    @app.get("/api/crawl-jobs/{job_id}", response_model=CrawlJobResponse)
    async def get_crawl_job(job_id: str) -> CrawlJobResponse:
        job = app.state.job_manager.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return job.to_response()

    @app.get("/api/runs", response_model=list[RunSummary])
    async def list_runs() -> list[RunSummary]:
        return app.state.run_store.list_runs()

    @app.get("/api/runs/{run_id}/result")
    async def get_run_result(run_id: str) -> dict:
        return _read_json_or_404(run_id, "result.json")

    @app.get("/api/runs/{run_id}/agent-response")
    async def get_run_agent_response(run_id: str) -> dict:
        return _read_json_or_404(run_id, "agent_response.json")

    @app.get("/api/runs/{run_id}/features", response_class=PlainTextResponse)
    async def get_run_features(run_id: str) -> str:
        try:
            return app.state.run_store.read_text(run_id, "features.md")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Run features not found.")

    @app.get("/api/runs/{run_id}/screenshot")
    async def get_run_screenshot(run_id: str) -> FileResponse:
        try:
            path = app.state.run_store.file_path(run_id, "page.png")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Run screenshot not found.")
        return FileResponse(path)

    def _read_json_or_404(run_id: str, filename: str) -> dict:
        try:
            return app.state.run_store.read_json(run_id, filename)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Run result not found.")

    return app


app = create_app()
