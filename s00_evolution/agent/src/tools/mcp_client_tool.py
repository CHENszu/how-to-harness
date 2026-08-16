import asyncio
import os
from typing import Dict, Any, List, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MCPClientWrapper:
    """
    轻量级的 MCP Client 包装器
    负责管理与 MCP Server (如 GitHub MCP) 的底层通信
    """
    def __init__(self, server_command: str, server_args: List[str], env: Optional[Dict[str, str]] = None):
        self.server_parameters = StdioServerParameters(
            command=server_command,
            args=server_args,
            env=env or os.environ.copy()
        )
        self.session: Optional[ClientSession] = None
        self._exit_stack = None

    async def connect(self):
        """连接到 MCP Server 并初始化会话"""
        from contextlib import AsyncExitStack
        self._exit_stack = AsyncExitStack()
        
        # 启动 stdio 通信子进程
        read, write = await self._exit_stack.enter_async_context(stdio_client(self.server_parameters))
        
        # 建立 MCP 协议会话
        self.session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()
        return self

    async def get_tools(self) -> List[Any]:
        """获取 Server 暴露的所有工具 (Discovery 阶段)"""
        if not self.session:
            raise RuntimeError("MCP Client 未连接")
        response = await self.session.list_tools()
        return response.tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """调用 Server 的特定工具 (Execution 阶段)"""
        if not self.session:
            raise RuntimeError("MCP Client 未连接")
        
        response = await self.session.call_tool(name, arguments)
        
        # 将 MCP 的结果格式化为字符串返回给大模型
        if response.isError:
            return f"❌ 错误: {response.content}"
        
        # 简单拼接返回的内容
        result_texts = []
        for item in response.content:
            if item.type == "text":
                result_texts.append(item.text)
            else:
                result_texts.append(f"[未知类型: {item.type}]")
                
        return "\n".join(result_texts)

    async def cleanup(self):
        """清理资源"""
        if self._exit_stack:
            await self._exit_stack.aclose()


class DynamicMCPTool:
    """
    这是一个动态的工具包装器。
    它将 MCP Server 返回的一个工具 (Schema) 伪装成我们 Harness 的 BaseTool。
    """
    def __init__(self, mcp_client: MCPClientWrapper, mcp_tool_info: Any):
        self.mcp_client = mcp_client
        self._mcp_tool_name = mcp_tool_info.name
        self._mcp_tool_desc = mcp_tool_info.description
        self._mcp_input_schema = mcp_tool_info.inputSchema
        
    @property
    def name(self) -> str:
        return self._mcp_tool_name
        
    @property
    def description(self) -> str:
        return self._mcp_tool_desc or f"调用 MCP 工具: {self._mcp_tool_name}"
        
    @property
    def parameters(self) -> Dict[str, Any]:
        """获取工具的参数 Schema (适配 BaseTool)"""
        return self._mcp_input_schema
        
    def get_schema(self) -> Dict[str, Any]:
        """直接使用 MCP Server 提供的 Schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self._mcp_input_schema
            }
        }
        
    def execute(self, **kwargs) -> str:
        """
        注意：我们的 BaseTool.execute 是同步的，
        但 MCP 通信是异步的，所以需要用 asyncio.run 桥接。
        """
        import nest_asyncio
        nest_asyncio.apply()
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        try:
            return loop.run_until_complete(self.mcp_client.call_tool(self.name, kwargs))
        except Exception as e:
            return f"❌ MCP 工具调用失败: {str(e)}"
