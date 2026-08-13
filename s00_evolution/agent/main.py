import sys
import os
from dotenv import load_dotenv
from engine import AgentEngine

def print_welcome():
    print("=" * 50)
    print("🤖 欢迎来到 Mini Claude Code (Agent Harness)")
    print("=" * 50)
    print("支持的功能：")
    print("  - bash: 运行 PowerShell 指令")
    print("  - web_search: 网络搜索 (基于 DuckDuckGo)")
    print("  - web_fetch: 抓取网页文本")
    print("输入 'exit' 或 'quit' 退出。")
    print("-" * 50)

def main():
    # 加载当前目录下的 .env 文件
    load_dotenv()
    
    print_welcome()
    
    # 检查并要求输入 API Key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        api_key = input("🔑 未检测到 ANTHROPIC_API_KEY 环境变量。\n请输入您的 Anthropic API Key: ").strip()
        if not api_key:
            print("❌ 未提供 API Key，程序退出。")
            sys.exit(1)
        # 将用户输入的 key 放入环境变量，供引擎读取
        os.environ["ANTHROPIC_API_KEY"] = api_key
    
    # 初始化引擎
    engine = AgentEngine()
    
    while True:
        try:
            user_input = input("\n👤 You: ")
            if not user_input.strip():
                continue
                
            if user_input.lower() in ['exit', 'quit']:
                print("👋 再见！")
                break
                
            print("\n🤔 Agent 正在思考...")
            
            # 调用 Agent Loop
            response = engine.run(user_input)
            
            print(f"\n🤖 Agent:\n{response}")
            
        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"\n❌ 发生未捕获的错误: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
