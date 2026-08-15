import os
import httpx
from typing import Any, Dict
from .base import BaseTool

class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = "使用 SerpApi (Google Search) 在互联网上搜索最新信息。"
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

    def _fallback_duckduckgo(self, query: str) -> str:
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, region='wt-wt', safesearch='moderate', max_results=5))
            
            if not results:
                return f"未找到关于 '{query}' 的搜索结果 (降级DuckDuckGo)。"
                
            lines = [f"搜索关键词 '{query}' 的 DuckDuckGo 结果 (未配置 SerpApi 时的降级方案):"]
            for index, result in enumerate(results, start=1):
                title = result.get("title", "无标题")
                link = result.get("href", "")
                snippet = result.get("body", "")
                
                lines.append(f"{index}. {title}")
                lines.append(f"   URL: {link}")
                if snippet:
                    lines.append(f"   摘要: {snippet}")
                    
            return "\n".join(lines)
        except ImportError:
            return "搜索失败：未配置 SERPAPI_API_KEY，且未安装 duckduckgo-search 模块用于降级。请运行 `pip install duckduckgo-search`。"
        except Exception as e:
            return f"DuckDuckGo 降级搜索失败: {str(e)}"

    def execute(self, query: str, **kwargs) -> str:
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            return self._fallback_duckduckgo(query)

        try:
            endpoint = "https://serpapi.com/search"
            params = {
                "q": query,
                "api_key": api_key,
                "engine": "google",
                "hl": "zh-cn", # 偏好中文结果
                "gl": "cn",    # 偏好中国地区
                "num": 5       # 返回 5 条结果
            }

            with httpx.Client(timeout=20.0) as client:
                response = client.get(endpoint, params=params)
                response.raise_for_status()
                
            data = response.json()
            
            # 解析自然搜索结果
            organic_results = data.get("organic_results", [])
            if not organic_results:
                return f"未找到关于 '{query}' 的搜索结果。"

            lines = [f"搜索关键词 '{query}' 的 Google 结果:"]
            for index, result in enumerate(organic_results, start=1):
                title = result.get("title", "无标题")
                link = result.get("link", "")
                snippet = result.get("snippet", "")
                
                lines.append(f"{index}. {title}")
                lines.append(f"   URL: {link}")
                if snippet:
                    lines.append(f"   摘要: {snippet}")
                    
            return "\n".join(lines)
            
        except httpx.HTTPError as exc:
            return f"网络请求失败 (SerpApi): {exc}"
        except Exception as e:
            return f"搜索解析过程发生错误: {str(e)}"
