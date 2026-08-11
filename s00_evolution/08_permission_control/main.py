import os
from dotenv import load_dotenv
from tools import ToolRegistry, BashTool, WebSearchTool, SaveMemoryTool, WriteFileTool
from engine import run_agent_loop

def main():
    print("=======================================")
    print("  🛡️ 欢迎来到权限管控 (Permission Control) 测试 🛡️")
    print("=======================================")
    print("本节我们为 Agent 引入了 DEFAULT, PLAN, FULL_AUTO 三种权限模式。")
    print("默认情况下处于 DEFAULT 模式，只读工具(如搜索)自动执行，而变更工具(如bash,写文件)需要你的确认。")
    print("你可以尝试：")
    print(" 1. 问它：'帮我搜索一下今天的天气' (应该自动执行搜索)")
    print(" 2. 问它：'帮我新建一个 test_perm.txt 并写入 hello' (应该会弹窗询问你是否允许)")
    print(" 3. 拒绝它的执行，观察它的反应。")
    print(" 4. 按 'q' 退出。")
    
    # 1. 加载环境变量
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            load_dotenv(stream=f)
            
    # 2. 注册工具
    registry = ToolRegistry()
    registry.register(WebSearchTool())
    registry.register(BashTool())
    registry.register(SaveMemoryTool())  # 注入记忆写入工具
    registry.register(WriteFileTool())
    
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
