from typing import Any, Dict
from .base import BaseTool

class AskUserQuestionTool(BaseTool):
    name: str = "ask_user_question"
    description: str = "遇到不确定、需要人类审批或选择时，主动向用户提问并暂停等待回复。"
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "要向用户提出的问题"
            }
        },
        "required": ["question"]
    }

    def execute(self, question: str, status_indicator=None, **kwargs) -> str:
        if status_indicator and hasattr(status_indicator, 'suspend'):
            status_indicator.suspend()
            
        try:
            from rich.console import Console
            from rich.prompt import Prompt
            console = Console()
            console.print(f"\n[bold yellow]🛑 Agent 提问: {question}[/bold yellow]")
            user_answer = Prompt.ask("[bold green]请输入你的回答[/bold green]")
            return f"用户的回答是: {user_answer}"
        except Exception as e:
            return f"获取用户回答失败: {str(e)}"
        finally:
            if status_indicator and hasattr(status_indicator, 'resume'):
                status_indicator.resume()