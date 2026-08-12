# 12_mcp - 将 MCP 封装为 Agent 工具

本节展示了如何让 Agent 拥有调用 Model Context Protocol (MCP) 服务器的能力。

## 核心目标
1. **统一工具接口**：将 MCP 服务器封装为 `CallMcpTool`，对 Agent 屏蔽底层协议细节，使其像调用本地普通工具一样调用 MCP。
2. **多协议支持**：支持 `stdio` (本地子进程) 和 `http` (SSE) 两种标准的 MCP 通信协议。

## 如何运行
确保你已在 `harness` conda 环境中安装了 MCP 相关依赖 (`pip install mcp fastmcp`)。

**第一步：启动远程 HTTP MCP 服务器**
你需要打开一个新的终端，激活环境并启动 HTTP 服务。它会默认在后台挂起并监听 `http://localhost:8000/sse`：
```bash
conda activate harness
cd C:\Users\18085\Desktop\claude_code\2_学习\how-to-harness\s00_evolution\12_mcp
python dummy_http_server.py
```

**第二步：启动 Agent**
在另一个终端启动 Agent 主程序：
```bash
conda activate harness
cd C:\Users\18085\Desktop\claude_code\2_学习\how-to-harness\s00_evolution\12_mcp
python main.py
```

**第三步：测试对话**
你可以直接复制以下提示词要求 Agent：
- 测试 Stdio（本地调用）：
  > *"帮我调用本地 `dummy_mcp_server.py` 的 `hello` 工具，传参 name='大老板'，使用 stdio 协议"* 
- 测试 HTTP（远程调用）：
  > *"帮我通过 http 协议调用 `http://localhost:8000/sse` 上的 `fetch_weather` 工具，查询 Beijing 的天气"*

## 原理说明
像流水线上的多协议转换接头一样，`CallMcpTool` 在内部处理了 `stdio_client` 和 `streamable_http_client`，把 Agent 的自然语言请求转化为标准的 JSON-RPC 发送给 MCP Server，然后把返回的结构化结果提取为文本供大模型阅读。
