import asyncio
from mcp_client_tool import CallMcpTool
import traceback

tool = CallMcpTool()

print("Testing http...")
try:
    res2 = tool.execute(
        server_type="http",
        command_or_url="http://localhost:8000/sse",
        args=[],
        tool_name="fetch_weather",
        arguments={"city": "Beijing"}
    )
    print("Http result:")
    print(res2)
except Exception as e:
    traceback.print_exc()
