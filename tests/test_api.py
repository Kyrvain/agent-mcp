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
            latest = client.get("/api/runs/latest/direct")

        self.assertEqual(runs.status_code, 200)
        self.assertEqual(runs.json()[0]["id"], "20260518-120000")
        self.assertEqual(result.json(), {"ok": True})
        self.assertEqual(features.text, "# demo\n")
        self.assertEqual(latest.status_code, 404)

    def test_latest_run_endpoint_infers_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            direct_dir = base / "20260518-120000"
            search_dir = base / "20260518-130000"
            batch_dir = base / "20260518-140000"
            direct_dir.mkdir()
            search_dir.mkdir()
            batch_dir.mkdir()
            (direct_dir / "result.json").write_text(
                json.dumps(
                    {
                        "crawl": {
                            "requested_url": "https://example.test/detail",
                            "final_url": "https://example.test/detail",
                        },
                        "product_features": {"product_name": "direct demo"},
                    }
                ),
                encoding="utf-8",
            )
            (direct_dir / "agent_response.json").write_text(
                json.dumps({"product_name": "direct demo"}),
                encoding="utf-8",
            )
            (search_dir / "result.json").write_text(
                json.dumps(
                    {
                        "crawl": {},
                        "search": {"query": "search demo"},
                        "product_features": {"product_name": "search demo"},
                    }
                ),
                encoding="utf-8",
            )
            (search_dir / "agent_response.json").write_text(
                json.dumps({"product_name": "search demo"}),
                encoding="utf-8",
            )
            (batch_dir / "result.json").write_text(
                json.dumps({"batch": {"processed_count": 1}, "products": []}),
                encoding="utf-8",
            )
            (batch_dir / "agent_response.json").write_text(
                json.dumps(
                    {
                        "batch": {"processed_count": 1},
                        "products": [{"product_name": "batch demo"}],
                    }
                ),
                encoding="utf-8",
            )

            app = create_app(
                job_manager=StaticJobManager(),
                run_store=RunStore(base),
            )
            client = TestClient(app)
            direct = client.get("/api/runs/latest/direct").json()
            search = client.get("/api/runs/latest/search").json()
            batch = client.get("/api/runs/latest/batch").json()

        self.assertEqual(direct["request"]["url"], "https://example.test/detail")
        self.assertFalse(direct["request"]["search"])
        self.assertEqual(search["request"]["product_name"], "search demo")
        self.assertTrue(search["request"]["search"])
        self.assertTrue(batch["request"]["batch_proofread"])
        self.assertIn("batch", batch["agent_response"])


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

    async def run_batch_proofread(
        self,
        *,
        force_refresh_catalog: bool = False,
        limit: int | None = None,
        concurrency: int | None = None,
        output_dir: Path | None = None,
    ) -> object:
        return type(
            "BatchResult",
            (),
            {
                "result_payload": {
                    "batch": {
                        "refreshed_catalog": force_refresh_catalog,
                        "processed_count": limit,
                        "concurrency": concurrency,
                    }
                },
                "agent_response": {
                    "batch": {
                        "refreshed_catalog": force_refresh_catalog,
                        "processed_count": limit,
                        "concurrency": concurrency,
                    }
                },
            },
        )()


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

    async def test_job_manager_runs_batch_proofread_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = CrawlJobManager(
                workflow_factory=FakeWorkflow,
                run_dir_factory=lambda: Path(tmp) / "api-batch-run",
            )
            job = await manager.create_job(
                CrawlJobRequest(
                    product_name="demo",
                    batch_proofread=True,
                    refresh_catalog=True,
                    batch_limit=2,
                    batch_concurrency=3,
                )
            )
            await job.task

        self.assertEqual(job.status, "succeeded")
        self.assertTrue(job.agent_response["batch"]["refreshed_catalog"])
        self.assertEqual(job.agent_response["batch"]["processed_count"], 2)
        self.assertEqual(job.agent_response["batch"]["concurrency"], 3)


if __name__ == "__main__":
    unittest.main()
