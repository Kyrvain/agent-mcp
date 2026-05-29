from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from agent_mcp_cdp.api.app import create_app
from agent_mcp_cdp.api.jobs import CrawlJob, CrawlJobManager
from agent_mcp_cdp.api.run_store import RunStore
from agent_mcp_cdp.api.schemas import CrawlJobRequest
from agent_mcp_cdp.config import Settings
from agent_mcp_cdp.models import CrawlResult, ProductFeatures
from agent_mcp_cdp.services.crawl_workflow import CrawlWorkflowResult


class StaticJobManager:
    def __init__(self) -> None:
        self.job: CrawlJob | None = None

    async def create_job(self, request: CrawlJobRequest) -> CrawlJob:
        self.job = CrawlJob(id="job-1", request=request, status="queued")
        return self.job

    def list_jobs(self) -> list[CrawlJob]:
        return [self.job] if self.job is not None else []

    def get_job(self, job_id: str) -> CrawlJob | None:
        if self.job and self.job.id == job_id:
            return self.job
        return None


class ApiRouteTests(unittest.TestCase):
    def test_create_and_get_crawl_job(self) -> None:
        manager = StaticJobManager()
        app = create_app(job_manager=manager, run_store=RunStore(Path("missing-runs")))
        client = TestClient(app)

        created = client.post(
            "/api/crawl-jobs",
            json={"product_name": "九章爱学", "proofread": True},
        )

        self.assertEqual(created.status_code, 202)
        self.assertEqual(created.json()["id"], "job-1")
        self.assertEqual(created.json()["request"]["product_name"], "九章爱学")

        fetched = client.get("/api/crawl-jobs/job-1")

        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["status"], "queued")

    def test_run_store_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            run_dir = base / "20260518-120000"
            run_dir.mkdir()
            (run_dir / "result.json").write_text(
                json.dumps({"ok": True}),
                encoding="utf-8",
            )
            (run_dir / "agent_response.json").write_text(
                json.dumps({"product_name": "demo"}),
                encoding="utf-8",
            )
            (run_dir / "features.md").write_text("# demo\n", encoding="utf-8")

            app = create_app(
                job_manager=StaticJobManager(),
                run_store=RunStore(base),
            )
            client = TestClient(app)

            runs = client.get("/api/runs")
            result = client.get("/api/runs/20260518-120000/result")
            features = client.get("/api/runs/20260518-120000/features")

        self.assertEqual(runs.status_code, 200)
        self.assertEqual(runs.json()[0]["id"], "20260518-120000")
        self.assertEqual(result.json(), {"ok": True})
        self.assertEqual(features.text, "# demo\n")


class FakeWorkflow:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def run(
        self,
        *,
        use_search: bool,
        list_only: bool = False,
        proofread: bool = False,
        output_dir: Path | None = None,
    ) -> CrawlWorkflowResult:
        crawl = CrawlResult(
            requested_url=self.settings.target_url,
            final_url=self.settings.target_url,
            title="Demo",
            text="body",
        )
        features = ProductFeatures(
            product_name=self.settings.product_name,
            summary="summary",
            features=["feature"],
        )
        return CrawlWorkflowResult(
            crawl=crawl,
            features=features,
            result_payload={"crawl": crawl.to_dict(), "product_features": features.to_dict()},
            agent_response=features.to_dict(),
        )


class CrawlJobManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_job_manager_runs_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = CrawlJobManager(
                workflow_factory=FakeWorkflow,
                run_dir_factory=lambda: Path(tmp) / "api-run",
            )
            job = await manager.create_job(
                CrawlJobRequest(
                    product_name="demo",
                    url="https://example.test/detail",
                    search=False,
                )
            )
            self.assertIsNotNone(job.task)
            await job.task

        self.assertEqual(job.status, "succeeded")
        self.assertEqual(job.agent_response["product_name"], "demo")
        self.assertEqual(manager.get_job(job.id), job)

    async def test_headed_false_forces_headless_mode(self) -> None:
        manager = CrawlJobManager(
            workflow_factory=FakeWorkflow,
            run_dir_factory=lambda: Path("unused"),
        )
        settings = manager._settings_from_request(
            CrawlJobRequest(product_name="demo", headed=False),
            None,
        )

        self.assertTrue(settings.browser_headless)

    async def test_headed_true_forces_visible_browser(self) -> None:
        manager = CrawlJobManager(
            workflow_factory=FakeWorkflow,
            run_dir_factory=lambda: Path("unused"),
        )
        settings = manager._settings_from_request(
            CrawlJobRequest(product_name="demo", headed=True),
            None,
        )

        self.assertFalse(settings.browser_headless)


if __name__ == "__main__":
    unittest.main()
