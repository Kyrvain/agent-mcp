from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_mcp_cdp.models import CrawlResult, NetworkSnippet
from agent_mcp_cdp.product_search import (
    ProductListEntry,
    build_detail_url,
    match_product,
    parse_product_list,
    product_entry_from_dict,
    product_entry_to_dict,
)


def make_catalog_crawl(body: dict) -> CrawlResult:
    return CrawlResult(
        requested_url="https://example.test/catalog",
        final_url="https://example.test/catalog",
        title="catalog",
        text="",
        responses=[
            NetworkSnippet(
                url="https://bjedures.bjedu.cn/dse/service.do",
                status=200,
                content_type="application/json",
                body=json.dumps(body, ensure_ascii=False),
            )
        ],
    )


class ProductSearchParseTests(unittest.TestCase):
    def test_parse_product_list_extracts_unique_entries(self) -> None:
        crawl = make_catalog_crawl(
            {
                "hits": [
                    {
                        "_id": "1",
                        "_source": {
                            "name": "九章爱学",
                            "client_name": "北京公司",
                            "introduction": "智能作业平台",
                        },
                    },
                    {
                        "_id": "1",
                        "_source": {
                            "name": "重复产品",
                            "client_name": "重复公司",
                            "introduction": "重复",
                        },
                    },
                    {
                        "_id": "2",
                        "_source": {
                            "name": "超星泛雅智慧课程平台",
                            "client_name": "超星",
                        },
                    },
                ]
            }
        )

        entries = parse_product_list(crawl)

        self.assertEqual([entry._id for entry in entries], ["1", "2"])
        self.assertEqual(entries[0].name, "九章爱学")
        self.assertEqual(entries[0].introduction, "智能作业平台")

    def test_parse_product_list_ignores_invalid_responses(self) -> None:
        crawl = CrawlResult(
            requested_url="https://example.test",
            final_url="https://example.test",
            title="catalog",
            text="",
            responses=[
                NetworkSnippet(
                    url="https://example.test/not-service",
                    status=200,
                    content_type="application/json",
                    body='{"hits":[]}',
                ),
                NetworkSnippet(
                    url="https://bjedures.bjedu.cn/dse/service.do",
                    status=200,
                    content_type="application/json",
                    body="not json",
                ),
            ],
        )

        self.assertEqual(parse_product_list(crawl), [])

    def test_build_detail_url_encodes_product_name(self) -> None:
        url = build_detail_url(ProductListEntry(_id="abc", name="九章爱学"))

        self.assertIn("id=abc", url)
        self.assertIn("name=%E4%B9%9D%E7%AB%A0%E7%88%B1%E5%AD%A6", url)

    def test_product_entry_dict_includes_detail_url(self) -> None:
        entry = ProductListEntry(_id="abc", name="九章爱学")

        payload = product_entry_to_dict(entry)
        restored = product_entry_from_dict(payload)

        self.assertEqual(restored._id, "abc")
        self.assertEqual(restored.name, "九章爱学")
        self.assertEqual(payload["detail_url"], entry.detail_url)


class ProductMatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_match_product_exact_name(self) -> None:
        entry = ProductListEntry(_id="1", name="九章爱学")

        matched, confidence, warnings = await match_product("九章爱学", [entry])

        self.assertIs(matched, entry)
        self.assertEqual(confidence, 1.0)
        self.assertEqual(warnings, [])

    async def test_match_product_low_confidence(self) -> None:
        entry = ProductListEntry(_id="1", name="九章爱学")

        matched, confidence, warnings = await match_product("完全无关", [entry])

        self.assertIsNone(matched)
        self.assertEqual(confidence, 0.0)
        self.assertTrue(warnings)

    async def test_match_product_empty_catalog(self) -> None:
        matched, confidence, warnings = await match_product("九章爱学", [])

        self.assertIsNone(matched)
        self.assertEqual(confidence, 0.0)
        self.assertEqual(warnings, ["列表页未返回任何产品。"])


if __name__ == "__main__":
    unittest.main()
