import asyncio
from pydantic import BaseModel, Field
from typing import Dict, Any, List

from tools import BaseTool

class CallMcpToolInput(BaseModel):
    server_type: str = Field(description="服务器类型，'stdio' 或 'http'")
    command_or_url: str = Field(description="stdio 对应的可执行命令(如 python)，或 http 对应的 URL (例如 http://localhost:8000/sse)")
    args: List[str] = Field(default=[], description="stdio 对应的参数列表(如 ['my_mcp_server.py'])")
    tool_name: str = Field(description="要调用的 MCP 工具名称")
    arguments: dict = Field(default={}, description="传递给 MCP 工具的参数字典")

class CallMcpTool(BaseTool):
    name = "call_mcp"
    description = "连接外部的 MCP 服务器并调用其提供的工具。支持 stdio (本地进程) 和 http (SSE) 两种协议。"
    input_model = CallMcpToolInput
    
    def execute(self, **kwargs) -> str:
        # 因为 Agent 的 engine.py 是同步循环，所以我们在执行时启动 asyncio
        return asyncio.run(self._async_execute(**kwargs))
        
    async def _async_execute(self, server_type: str, command_or_url: str, args: List[str], tool_name: str, arguments: dict) -> str:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            
            print(f"  [CallMcp] 正在通过 {server_type} 连接 MCP Server...")
            
            if server_type == "stdio":
                # Stdio 模式：启动本地子进程并通过标准输入输出通信
                server_params = StdioServerParameters(command=command_or_url, args=args)
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        print(f"  [CallMcp] 正在调用远程工具: {tool_name}")
                        result = await session.call_tool(tool_name, arguments)
                        return self._format_result(result)
                        
            elif server_type == "http":
                # HTTP(SSE) 模式：连接远程 HTTP 服务
                from mcp.client.sse import sse_client
                
                async with sse_client(command_or_url) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        print(f"  [CallMcp] 正在调用远程工具: {tool_name}")
                        result = await session.call_tool(tool_name, arguments)
                        return self._format_result(result)
            else:
                return f"不支持的 server_type: {server_type}"
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"MCP 调用失败: {e}"

    def _format_result(self, result) -> str:
        parts = []
        for item in result.content:
            if getattr(item, "type", None) == "text":
                parts.append(getattr(item, "text", ""))
            else:
                parts.append(item.model_dump_json())
        return "\n".join(parts) if parts else "(无输出)"
