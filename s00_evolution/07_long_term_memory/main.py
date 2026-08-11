import os
from dotenv import load_dotenv
from tools import ToolRegistry, BashTool, WebSearchTool, SaveMemoryTool, WriteFileTool
from engine import run_agent_loop

def main():
    print("=======================================")
    print("  🧠 欢迎来到长期记忆与启发式检索测试 🧠")
    print("=======================================")
    print("本节我们为 Agent 配备了 save_memory 工具，以及一个本地隐藏的 .memory 文件夹。")
    print("你可以尝试：")
    print(" 1. 先告诉它：'记住：以后在写 Python 代码时，必须加上中文注释，这对我非常重要！'")
    print(" 2. 按 'q' 退出程序（这会清空短期记忆）。")
    print(" 3. 重新运行程序，问它：'给我写一个冒泡排序。'")
    print(" 4. 观察它是否能自动检索到之前的长期记忆偏好！")
    
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
