from typing import Any, Dict
from .base import BaseTool
import json

class SearchAgentTool(BaseTool):
    name: str = "search_agent"
    description: str = "【必须优先使用】启动一个专门负责信息检索、代码阅读、项目结构分析和问题排查的子代理 (Search Sub-Agent)。当用户要求你'分析项目'、'查看代码'、'阅读长文件'或进行任何宽泛的调研任务时，你必须调用此工具，不要自己去手动读文件或执行 Bash。它会自主执行所有的底层排查工作，并返回精炼的总结报告给你。"
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "task_description": {
                "type": "string",
                "description": "详细描述你希望这个子代理去查找、阅读或排查的内容。描述越清晰，子代理返回的结果越准确。"
            }
        },
        "required": ["task_description"]
    }

    def execute(self, task_description: str, **kwargs: Any) -> str:
        # 为了避免循环依赖，我们在函数内部导入
        from engine import AgentEngine
        
        # 为了让子代理只能使用安全/只读的工具，我们需要手动导入它能用的工具
        from .file_read_tool import FileReadTool
        from .glob_tool import GlobTool
        from .grep_tool import GrepTool
        from .web_search_tool import WebSearchTool
        from .web_fetch_tool import WebFetchTool
        
        allowed_tools = [
            FileReadTool(),
            GlobTool(),
            GrepTool(),
            WebSearchTool(),
            WebFetchTool()
        ]
        
        # 实例化子代理引擎，赋予专属的 search_agent persona，并限制其可用工具
        # 我们这里不传递 api_key，让 AgentEngine 自动去读当前进程的环境变量 (或使用外层注入的环境)
        # 如果当前没有环境变量，那么使用这个工具的主进程其实也无法工作
        import os
        sub_agent = AgentEngine(
            persona="search_agent",
            allowed_tools=allowed_tools,
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
            model=os.environ.get("MODEL_NAME", "deepseek-chat"),
            max_turns=10
        )
        
        if kwargs.get("status_indicator") and hasattr(kwargs.get("status_indicator"), 'update'):
            kwargs.get("status_indicator").update("🚀 正在启动 Search Agent 深入探查...")
        else:
            print(f"\n🚀 [Sub-Agent] 正在启动 Search Agent 深入探查...")
            print(f"🎯 [Sub-Agent 任务]: {task_description}")
        
        try:
            # 传递 status_indicator (如果有)
            status_indicator = kwargs.get("status_indicator")
            result = sub_agent.run(task_description, status_indicator=status_indicator)
            if not status_indicator:
                print(f"\n✅ [Sub-Agent] 探查完毕，结果已返回给主 Agent。")
            return f"[Search Agent 汇报结果]:\n{result}"
        except Exception as e:
            return f"[Search Agent 运行出错]: {str(e)}"
