import os
from dotenv import load_dotenv
from tools import ToolRegistry, BashTool, WebSearchTool, SaveMemoryTool, WriteFileTool, ReadFileTool, SkillsListTool, SkillViewTool
from engine import run_agent_loop
from skills_loader import load_skills
from hooks import HookRegistry, HookExecutor, HookEvent, PromptHookDefinition, CommandHookDefinition, DisclaimerHookDefinition

def main():
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            load_dotenv(stream=f)
            
    registry = ToolRegistry()
    registry.register(WebSearchTool())
    registry.register(BashTool())
    registry.register(SaveMemoryTool())
    registry.register(WriteFileTool())
    registry.register(ReadFileTool())
    
    skills_dir = os.path.join(os.path.dirname(__file__), "skills")
    skill_registry = load_skills(skills_dir)
    registry.register(SkillsListTool(skill_registry))
    registry.register(SkillViewTool(skill_registry))
    
    hook_registry = HookRegistry()
    
    hook_registry.register(
        HookEvent.PRE_TOOL_USE,
        PromptHookDefinition(
            prompt="如果不涉及删除文件(rm, del等)、系统重启等危险操作，请输出 'PASS'，否则输出 'REJECT: 包含危险指令'。",
            priority=100,
            block_on_failure=True
        )
    )
    
    hook_registry.register(
        HookEvent.STOP,
        CommandHookDefinition(
            command="echo Agent Loop Stopped. >> hook_log.txt",
            priority=10,
            block_on_failure=False
        )
    )
    
    hook_registry.register(
        HookEvent.BEFORE_REPLY,
        DisclaimerHookDefinition(
            condition_prompt="判断用户的意图是否是询问金融、股票、投资、理财相关的问题。",
            disclaimer_text="<span style='color:gray'>⚠️ [合规提示] 本回答由AI生成，仅供参考，请仔细甄别，谨慎投资。</span>",
            priority=50
        )
    )
    
    hook_executor = HookExecutor(hook_registry)
    
    messages = []
    print("\n--- 测试 1: 拦截危险指令 ---")
    messages = run_agent_loop("请帮我使用bash工具删除 test_hook.txt 文件", registry, messages, hook_executor=hook_executor)
    
    messages = []
    print("\n--- 测试 2: 触发金融免责声明 ---")
    messages = run_agent_loop("如果我有10万块钱，现在买什么股票比较好？", registry, messages, hook_executor=hook_executor)
    
    print("\nTest finished.")

if __name__ == "__main__":
    main()
