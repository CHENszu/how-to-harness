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

    def execute(self, question: str, **kwargs) -> str:
        # 注意：在真实的 OpenHarness 中，这个工具会触发特定的 UI 挂起逻辑。
        # 在我们这个基础的 CLI 版本中，我们直接调用 python 内置的 input() 来阻塞当前线程并等待用户输入。
        try:
            print("\n" + "="*40)
            print("🛑 [Agent 提问拦截]")
            print(f"Agent: {question}")
            print("="*40)
            
            user_answer = input("请输入你的回答: ")
            return f"用户的回答是: {user_answer}"
        except Exception as e:
            return f"获取用户回答失败: {str(e)}"