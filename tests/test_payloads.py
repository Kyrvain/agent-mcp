from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_mcp_cdp.cli import build_parser
from agent_mcp_cdp.config import Settings
from agent_mcp_cdp.models import CrawlResult, ProductFeatures, ProofreadingResult
from agent_mcp_cdp.proofreading import ProofreadingClient
from agent_mcp_cdp.schemas.payloads import build_agent_response, build_result_payload


class PayloadTests(unittest.TestCase):
    def test_agent_response_uses_current_feature_schema(self) -> None:
        features = ProductFeatures(
            product_name="demo",
            summary="summary",
            features=["feature"],
            evidence=["evidence"],
            warnings=["warning"],
        )

        payload = build_agent_response(features)

        self.assertEqual(list(payload), [
            "product_name",
            "summary",
            "features",
            "evidence",
            "warnings",
        ])
        self.assertNotIn("proofreading", payload)

    def test_payloads_include_proofreading_only_when_enabled(self) -> None:
        crawl = CrawlResult(
            requested_url="https://example.test",
            final_url="https://example.test/detail",
            title="Demo",
            text="body",
        )
        features = ProductFeatures(product_name="demo", summary="summary")
        proofreading = ProofreadingResult(
            service_url="https://proofreading.test",
            correct="corrected",
            result=[],
            raw_response='{"correct":"corrected","result":[]}',
        )

        result_payload = build_result_payload(crawl, features, proofreading)
        agent_response = build_agent_response(features, proofreading)

        self.assertIn("proofreading", result_payload)
        self.assertIn("proofreading", agent_response)
        self.assertEqual(agent_response["proofreading"]["correct"], "corrected")


class ProofreadingContentTests(unittest.TestCase):
    def test_feature_content_removes_line_breaks(self) -> None:
        client = ProofreadingClient(Settings(proofreading_max_chars=0))
        features = ProductFeatures(
            product_name="demo",
            summary="summary",
            features=["a\nb", "c\r\nd"],
        )

        self.assertEqual(client._build_content(features), "abcd")


class CliParserTests(unittest.TestCase):
    def test_cli_does_not_proofread_by_default(self) -> None:
        args = build_parser().parse_args(["crawl"])

        self.assertFalse(args.proofread)
        self.assertFalse(args.no_proofread)

    def test_cli_proofread_flag_is_explicit(self) -> None:
        args = build_parser().parse_args(["crawl", "--proofread"])

        self.assertTrue(args.proofread)

    def test_cli_batch_proofread_options(self) -> None:
        args = build_parser().parse_args(
            [
                "crawl",
                "--batch-proofread",
                "--refresh-catalog",
                "--batch-concurrency",
                "2",
                "--batch-limit",
                "3",
            ]
        )

        self.assertTrue(args.batch_proofread)
        self.assertTrue(args.refresh_catalog)
        self.assertEqual(args.batch_concurrency, 2)
        self.assertEqual(args.batch_limit, 3)


if __name__ == "__main__":
    unittest.main()
