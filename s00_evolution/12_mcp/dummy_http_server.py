from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Dummy HTTP MCP Server")

@mcp.tool()
def fetch_weather(city: str) -> str:
    """Fetch weather for a city (mock implementation)."""
    return f"The weather in {city} is sunny and 25°C. (from HTTP MCP Server)"

if __name__ == "__main__":
    # Start the server using SSE transport
    mcp.run(transport='sse')
