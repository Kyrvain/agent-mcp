from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_mcp_cdp.config import Settings


class SettingsFromEnvTests(unittest.TestCase):
    def test_from_env_parses_known_types(self) -> None:
        env = {
            "REMOTE_DEBUGGING_PORT": "9333",
            "BROWSER_HEADLESS": "false",
            "WAIT_AFTER_LOAD_MS": "1234",
            "SEARCH_CONFIDENCE_THRESHOLD": "0.75",
            "PROOFREADING_TIMEOUT_S": "2.5",
        }

        with patch.dict(os.environ, env, clear=False):
            settings = Settings.from_env()

        self.assertEqual(settings.remote_debugging_port, 9333)
        self.assertFalse(settings.browser_headless)
        self.assertEqual(settings.wait_after_load_ms, 1234)
        self.assertEqual(settings.search_confidence_threshold, 0.75)
        self.assertEqual(settings.proofreading_timeout_s, 2.5)

    def test_invalid_integer_env_has_clear_error(self) -> None:
        with patch.dict(os.environ, {"REMOTE_DEBUGGING_PORT": "abc"}, clear=False):
            with self.assertRaisesRegex(
                ValueError,
                "REMOTE_DEBUGGING_PORT must be an integer",
            ):
                Settings.from_env()

    def test_invalid_boolean_env_has_clear_error(self) -> None:
        with patch.dict(os.environ, {"BROWSER_HEADLESS": "maybe"}, clear=False):
            with self.assertRaisesRegex(
                ValueError,
                "BROWSER_HEADLESS must be a boolean",
            ):
                Settings.from_env()


if __name__ == "__main__":
    unittest.main()
