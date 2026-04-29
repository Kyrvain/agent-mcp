from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_TARGET_URL = (
    "https://bjedures.bjedu.cn/ggzypt/#/ai/mark/detail"
    "?id=9c7f91783fb83cc08aa98036f939b4e2"
    "&name=%E9%A3%9E%E8%B1%A1%E6%99%BA%E8%83%BD%E4%BD%9C%E4%B8%9A"
)
DEFAULT_PRODUCT_NAME = "飞象智能作业"


def _truthy(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


@dataclass(slots=True)
class Settings:
    target_url: str = DEFAULT_TARGET_URL
    product_name: str = DEFAULT_PRODUCT_NAME
    cdp_url: str | None = None
    remote_debugging_port: int = 9222
    browser_executable: str | None = None
    browser_headless: bool = True
    browser_user_data_dir: Path = Path(".browser-profile")
    output_dir: Path = Path("data/runs")
    wait_after_load_ms: int = 5000
    navigation_timeout_ms: int = 60000
    max_response_chars: int = 8000
    max_responses: int = 16
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o-mini"

    @classmethod
    def from_env(cls, **overrides: object) -> "Settings":
        load_dotenv()
        values: dict[str, object] = {
            "target_url": os.getenv("TARGET_URL", DEFAULT_TARGET_URL),
            "product_name": os.getenv("PRODUCT_NAME", DEFAULT_PRODUCT_NAME),
            "cdp_url": _optional(os.getenv("CDP_URL")),
            "remote_debugging_port": int(os.getenv("REMOTE_DEBUGGING_PORT", "9222")),
            "browser_executable": _optional(os.getenv("BROWSER_EXECUTABLE")),
            "browser_headless": _truthy(os.getenv("BROWSER_HEADLESS"), True),
            "browser_user_data_dir": Path(
                os.getenv("BROWSER_USER_DATA_DIR", ".browser-profile")
            ),
            "output_dir": Path(os.getenv("OUTPUT_DIR", "data/runs")),
            "wait_after_load_ms": int(os.getenv("WAIT_AFTER_LOAD_MS", "5000")),
            "navigation_timeout_ms": int(os.getenv("NAVIGATION_TIMEOUT_MS", "60000")),
            "max_response_chars": int(os.getenv("MAX_RESPONSE_CHARS", "8000")),
            "max_responses": int(os.getenv("MAX_RESPONSES", "16")),
            "openai_api_key": _optional(os.getenv("OPENAI_API_KEY")),
            "openai_base_url": _optional(os.getenv("OPENAI_BASE_URL")),
            "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        }
        values.update({key: value for key, value in overrides.items() if value is not None})
        return cls(**values)
