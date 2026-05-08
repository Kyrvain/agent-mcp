# LLM 智能体 + MCP + CDP 产品搜索与功能提取

输入产品名称，自动从北京教育数字资源交易平台的「AI 应用超市」找到匹配产品，爬取详情并提取产品功能。

数据来源：`https://bjedures.bjedu.cn/ggzypt/#/ai/mark/index`（智链货架）

## 两种使用模式

### 搜索模式（推荐）

输入自然语言产品名称，系统自动搜索匹配、导航到详情页、提取功能：

```powershell
# 搜索产品
.venv\Scripts\python.exe -m agent_mcp_cdp crawl --search --headed --product-name "飞象智能作业"

# 只列出所有可用产品，不爬取详情
.venv\Scripts\python.exe -m agent_mcp_cdp crawl --search --headed --list-only
```

### 直连模式

已知产品详情页 URL 时直接爬取：

```powershell
.venv\Scripts\python.exe -m agent_mcp_cdp crawl --headed --url "https://bjedures.bjedu.cn/ggzypt/#/ai/mark/detail?id=..."
```

## 结构

| 模块 | 文件 | 作用 |
|------|------|------|
| CDP crawler | `cdp_browser.py` | 通过 Chrome DevTools Protocol 控制浏览器，拦截 API 响应，自动翻页 |
| 产品搜索 | `product_search.py` | 从列表页 API 响应中提取产品目录，LLM/关键词匹配 |
| LLM agent | `agent.py` | 用 OpenAI 兼容接口从页面材料整理产品功能（无 Key 时规则兜底） |
| MCP server | `mcp_server.py` | 暴露 `crawl_product_features` 为 MCP tool |
| CLI | `cli.py` | 命令行入口 |

## 工作原理

1. 打开 Chrome（使用 `.browser-profile` 持久化 profile，通过反爬检测）
2. 先导航到详情页建立会话，再通过 SPA hash 路由跳转到列表页
3. 拦截 `dse/service.do` API 的 JSON 响应，提取产品名称、简介、厂商
4. 自动点击 Element UI 分页器遍历所有页面（当前约 48 个产品）
5. 用户输入的产品名与目录匹配（有 API Key 用 LLM，否则用关键词打分）
6. 匹配成功后导航到对应产品详情页，爬取并提取功能

## 本地运行

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
```

站点入口有 `412` 脚本挑战，headless 模式可能拿到空白页，建议使用 `--headed`。

如果你已有 Chrome 或 Edge：

```powershell
.venv\Scripts\python.exe -m agent_mcp_cdp crawl --search --headed --product-name "超星泛雅智慧课程平台"
```

如果浏览器已经用远程调试端口启动：

```powershell
.venv\Scripts\python.exe -m agent_mcp_cdp crawl --search --cdp-url http://127.0.0.1:9222 --product-name "飞象智能作业"
```

## CLI 参数

```
crawl 子命令：
  --search, -s          搜索模式：输入产品名称，自动查找匹配
  --product-name NAME   产品名称（搜索模式的输入，直连模式用于提取提示）
  --url URL             直连模式：指定详情页 URL
  --list-only           仅列出可用产品，不爬取详情
  --confidence N        匹配置信度阈值（默认 0.3）
  --headed              显示浏览器窗口
  --wait-ms MS          页面加载后额外等待时间
  --no-llm              强制规则提取，不调用 LLM
  --cdp-url URL         连接已有 CDP 端点
  --browser-executable  指定浏览器路径
  --output-dir DIR      输出目录
```

## 配置 LLM

复制 `.env.example` 为 `.env`，填入 OpenAI 兼容配置：

```text
OPENAI_API_KEY=你的 key
OPENAI_BASE_URL=
OPENAI_MODEL=gpt-4o-mini
```

有 Key 时：产品匹配和功能提取都用 LLM，准确度更高。
无 Key 时：关键词匹配 + 规则提取兜底，基础可用。

国内模型厂商只要兼容 OpenAI Chat Completions，也可以填自己的 `OPENAI_BASE_URL` 和模型名。

## 接入 Claude Code

编辑 `C:\Users\<用户名>\.claude.json`，在 `mcpServers` 中添加：

```json
"agent-mcp-cdp": {
  "command": "d:/Projections/agent-mcp/.venv/Scripts/python.exe",
  "args": ["-m", "agent_mcp_cdp", "mcp"],
  "env": {}
}
```

重启 Claude Code 后，对话中可以直接用自然语言调用：

> 查一下飞象智能作业的产品功能

MCP 工具名：`crawl_product_features`

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `url` | str | — | 直连模式：详情页 URL |
| `product_name` | str | `超星泛雅智慧课程平台` | 产品名称 |
| `search_product` | str | — | 搜索模式：触发自动搜索匹配 |
| `list_only` | bool | false | 仅返回产品目录，不爬详情 |
| `wait_ms` | int | — | 页面加载后等待时间 |

## 输出

每次运行在 `data/runs/<时间戳>/` 下生成：

- `result.json` — 完整抓取数据 + 产品功能
- `features.md` — Markdown 格式的产品功能报告
- `page.png` — 页面截图（辅助参考）
