import os
from dotenv import load_dotenv
from tools import ToolRegistry, BashTool, WebSearchTool, SaveMemoryTool, WriteFileTool, ReadFileTool, SkillsListTool, SkillViewTool
from engine import run_agent_loop
from skills_loader import load_skills
from hooks import HookRegistry, HookExecutor, HookEvent, PromptHookDefinition, CommandHookDefinition, DisclaimerHookDefinition

def main():
    print("=======================================")
    print("  🛡️ 欢迎来到 Hook 卡点质检机制测试 🛡️")
    print("=======================================")
    print("本节我们为 Agent 引入了 Hook 机制（汽车流水线的质检员）。")
    print("注意：当前已开启 FULL_AUTO 模式，但 Hook 可以拦截危险操作。")
    print("你可以尝试：")
    print(" 1. 尝试让它执行 '删除 test_hook.txt' -> 观察 Prompt Hook 是否拦截。") 
    print(" 2. 问它：'如果我有10万块钱，现在买什么股票比较好？' -> 观察 BEFORE_REPLY Hook 是否自动追加免责声明。")
    print(" 3. 观察 Agent Loop 结束后是否触发了 STOP Hook。")
    print(" 4. 按 'q' 退出。")
    
    # 1. 加载环境变量
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            load_dotenv(stream=f)
            
    # 2. 注册工具与技能
    registry = ToolRegistry()
    registry.register(WebSearchTool())
    registry.register(BashTool())
    registry.register(SaveMemoryTool())  # 注入记忆写入工具
    registry.register(WriteFileTool())
    registry.register(ReadFileTool())    # 注入读文件工具（防止找模板时卡死）
    
    # 加载 Skill
    skills_dir = os.path.join(os.path.dirname(__file__), "skills")
    skill_registry = load_skills(skills_dir)
    registry.register(SkillsListTool(skill_registry))
    registry.register(SkillViewTool(skill_registry))
    
    # 2.5 注册 Hooks (质检员排班)
    hook_registry = HookRegistry()
    
    # 注册一个 Prompt Hook：禁止调用 bash 执行危险命令
    hook_registry.register(
        HookEvent.PRE_TOOL_USE,
        PromptHookDefinition(
            prompt="如果不涉及删除文件(rm, del等)、系统重启等危险操作，请输出 'PASS'，否则输出 'REJECT: 包含危险指令'。",
            priority=100,
            block_on_failure=True
        )
    )
    
    # 注册一个 Command Hook：Agent 停机时记录日志
    hook_registry.register(
        HookEvent.STOP,
        CommandHookDefinition(
            command="echo Agent Loop Stopped. >> hook_log.txt",
            priority=10,
            block_on_failure=False
        )
    )
    
    # 注册一个 Disclaimer Hook：判断是否为金融问题，并追加免责声明
    hook_registry.register(
        HookEvent.BEFORE_REPLY,
        DisclaimerHookDefinition(
            condition_prompt="判断用户的意图是否是询问金融、股票、投资、理财相关的问题。",
            disclaimer_text="<span style='color:gray'>⚠️ [合规提示] 本回答由AI生成，仅供参考，请仔细甄别，谨慎投资。</span>",
            priority=50
        )
    )
    
    hook_executor = HookExecutor(hook_registry)
    
    # 3. 开启循环
    messages = []
    while True:
        try:
            user_msg = input("\n请输入你的问题 (输入 q 退出): ")
            if user_msg.lower() == 'q':
                break
            if not user_msg.strip():
                continue
                
            messages = run_agent_loop(user_msg, registry, messages, hook_executor=hook_executor)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n[发生错误]: {e}")

if __name__ == "__main__":
    main()
