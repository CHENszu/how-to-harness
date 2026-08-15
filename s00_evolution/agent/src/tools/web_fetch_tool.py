import re
import httpx
from typing import Any, Dict
from .base import BaseTool

class WebFetchTool(BaseTool):
    name: str = "web_fetch"
    description: str = "获取指定 URL 的网页纯文本内容。"
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "要抓取的完整 URL"
            }
        },
        "required": ["url"]
    }

    def execute(self, url: str, **kwargs) -> str:
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                response = client.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
                response.raise_for_status()
                html = response.text
            
            # 移除 script 和 style
            html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.IGNORECASE | re.DOTALL)
            # 移除所有标签
            text = re.sub(r'<[^>]+>', ' ', html)
            # 替换多个空白为单个空格
            text = re.sub(r'\s+', ' ', text).strip()
            
            return text[:4000] # 截断避免过长
        except Exception as e:
            return f"抓取网页失败: {str(e)}\n提示：该网页可能设置了防爬虫机制，或者网络连接受限。请放弃使用 web_fetch 抓取此页面，直接基于现有信息回答用户。"
