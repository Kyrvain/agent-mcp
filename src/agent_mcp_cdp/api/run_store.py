from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import CrawlJobResponse, RunSummary


class RunStore:
    def __init__(self, base_dir: Path = Path("data/runs")) -> None:
        self.base_dir = base_dir

    def list_runs(self) -> list[RunSummary]:
        if not self.base_dir.exists():
            return []
        runs = []
        for path in self.base_dir.iterdir():
            if not path.is_dir():
                continue
            runs.append(self._summary(path))
        return sorted(runs, key=lambda item: item.updated_at, reverse=True)

    def latest_job_response(self, mode: str) -> CrawlJobResponse | None:
        for summary in self.list_runs():
            if not summary.has_agent_response or not summary.has_result:
                continue
            try:
                result = self.read_json(summary.id, "result.json")
                agent_response = self.read_json(summary.id, "agent_response.json")
            except (FileNotFoundError, json.JSONDecodeError):
                continue
            if _infer_run_mode(result, agent_response) != mode:
                continue
            return CrawlJobResponse(
                id=f"run:{summary.id}",
                status="succeeded",
                request=_request_from_run(mode, result, agent_response),
                created_at=summary.updated_at,
                started_at=None,
                finished_at=summary.updated_at,
                output_dir=summary.path,
                error=None,
                result=None,
                agent_response=agent_response,
            )
        return None

    def read_json(self, run_id: str, filename: str) -> dict[str, Any]:
        path = self._run_path(run_id) / filename
        if not path.exists():
            raise FileNotFoundError(path)
        return json.loads(path.read_text(encoding="utf-8"))

    def read_text(self, run_id: str, filename: str) -> str:
        path = self._run_path(run_id) / filename
        if not path.exists():
            raise FileNotFoundError(path)
        return path.read_text(encoding="utf-8")

    def file_path(self, run_id: str, filename: str) -> Path:
        path = self._run_path(run_id) / filename
        if not path.exists():
            raise FileNotFoundError(path)
        return path

    def _run_path(self, run_id: str) -> Path:
        if "/" in run_id or "\\" in run_id or run_id in {"", ".", ".."}:
            raise FileNotFoundError(run_id)
        base = self.base_dir.resolve()
        path = (base / run_id).resolve()
        if base not in path.parents and path != base:
            raise FileNotFoundError(run_id)
        if not path.is_dir():
            raise FileNotFoundError(run_id)
        return path

    def _summary(self, path: Path) -> RunSummary:
        stat = path.stat()
        updated_at = datetime.fromtimestamp(
            stat.st_mtime,
            tz=timezone.utc,
        ).isoformat()
        return RunSummary(
            id=path.name,
            path=str(path),
            updated_at=updated_at,
            has_result=(path / "result.json").exists(),
            has_agent_response=(path / "agent_response.json").exists(),
            has_features=(path / "features.md").exists(),
            has_screenshot=(path / "page.png").exists(),
        )


def _infer_run_mode(
    result: dict[str, Any],
    agent_response: dict[str, Any],
) -> str | None:
    if "batch" in result or "batch" in agent_response:
        return "batch"
    if "search" in result:
        return "search"
    if "crawl" in result:
        return "direct"
    return None


def _request_from_run(
    mode: str,
    result: dict[str, Any],
    agent_response: dict[str, Any],
) -> dict[str, Any]:
    product_name = str(
        agent_response.get("product_name")
        or (result.get("product_features") or {}).get("product_name")
        or "历史任务"
    )
    request: dict[str, Any] = {
        "product_name": product_name,
        "search": mode == "search",
        "proofread": _has_proofreading(agent_response),
        "batch_proofread": mode == "batch",
    }
    crawl = result.get("crawl")
    if mode == "direct" and isinstance(crawl, dict):
        request["url"] = crawl.get("requested_url") or crawl.get("final_url")
    return request


def _has_proofreading(agent_response: dict[str, Any]) -> bool:
    if "proofreading" in agent_response:
        return True
    products = agent_response.get("products")
    if isinstance(products, list):
        return any(
            isinstance(product, dict) and "proofreading" in product
            for product in products
        )
    return False
