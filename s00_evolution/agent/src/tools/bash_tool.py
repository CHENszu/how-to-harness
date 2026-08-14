import subprocess
import re
from typing import Any, Dict
from .base import BaseTool

from rich.console import Console
from rich.prompt import Confirm

console = Console()

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

    def execute(self, command: str, status_indicator=None, **kwargs) -> str:
        # 敏感命令检测：删除操作
        danger_pattern = r'\b(rm|del|rmdir|rd|erase|remove-item)\b'
        if re.search(danger_pattern, command, re.IGNORECASE):
            # 如果存在外层的加载动画，先暂停它，以免吞掉用户的键盘输入
            if status_indicator:
                status_indicator.stop()
                
            console.print(f"\n⚠️ [bold red]警告：拦截到敏感操作！[/bold red]")
            console.print(f"Coco 想要执行以下删除命令：\n[bold yellow]{command}[/bold yellow]")
            is_confirmed = Confirm.ask("[bold red]是否允许执行此命令？[/bold red]", default=False)
            
            # 恢复加载动画
            if status_indicator:
                status_indicator.start()
            
            if not is_confirmed:
                return f"执行被拦截：用户拒绝了该操作 ({command})。"

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
