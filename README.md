# LLM 智能体 + MCP + CDP 网站爬取项目

这个项目用于爬取动态前端页面，并把页面中的产品功能整理出来。当前默认目标是：

`https://bjedures.bjedu.cn/ggzypt/#/ai/mark/detail?id=9c7f91783fb83cc08aa98036f939b4e2&name=%E9%A3%9E%E8%B1%A1%E6%99%BA%E8%83%BD%E4%BD%9C%E4%B8%9A`

## 结构

- `CDP crawler`：通过 Chrome DevTools Protocol 打开网页，等待前端接口返回并抽取正文、链接、网络响应和截图。
- `LLM agent`：用 OpenAI 兼容接口把页面材料整理成“产品功能”。没有 API key 时会自动使用规则提取兜底。
- `MCP server`：把 `crawl_product_features` 暴露为 MCP tool，方便接入支持 MCP 的客户端。
- `CLI`：本地一条命令跑完整流程。

## 本地运行

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
.venv\Scripts\python.exe -m agent_mcp_cdp crawl --headed --wait-ms 12000
```

这个站点入口会返回一次 `412` 脚本挑战；实测 headless 模式可能得到空白页，所以默认演示命令使用可见浏览器。如果爬其他普通站点，可以去掉 `--headed`。

如果你已经有 Chrome 或 Edge，并希望直接用它的 CDP：

```powershell
.venv\Scripts\python.exe -m agent_mcp_cdp crawl --headed
```

如果浏览器已经用远程调试端口启动：

```powershell
.venv\Scripts\python.exe -m agent_mcp_cdp crawl --cdp-url http://127.0.0.1:9222
```

## 配置 LLM

复制 `.env.example` 为 `.env`，填入 OpenAI 兼容配置：

```text
OPENAI_API_KEY=你的 key
OPENAI_BASE_URL=
OPENAI_MODEL=gpt-4o-mini
```

国内模型厂商只要兼容 OpenAI Chat Completions，也可以填自己的 `OPENAI_BASE_URL` 和模型名。

## 启动 MCP Server

```powershell
.venv\Scripts\python.exe -m agent_mcp_cdp mcp
```

MCP 工具名：`crawl_product_features`

参数：

- `url`：要爬取的页面 URL
- `product_name`：产品名，默认 `飞象智能作业`
- `wait_ms`：页面加载后额外等待时间
