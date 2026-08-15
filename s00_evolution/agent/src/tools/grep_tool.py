import re
import os
import glob
from typing import Any, Dict
from .base import BaseTool

class GrepTool(BaseTool):
    name: str = "grep"
    description: str = "使用正则表达式在文件中搜索特定内容。"
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "要搜索的正则表达式"
            },
            "path": {
                "type": "string",
                "description": "要搜索的起始目录或具体文件",
                "default": "."
            },
            "include": {
                "type": "string",
                "description": "仅在匹配此 glob 模式的文件中搜索，例如 '*.py'"
            }
        },
        "required": ["pattern"]
    }

    def execute(self, pattern: str, path: str = ".", include: str = None, **kwargs) -> str:
        try:
            regex = re.compile(pattern)
            results = []
            
            # 确定要搜索的文件列表
            files_to_search = []
            if os.path.isfile(path):
                files_to_search.append(path)
            elif os.path.isdir(path):
                search_pattern = include if include else "**/*"
                full_pattern = os.path.join(path, search_pattern)
                for f in glob.iglob(full_pattern, recursive=True):
                    if os.path.isfile(f):
                        files_to_search.append(f)
                    if len(files_to_search) >= 500:
                        results.append("[警告] 文件数过多，只搜索了前 500 个文件，请使用 include 参数缩小范围！")
                        break
            
            for file_path in files_to_search:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for i, line in enumerate(f, 1):
                            if regex.search(line):
                                results.append(f"{file_path}:{i}:{line.rstrip()}")
                except Exception:
                    continue # 忽略无法读取的文件(如二进制)
                    
            if not results:
                return f"未找到匹配 '{pattern}' 的内容。"
                
            # 限制返回行数避免过长
            MAX_RESULTS = 100
            if len(results) > MAX_RESULTS:
                res_str = "\n".join(results[:MAX_RESULTS])
                res_str += f"\n... (还有 {len(results) - MAX_RESULTS} 个匹配项被截断)"
                return res_str
            return "\n".join(results)
        except Exception as e:
            return f"搜索失败: {str(e)}"