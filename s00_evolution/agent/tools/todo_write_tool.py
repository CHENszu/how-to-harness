import json
import os
from typing import Any, Dict
from .base import BaseTool

class TodoWriteTool(BaseTool):
    name: str = "todo_write"
    description: str = "管理一个 Markdown 格式的待办事项清单 (TODOs.md)。支持覆盖写入整个清单。"
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "要写入的待办事项列表。如果为空数组则清空清单。"
            }
        },
        "required": ["todos"]
    }

    def execute(self, todos: list, **kwargs) -> str:
        try:
            file_path = "TODOs.md"
            if not todos:
                if os.path.exists(file_path):
                    os.remove(file_path)
                return "已清空待办清单。"
                
            markdown_content = "# 📝 待办事项 (TODOs)\n\n"
            for i, task in enumerate(todos, 1):
                markdown_content += f"- [ ] {task}\n"
                
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
                
            return f"成功更新待办清单，共 {len(todos)} 项。\n当前内容:\n{markdown_content}"
        except Exception as e:
            return f"更新待办清单失败: {str(e)}"