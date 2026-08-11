import os
from dotenv import load_dotenv
from tools import ToolRegistry, BashTool, WebSearchTool, WriteFileTool
from engine import run_agent_loop

def main():
    print("=======================================")
    print("  🧠 欢迎来到短期记忆与上下文压缩测试 🧠")
    print("=======================================")
    print("本节我们为 Agent 配备了 Bash 和联网搜索工具。")
    print("为了触发记忆压缩，你可以让它做一些大量耗费输出的操作，例如：")
    print(" 1. 请帮我搜索 'DeepSeek R1' 的资料，并使用 bash 执行 `dir C:\\Windows` 查看系统目录，多重复几次。")
    
    # 1. 加载环境变量
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            load_dotenv(stream=f)
            
    # 2. 注册工具
    registry = ToolRegistry()
    registry.register(WebSearchTool())
    registry.register(BashTool())
    registry.register(WriteFileTool())
    
    # 3. 开启循环
    while True:
        try:
            user_msg = input("\n请输入你的问题 (输入 q 退出): ")
            if user_msg.lower() == 'q':
                break
            if not user_msg.strip():
                continue
                
            run_agent_loop(user_msg, registry)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n[发生错误]: {e}")

if __name__ == "__main__":
    main()
