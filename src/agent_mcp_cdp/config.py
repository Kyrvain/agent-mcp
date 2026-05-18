from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_LISTING_URL = "https://bjedures.bjedu.cn/ggzypt/#/ai/mark/index"
DEFAULT_PRODUCT_NAME = "九章爱学"
DEFAULT_TARGET_URL = (
    "https://bjedures.bjedu.cn/ggzypt/#/ai/mark/detail?id=d2f86dc826363941840a28c0d084431f&name=%E4%B9%9D%E7%AB%A0%E7%88%B1%E5%AD%A6"
)


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean, got {value!r}")


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {value!r}") from exc


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
    listing_url: str = DEFAULT_LISTING_URL
    listing_wait_after_load_ms: int = 8000
    listing_max_response_chars: int = 262144
    search_confidence_threshold: float = 0.3
    proofreading_api_url: str | None = "http://10.199.194.160:22235/api"
    proofreading_timeout_s: float = 30.0
    proofreading_max_chars: int = 20000

    @classmethod
    def from_env(cls, **overrides: object) -> "Settings":
        load_dotenv()
        values: dict[str, object] = {
            "target_url": _env_str("TARGET_URL", DEFAULT_TARGET_URL),
            "product_name": _env_str("PRODUCT_NAME", DEFAULT_PRODUCT_NAME),
            "cdp_url": _optional(os.getenv("CDP_URL")),
            "remote_debugging_port": _env_int("REMOTE_DEBUGGING_PORT", 9222),
            "browser_executable": _optional(os.getenv("BROWSER_EXECUTABLE")),
            "browser_headless": _env_bool("BROWSER_HEADLESS", True),
            "browser_user_data_dir": Path(
                _env_str("BROWSER_USER_DATA_DIR", ".browser-profile")
            ),
            "output_dir": Path(_env_str("OUTPUT_DIR", "data/runs")),
            "wait_after_load_ms": _env_int("WAIT_AFTER_LOAD_MS", 5000),
            "navigation_timeout_ms": _env_int("NAVIGATION_TIMEOUT_MS", 60000),
            "max_response_chars": _env_int("MAX_RESPONSE_CHARS", 8000),
            "max_responses": _env_int("MAX_RESPONSES", 16),
            "listing_url": _env_str("LISTING_URL", DEFAULT_LISTING_URL),
            "listing_wait_after_load_ms": _env_int("LISTING_WAIT_AFTER_LOAD_MS", 8000),
            "listing_max_response_chars": _env_int(
                "LISTING_MAX_RESPONSE_CHARS", 262144
            ),
            "search_confidence_threshold": _env_float(
                "SEARCH_CONFIDENCE_THRESHOLD", 0.3
            ),
            "proofreading_api_url": _optional(
                os.getenv("PROOFREADING_API_URL", "http://10.199.194.160:22235/api")
            ),
            "proofreading_timeout_s": _env_float("PROOFREADING_TIMEOUT_S", 30.0),
            "proofreading_max_chars": _env_int("PROOFREADING_MAX_CHARS", 20000),
        }
        values.update({key: value for key, value in overrides.items() if value is not None})
        return cls(**values)
