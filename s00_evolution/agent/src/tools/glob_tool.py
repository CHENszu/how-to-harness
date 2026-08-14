import os
import glob
from typing import Any, Dict
from .base import BaseTool

class GlobTool(BaseTool):
    name: str = "glob"
    description: str = "使用通配符模式在本地文件系统中搜索文件，例如 '**/*.py'。"
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "通配符模式，如 '*.md' 或 '**/*.py'"
            },
            "path": {
                "type": "string",
                "description": "搜索的起始目录，默认为当前工作目录",
                "default": "."
            }
        },
        "required": ["pattern"]
    }

    def execute(self, pattern: str, path: str = ".", **kwargs) -> str:
        try:
            full_pattern = os.path.join(path, pattern)
            # 开启 recursive=True 支持 **
            matches = glob.glob(full_pattern, recursive=True)
            
            # 过滤掉目录，只保留文件
            files = [m for m in matches if os.path.isfile(m)]
            
            if not files:
                return f"未找到匹配 '{pattern}' 的文件。"
                
            return f"找到 {len(files)} 个匹配的文件:\n" + "\n".join(files)
        except Exception as e:
            return f"搜索失败: {str(e)}"