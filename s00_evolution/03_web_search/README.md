# 03. Web Search 工具实现原理

在本模块中，我们将学习 OpenHarness 是如何实现 `web_search` 工具，从而赋予 Agent 联网搜索能力的。

## 核心实现机制

经过对源码 `web_search_tool.py` 的分析，我们发现它的实现非常轻量和巧妙：

### 1. 发起搜索 (The Engine)
它没有使用重量级的无头浏览器（如 Puppeteer 或 Playwright），也没有使用昂贵的第三方搜索 API（如 Google Custom Search）。
- 它使用了 `httpx` 发送最基础的 HTTP GET 请求。
- 目标端点默认指向了 **DuckDuckGo 的 HTML 极简版页面** (`https://html.duckduckgo.com/html/`)。
- 通过在 URL 参数中附带 `q=搜索词` 即可获取纯 HTML 格式的搜索结果。

### 2. 解析结果 (The Parser)
为了保持依赖的轻量，它甚至没有引入 `BeautifulSoup`。
- 完全依赖**正则表达式 (`re`)** 暴力提取。
- 它通过匹配特定的 class 属性（如 `result__snippet` 和 `result__a`）来抓取网页的片段（Snippet）、标题和链接。
- 对获取到的文本进行了 HTML 转义清洗（去除标签、处理换行）。

### 3. Pydantic 模型 (The Interface)
工具向大模型暴露了以下三个参数：
- `query` (必须)：搜索关键词。
- `max_results` (可选)：期望返回的最大结果数，默认 5，限制 1-10。
- `search_url` (可选)：允许手动覆盖搜索后端的地址。

## 运行测试

在虚拟环境中运行：
```bash
conda activate harness
python code_annotated.py
```

可以尝试向 Agent 提问：
- “请帮我搜索一下2024年巴黎奥运会中国队获得了多少金牌？”
- “帮我查一下现在 Python 的最新稳定版本是多少。”

Agent 会自主调用 `web_search` 工具去互联网上找答案！
