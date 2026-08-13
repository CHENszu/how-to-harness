import os
from typing import Any, Dict, Optional
from .base import BaseTool

class FileReadTool(BaseTool):
    name: str = "file_read"
    description: str = "读取文件的内容，支持通过 offset 和 limit 截取部分行。"
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要读取的文件的绝对路径或相对路径"
            },
            "offset": {
                "type": "integer",
                "description": "从第几行开始读取 (1-indexed)",
                "default": 1
            },
            "limit": {
                "type": "integer",
                "description": "读取的行数",
            }
        },
        "required": ["file_path"]
    }

    def execute(self, file_path: str, offset: int = 1, limit: Optional[int] = None, **kwargs) -> str:
        try:
            if not os.path.exists(file_path):
                return f"文件未找到: {file_path}"
            
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
                
            if not lines:
                return f"文件是空的: {file_path}"
                
            start_idx = max(0, offset - 1)
            end_idx = start_idx + limit if limit is not None else len(lines)
            
            selected_lines = lines[start_idx:end_idx]
            
            # 加上行号
            numbered_lines = []
            for i, line in enumerate(selected_lines, start=start_idx + 1):
                numbered_lines.append(f"{i} | {line.rstrip()}")
                
            result = f"--- {file_path} (行 {start_idx + 1} 到 {end_idx}) ---\n"
            result += "\n".join(numbered_lines)
            return result
        except Exception as e:
            return f"读取文件失败: {str(e)}"