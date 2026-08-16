from typing import List, Dict, Any, Optional

from .base import BaseTool
from .bash_tool import BashTool
from .web_search_tool import WebSearchTool
from .web_fetch_tool import WebFetchTool
# 类别1：文件操作
from .file_read_tool import FileReadTool
from .file_write_tool import FileWriteTool
from .glob_tool import GlobTool
from .grep_tool import GrepTool
# 类别7：任务规划与交互
from .todo_write_tool import TodoWriteTool
from .ask_user_question_tool import AskUserQuestionTool
# 类别8：子代理委派
from .search_agent_tool import SearchAgentTool
# 类别9：技能加载 (渐进式披露)
from .skills_list_tool import SkillsListTool
from .skill_view_tool import SkillViewTool

# 工具注册表
AVAILABLE_TOOLS = [
    BashTool(),
    WebSearchTool(),
    WebFetchTool(),
    FileReadTool(),
    FileWriteTool(),
    GlobTool(),
    GrepTool(),
    TodoWriteTool(),
    AskUserQuestionTool(),
    SearchAgentTool(),
    SkillsListTool(),
    SkillViewTool()
]

def get_tools_schema() -> List[Dict[str, Any]]:
    """获取适用于 LLM 的 tools 定义"""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters
            }
        }
        for t in AVAILABLE_TOOLS
    ]

def get_tool_by_name(name: str) -> Optional[BaseTool]:
    """根据名称获取工具实例"""
    for t in AVAILABLE_TOOLS:
        if t.name == name:
            return t
    return None
