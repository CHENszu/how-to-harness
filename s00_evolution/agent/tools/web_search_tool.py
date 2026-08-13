import json
import urllib.request
import urllib.parse
from typing import Any, Dict
from .base import BaseTool

class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = "在互联网上搜索信息 (免API Key)。"
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词"
            }
        },
        "required": ["query"]
    }

    def execute(self, query: str, **kwargs) -> str:
        try:
            # 这是一个不需要 API Key 的开源搜索接口（基于 SearxNG 的公开实例，或者更简单的 Wikipedia 兜底）
            # 为了确保这个 Harness 能 100% 在国内网络跑通，我们使用一个简单的 Wikipedia 接口做平替，
            # 实际生产中你应该在这里换成 Bing API 或 SerpApi
            
            # 由于国内网络环境限制，Wikipedia 也会报 SSL 错误。
            # 为了保证 Agent Loop 能够跑通不至于死循环，我们这里用一个非常基础的模拟返回。
            # 真实项目中，建议通过环境变量传入 Bing API Key，使用 bing search 接口。
            
            return (
                f"搜索结果 (模拟数据，因网络受限无法真实抓取):\n\n"
                f"1. 关于 {query} 的最新资讯\n"
                f"链接: https://example.com/news/{urllib.parse.quote(query)}\n"
                f"摘要: {query} 是一家知名的公司，近期在市场上表现活跃...\n\n"
                f"2. {query} 股票行情分析\n"
                f"链接: https://example.com/stock/{urllib.parse.quote(query)}\n"
                f"摘要: 分析师指出 {query} 当前市盈率合理，建议长期关注..."
            )
            
        except Exception as e:
            return f"搜索失败: {str(e)}"
