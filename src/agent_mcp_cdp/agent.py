from __future__ import annotations

import json
import re
from typing import Any

from .config import Settings
from .models import CrawlResult, ProductFeatures


class ProductFeatureAgent:
    def __init__(self, settings: Settings, use_llm: bool = True) -> None:
        self.settings = settings
        self.use_llm = use_llm

    async def extract(self, crawl: CrawlResult, product_name: str) -> ProductFeatures:
        warnings: list[str] = []
        source = crawl.source_text()

        if len(source.strip()) < 50:
            return ProductFeatures(
                product_name=product_name,
                summary="页面内容不足，无法提取产品功能。",
                warnings=[
                    "抓取产出文本过少，请检查列表页/搜索步骤或页面是否需要登录。"
                ],
                llm_used=False,
            )

        if self.use_llm and self.settings.openai_api_key:
            try:
                return await self._extract_with_llm(source, product_name)
            except Exception as exc:
                warnings.append(f"LLM 提取失败，已切换到规则提取：{exc}")

        result = self._extract_with_rules(source, product_name)
        result.warnings.extend(warnings)
        if not self.settings.openai_api_key:
            result.warnings.append("未配置 OPENAI_API_KEY，本次使用规则提取。")
        return result

    async def _extract_with_llm(self, source: str, product_name: str) -> ProductFeatures:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
            timeout=120.0,
        )
        context = source[:28000]
        response = await client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=0.1,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是教育产品和招投标页面分析智能体。"
                        "只基于用户提供的抓取材料提取信息；不确定时写入 warnings。"
                        "严格输出 JSON，字段：product_name, summary, features, evidence, warnings。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"请从下面抓取材料中提取「{product_name}」的产品功能。\n"
                        "features 是中文字符串数组，每项是一个明确功能；"
                        "evidence 是支撑功能判断的短证据文本数组。\n\n"
                        f"抓取材料：\n{context}"
                    ),
                },
            ],
        )
        content = response.choices[0].message.content or "{}"
        payload = parse_json_object(content)
        return ProductFeatures(
            product_name=str(payload.get("product_name") or product_name),
            summary=str(payload.get("summary") or ""),
            features=string_list(payload.get("features")),
            evidence=string_list(payload.get("evidence")),
            warnings=string_list(payload.get("warnings")),
            llm_used=True,
        )

    def _extract_with_rules(self, source: str, product_name: str) -> ProductFeatures:
        exact_features = extract_product_function_section(source)
        if exact_features:
            summary = extract_summary(source, product_name)
            return ProductFeatures(
                product_name=product_name,
                summary=summary,
                features=exact_features,
                evidence=exact_features[:8],
                llm_used=False,
            )

        lines = normalize_lines(source)
        keyword_pattern = re.compile(
            r"功能|支持|提供|智能|作业|批改|练习|学情|分析|报告|推荐|教师|学生|课堂|"
            r"题目|题库|答疑|错题|数据|管理|资源|AI|大模型"
        )
        noisy_pattern = re.compile(
            r"^\s*(首页|登录|注册|返回|更多|暂无|加载中|版权所有|京ICP备|联系我们)\s*$"
        )

        evidence: list[str] = []
        seen: set[str] = set()
        for line in lines:
            if len(line) < 6 or noisy_pattern.search(line):
                continue
            if not keyword_pattern.search(line):
                continue
            compact = re.sub(r"\s+", "", line)
            if compact in seen:
                continue
            seen.add(compact)
            evidence.append(line)
            if len(evidence) >= 16:
                break

        features = build_feature_candidates(evidence, product_name)
        warnings = []
        if not evidence:
            warnings.append("页面正文或接口文本过少，规则提取未找到可靠功能证据。")

        summary = (
            f"根据抓取文本，{product_name} 与智能作业、作业批改、学情分析等教学场景相关。"
            if features
            else f"未能从当前抓取材料中稳定提取 {product_name} 的产品功能。"
        )
        return ProductFeatures(
            product_name=product_name,
            summary=summary,
            features=features,
            evidence=evidence[:8],
            llm_used=False,
            warnings=warnings,
        )


def extract_product_function_section(source: str) -> list[str]:
    match = re.search(r"产品功能\s*(.*?)(?:\n产品场景|\n产品亮点|\n产品功能相关图片|\Z)", source, re.S)
    if not match:
        return []

    section = match.group(1)
    pattern = re.compile(
        r"(?:^|\n)\s*(\d+\.\s*[^\n]+)\n+\s*(.*?)(?=\n+\s*\d+\.\s*[^\n]+|\Z)",
        re.S,
    )
    features: list[str] = []
    for heading, body in pattern.findall(section):
        heading = re.sub(r"\s+", " ", heading).strip()
        body = re.sub(r"\s+", " ", body).strip()
        if not body:
            continue
        features.append(f"{heading}：{body}")
    return features


def extract_summary(source: str, product_name: str) -> str:
    for line in normalize_lines(source):
        if product_name in line and any(token in line for token in ("覆盖", "支持", "提升", "产品")):
            return line
    return f"根据页面“产品功能”分段提取 {product_name} 的功能描述。"


def normalize_lines(source: str) -> list[str]:
    raw_lines = re.split(r"[\n。；;]+", source)
    result = []
    for line in raw_lines:
        line = re.sub(r"\s+", " ", line).strip(" -\t\r\n")
        if line:
            result.append(line)
    return result


def build_feature_candidates(evidence: list[str], product_name: str) -> list[str]:
    rules = [
        ("作业|练习|布置", "支持教师布置、组织和管理学生作业/练习。"),
        ("批改|判题|阅卷", "支持作业自动批改或辅助批改，提升教师批阅效率。"),
        ("学情|分析|报告|数据", "提供学情数据分析和报告，帮助教师了解学生掌握情况。"),
        ("错题|薄弱|推荐", "基于错题或薄弱点提供个性化巩固与推荐。"),
        ("答疑|讲解|大模型|AI|智能", "提供 AI 辅助讲解、答疑或智能学习支持。"),
        ("题库|资源|试题", "提供题库、试题或教学资源支撑作业场景。"),
        ("教师|学生|课堂|学校", "覆盖教师教学和学生学习的校内应用流程。"),
    ]
    joined = "\n".join(evidence)
    features = [text for pattern, text in rules if re.search(pattern, joined)]
    if not features and evidence:
        features = [f"围绕 {product_name} 页面文本中的作业与教学场景提供功能支持。"]
    return dedupe(features)


def parse_json_object(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, flags=re.S)
        if match:
            return json.loads(match.group(0))
        raise


def string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
