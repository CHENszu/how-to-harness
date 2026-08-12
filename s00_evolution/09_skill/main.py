import os
from dotenv import load_dotenv
from tools import ToolRegistry, BashTool, WebSearchTool, SaveMemoryTool, WriteFileTool, ReadFileTool, SkillsListTool, SkillViewTool
from engine import run_agent_loop
from skills_loader import load_skills

def main():
    print("=======================================")
    print("  🛡️ 欢迎来到 Skill 按需加载机制测试 🛡️")
    print("=======================================")
    print("本节我们为 Agent 引入了 Skill（按需加载的扩展能力）机制。")
    print("注意：当前已开启 FULL_AUTO 模式，所有工具将全自动执行，无需手动确认。")
    print("你可以尝试：")
    print(" 1. 问它：'列出你当前拥有的所有可用技能'") 
    print(" 2. 问它：'使用 algorithmic-art 技能，帮我写一段代码'")
    print(" 3. 观察它是如何先调用 skills_list，再调用 skill_view 加载长指令，最后自动执行代码编写的。")
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
    
    # 3. 开启循环
    messages = []
    while True:
        try:
            user_msg = input("\n请输入你的问题 (输入 q 退出): ")
            if user_msg.lower() == 'q':
                break
            if not user_msg.strip():
                continue
                
            messages = run_agent_loop(user_msg, registry, messages)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n[发生错误]: {e}")

if __name__ == "__main__":
    main()
