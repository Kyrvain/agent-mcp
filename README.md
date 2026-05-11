# MCP + CDP 产品搜索与功能提取

输入产品名称，自动从北京教育数字资源交易平台的「AI 应用超市」找到匹配产品，爬取详情、提取产品功能，并把提取后的产品功能送入校对服务。

数据来源：`https://bjedures.bjedu.cn/ggzypt/#/ai/mark/index`（智链货架）

## 两种使用模式

### 搜索模式（推荐）

输入自然语言产品名称，系统会在「智链货架」页面的名称搜索框中查询，匹配产品后导航到详情页、提取功能并校对：

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
| CDP crawler | `cdp_browser.py` | 通过 Chrome DevTools Protocol 控制浏览器，使用列表页搜索框查询产品，拦截 API 响应 |
| 产品搜索 | `product_search.py` | 从列表页 API 响应中提取产品目录，并用关键词规则匹配 |
| 功能提取 | `agent.py` | 用规则从页面材料整理产品功能 |
| Proofreading | `proofreading.py` | 将 `product_features.features` 拼接后发送到校对服务 |
| MCP server | `mcp_server.py` | 暴露 `crawl_product_features` 为 MCP tool |
| CLI | `cli.py` | 命令行入口 |

## 工作原理

1. 打开 Chrome（使用 `.browser-profile` 持久化 profile，通过反爬检测）
2. 直接导航到 `/#/ai/mark/index`（智链货架），等待 SPA 初始化完成
3. 在列表页顶部「名称」输入框填入产品名并点击「查询」
4. 拦截搜索后的 `dse/service.do` API JSON 响应，提取候选产品名称、简介、厂商
5. 用户输入的产品名与候选目录做关键词打分匹配
6. 匹配成功后导航到对应产品详情页，爬取并提取功能
7. 将提取后的 `product_features.features` 去除换行后拼接，发送到校对服务

> `--list-only` / `list_only=true` 是全量目录场景，会保留翻页遍历；普通产品搜索不再逐页翻找。

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
# 先启动 Chrome（关键：--no-first-run 跳过登录提示）
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="d:/Projections/agent-mcp/.browser-profile" --no-first-run --no-default-browser-check

# 然后连接已有浏览器爬取
.venv\Scripts\python.exe -m agent_mcp_cdp crawl --search --cdp-url http://127.0.0.1:9222 --product-name "飞象智能作业"
```

## CLI 与 MCP 参数对照

CLI 和 MCP 是两种调用方式，参数不同，功能一一对应。

### CLI 模式（命令行）

```powershell
.venv\Scripts\python.exe -m agent_mcp_cdp crawl --search --headed --product-name "飞象智能作业"
```

| 参数 | 说明 |
|------|------|
| `--search, -s` | 搜索模式开关 |
| `--product-name NAME` | 产品名称（搜索模式的查询词） |
| `--url URL` | 直连模式：指定详情页 URL |
| `--list-only` | 仅列出产品目录，不爬详情 |
| `--confidence N` | 匹配置信度阈值（默认 0.3） |
| `--headed` | 显示浏览器窗口 |
| `--wait-ms MS` | 页面加载后额外等待时间 |
| `--no-proofread` | 跳过校对服务 |
| `--cdp-url URL` | 连接已有 CDP 端点 |
| `--browser-executable PATH` | 指定浏览器路径 |
| `--output-dir DIR` | 输出目录 |

### MCP 模式（Claude Code 对话中调用）

```json
crawl_product_features(product_name="飞象智能作业")
```

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `product_name` | str | 超星泛雅智慧课程平台 | 产品名称（搜索模式的查询词） |
| `url` | str | — | 直连模式：指定详情页 URL；不传时按 `product_name` 搜索 |
| `list_only` | bool | false | 仅返回产品目录，不爬详情 |
| `proofread` | bool | false | 是否把提取后的产品功能发送到校对服务 |
| `wait_ms` | int | — | 页面加载后额外等待时间 |

> MCP 没有 `--headed` 等 CLI 参数，这些由 `.env` 中的 `BROWSER_HEADLESS` 等配置控制。

### 对应关系

| 场景 | CLI | MCP |
|------|-----|-----|
| 搜索产品 | `--search --product-name "飞象"` | `product_name="飞象"` |
| 直连 URL | `--url "https://..."` | `url="https://..."` |
| 仅列出产品 | `--search --list-only` | `list_only=true` |
| 启用校对 | 默认启用 | `proofread=true` |
| 跳过校对 | `--no-proofread` | 默认跳过 |

## 配置校对服务

CLI 默认会把本次提取出的 `product_features.features` 作为产品详情发送到校对服务；MCP 调用中需要传 `proofread=true` 启用校对：

```text
PROOFREADING_API_URL=http://10.199.194.160:22235/api
PROOFREADING_TIMEOUT_S=30
PROOFREADING_MAX_CHARS=20000
```

发送内容只包含提取后的功能列表，不包含原始页面正文、接口响应、summary 或 evidence。拼接前会移除换行符，避免校对服务把换行误判为“多字”。

如需跳过校对：

```powershell
.venv\Scripts\python.exe -m agent_mcp_cdp crawl --search --headed --product-name "超星泛雅智慧课程平台" --no-proofread
```

如果要全局禁用校对，可以在 `.env` 中将 `PROOFREADING_API_URL` 留空。

## 接入 Claude Code

MCP Servers 配置在用户级全局文件 `C:\Users\<用户名>\.claude.json`（不是 `.claude\settings.json`）。在 `mcpServers` 中添加：

```json
"agent-mcp-cdp": {
  "command": "d:/Projections/agent-mcp/.venv/Scripts/python.exe",
  "args": ["-m", "agent_mcp_cdp", "mcp"],
  "env": {}
}
```

> `.claude.json` — MCP servers、项目注册等全局配置，由 Claude Code 自动管理（`/mcp` 面板操作的也是这个文件）。
> `.claude\settings.json` — 权限、hooks、环境变量等，分用户级和项目级，用户手动编辑。
>
> MCP Server 是全局基础设施，不绑定单个项目，所以放在 `.claude.json` 而非 `settings.json`。

**MCP 模式需要 `.env` 文件**（CLI 可以通过命令行参数覆盖，MCP 只能读 `.env`）。关键配置：

```text
BROWSER_HEADLESS=false    # 必须，headless 下网站返回空白页
PROOFREADING_API_URL=http://10.199.194.160:22235/api
```

重启 Claude Code 后，对话中可以直接用自然语言调用。

MCP 工具签名定义在 [mcp_server.py](src/agent_mcp_cdp/mcp_server.py)，当前只有一个工具 `crawl_product_features`。

## 输出

每次运行在 `data/runs/<时间戳>/` 下生成：

- `result.json` — 完整抓取数据 + 产品功能 + 校对结果
- `agent_response.json` — 返回给智能体的精简 JSON（产品功能 + 校对结果）
- `features.md` — Markdown 格式的产品功能和校对报告
- `page.png` — 页面截图（辅助参考）
