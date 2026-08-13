import subprocess
from typing import Any, Dict
from .base import BaseTool

class BashTool(BaseTool):
    name: str = "bash"
    description: str = "在 Windows 终端中执行命令行指令 (PowerShell)。"
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的命令"
            }
        },
        "required": ["command"]
    }

    def execute(self, command: str, **kwargs) -> str:
        try:
            # 针对 Windows 环境，使用 powershell 执行
            result = subprocess.run(
                ["powershell", "-Command", command],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=30
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[Error/Warning]:\n{result.stderr}"
            
            if not output.strip():
                return "命令执行成功，无输出。"
            return output[:4000] # 截断避免过长
        except subprocess.TimeoutExpired:
            return "命令执行超时 (30秒)。"
        except Exception as e:
            return f"执行失败: {str(e)}"
