from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import RunSummary


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
