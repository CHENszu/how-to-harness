from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Dummy MCP Server")

@mcp.tool()
def hello(name: str) -> str:
    """A simple tool that says hello."""
    return f"Hello, {name}! This is from the MCP Server over stdio."

@mcp.tool()
def calculate_sum(a: int, b: int) -> int:
    """A simple tool that calculates the sum of two integers."""
    return a + b

if __name__ == "__main__":
    # Start the server using stdio by default
    mcp.run()
