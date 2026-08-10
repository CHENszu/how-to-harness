# s19: MCP Tools — 万能转换插头，即插即用

> *"外接工具, 标准协议"* — 发现、组装、调用，Agent 根本不需要知道工具是谁写的。
>
> **Harness 层**: 插件 — 外部能力通过标准协议无缝接入。

---

## 问题：手写工具的噩梦

从 s01 到 s18，我们的 Agent 拥有了读写文件、执行 bash、创建任务、开辟 Worktree 等强大的能力。但这些工具全都是我们**一行一行用 Python 手写**出来的。

现在，你希望 Agent 能够：
1. 查公司的 Jira 给你总结 bug；
2. 连上团队的 Notion 搜索文档；
3. 直接连本地的 MySQL 数据库查数据。

难道我们要为了每个外部服务，重新写一套认证、请求、解析结果的 Python 工具函数吗？这不仅工作量巨大，而且无法复用。

这就好比你每买一个新电器，都要专门请电工为它拉一根专用的电线，太折腾了。

---

## 解决方案：安装“万能转换插头”（MCP 协议）

我们需要一个标准插座。**MCP（Model Context Protocol）** 就是 AI 界的“万能转换插头”协议。

只要外部服务（MCP Server）遵守这个协议，告诉 Agent：“我有这些工具（`tools/list`），你可以这样调用我（`tools/call`）”，Agent 就能**自动发现**并使用它们，不管这个服务是用 Java、Go 还是 Node.js 写的。

本章我们引入了：
1. **`MCPClient`**：Agent 的插座面板，负责连接外部服务。
2. **`connect_mcp` 工具**：大模型可以通过调用这个工具，主动“插上”一个外部服务。
3. **`assemble_tool_pool`**：系统会自动把“内置工具”和“刚刚发现的外部 MCP 工具”拼装成一个超级工具箱，喂给大模型。

---

## 工作原理：代码中的体现

### 1. 发现与调用
在我们的教学代码中，我们用 `MCPClient` 类模拟了这个过程。它能注册（发现）外部工具，并提供统一的调用接口：
```python
class MCPClient:
    def call_tool(self, tool_name: str, args: dict) -> str:
        handler = self._handlers.get(tool_name)
        if not handler:
            return f"MCP error: unknown tool '{tool_name}'"
        return handler(**args)
```
*注：教学版用 Python 函数模拟了外部服务器。在真实的 Claude Code 中，这里是通过子进程（stdio）或 HTTP/SSE 发送标准的 JSON-RPC 请求。*

### 2. 动态组装工具池
当 Agent 连接了外部服务后，系统需要把外部工具塞给大模型。
为了防止外部工具和内置工具重名（比如外部也有一个叫 `search` 的工具），我们会对外部工具强制加前缀规范化：`mcp__{server}__{tool}`。
```python
def assemble_tool_pool() -> tuple[list[dict], dict]:
    tools = list(BUILTIN_TOOLS)
    handlers = dict(BUILTIN_HANDLERS)
    for server_name, mcp_client in mcp_clients.items():
        for tool_def in mcp_client.tools:
            # 加上防冲突前缀
            prefixed = f"mcp__{server_name}__{tool_def['name']}"
            tools.append({...})
            handlers[prefixed] = ...
    return tools, handlers
```
例如，连接了 `docs` 服务后，它的 `search` 工具在 Agent 眼里就变成了 `mcp__docs__search`。

### 3. 告别提示词缓存
在之前的章节中，为了省钱和提速，我们缓存了 System Prompt（包含工具列表）。
但现在，大模型随时可能调用 `connect_mcp` 接入新插件，**工具池是动态变化的**！
如果继续用旧缓存，大模型就看不见新接入的工具。因此，在 `agent_loop` 中，一旦发现大模型连接了新服务，必须立刻刷新工具池和系统提示词。

---

## 相对 s18 的变更总结

| 组件 | 之前 (s18) | 之后 (s19) |
|------|-----------|-----------|
| 工具来源 | 100% 本地 Python 手写 | 内置手写工具 + MCP 动态接入的外部工具 |
| 工具管理 | 固定的全局变量 | `assemble_tool_pool` 动态拼装大工具池 |
| 命名冲突防范 | 无 | 强制增加 `mcp__{server}__{tool}` 规范化前缀 |
| 系统提示词缓存 | 有缓存，提升性能 | 取消缓存，应对动态扩充的工具列表 |
| 新增机制 | — | 模拟的 `MCPClient`、`connect_mcp` 工具 |

---

## 试一下

在终端中运行：
```sh
python s19_mcp_plugin/code_annotated.py
```

试试这些 Prompt：
> "Connect to the docs MCP server and search for something."
> 
> "Connect to the deploy server and trigger a deployment."
> 
> "Connect both servers — what tools are now available?"

观察重点：
1. Agent 是否成功调用了 `connect_mcp` 工具？
2. 连接后，接下来的思考轮次中，Agent 是否能正确识别并调用名为 `mcp__docs__search` 这样的外接工具？

---

## 接下来

现在，我们的 Agent 已经变成了真正的“完全体”：
它有**工具调用**、**Hook拦截**、**任务管理 (Todo)**、**异步后台任务**、**Cron 定时调度**、**多 Agent 团队协作**、**Worktree 物理隔离**，现在还插上了 **MCP 插件翅膀**。

但这 19 章就像是一块块散落的乐高积木，每一章我们只关注一个局部。
真实的 Agent 系统不可能这样拆散运行，我们需要一个把它们全部拼装在一起的“终极主板”。

**s20 Comprehensive Agent**，我们将把前 19 章的所有机制大合体，打造出属于你自己的、完整运行的超级 Agent 架构！