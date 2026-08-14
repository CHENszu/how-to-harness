import os
from typing import Any, Dict
from .base import BaseTool

class FileWriteTool(BaseTool):
    name: str = "file_write"
    description: str = "将内容写入文件，会覆盖已有的内容。如果父目录不存在会自动创建。"
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要写入的文件的绝对路径或相对路径"
            },
            "content": {
                "type": "string",
                "description": "要写入的完整内容"
            }
        },
        "required": ["file_path", "content"]
    }

    def execute(self, file_path: str, content: str, **kwargs) -> str:
        try:
            # 根据 project_memory 约束：必须在写入前自动创建不存在的父目录
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            return f"成功写入文件: {file_path} (共 {len(content)} 字符)"
        except Exception as e:
            return f"写入文件失败: {str(e)}"