import os
from dotenv import load_dotenv
from tools import ToolRegistry, BashTool, WebSearchTool, SaveMemoryTool, WriteFileTool, ReadFileTool, SkillsListTool, SkillViewTool
from engine import run_agent_loop
from skills_loader import load_skills
from mcp_client_tool import CallMcpTool

def main():
    print("=======================================")
    print("  🛡️ 欢迎来到 Agent 实验室 (v0.12 - MCP集成) 🛡️")
    print("=======================================")
    print("本节我们为 Agent 引入了 CallMcpTool。")
    print("你可以尝试：")
    print(" 1. 问它：'帮我调用本地 dummy_mcp_server.py 的 hello 工具 (使用 stdio 协议)'")
    print(" 2. 问它：'帮我调用 http mcp server 的工具'")
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
    registry.register(CallMcpTool())
    
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
