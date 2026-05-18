from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def default_run_dir(base_dir: Path | None = None, prefix: str = "") -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return (base_dir or Path("data/runs")) / f"{prefix}{stamp}"


def write_run_outputs(
    output_dir: Path,
    result_payload: dict[str, Any],
    agent_response: dict[str, Any],
) -> None:
    write_json(output_dir / "result.json", result_payload)
    write_json(output_dir / "agent_response.json", agent_response)
    write_markdown(output_dir / "features.md", result_payload)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    features = payload["product_features"]
    crawl = payload["crawl"]
    lines = [
        f"# {features['product_name']} 产品功能提取",
        "",
        f"- URL: {crawl['final_url']}",
        f"- 标题: {crawl['title']}",
        f"- 浏览器模式: {crawl['browser_mode']}",
        "",
        "## 摘要",
        "",
        features["summary"] or "无",
        "",
        "## 产品功能",
        "",
    ]
    if features["features"]:
        lines.extend(f"- {item}" for item in features["features"])
    else:
        lines.append("- 未提取到明确功能")

    lines.extend(["", "## 证据", ""])
    if features["evidence"]:
        lines.extend(f"- {item}" for item in features["evidence"])
    else:
        lines.append("- 无")

    if features["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in features["warnings"])

    proofreading = payload.get("proofreading")
    if proofreading:
        lines.extend(["", "## Proofreading", ""])
        if proofreading.get("error"):
            lines.append(f"- Error: {proofreading['error']}")
        else:
            result = proofreading.get("result")
            suggestion_count = len(result) if isinstance(result, list) else 0
            lines.append(f"- Suggestions: {suggestion_count}")
            correct = proofreading.get("correct")
            if correct:
                lines.append(f"- Correct: {correct}")
            if result:
                lines.append(
                    f"- Result: {json.dumps(result, ensure_ascii=False)}"
                )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
