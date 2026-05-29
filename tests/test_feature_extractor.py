from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_mcp_cdp.extractors.product_features import extract_summary


class FeatureExtractorTests(unittest.TestCase):
    def test_extract_summary_skips_raw_json_payload_lines(self) -> None:
        source = """
        [response]
        {"meta_group":"1,0,20","name":"超星泛雅智慧课程平台","_source":{"note":"后续不再提供运行监测数据"}}
        产品功能
        1.AI助教
        AI助教智能答疑结合了人工智能技术。
        """

        summary = extract_summary(source, "超星泛雅智慧课程平台")

        self.assertEqual(
            summary,
            "根据页面“产品功能”分段提取 超星泛雅智慧课程平台 的功能描述。",
        )
        self.assertNotIn("meta_group", summary)


if __name__ == "__main__":
    unittest.main()
