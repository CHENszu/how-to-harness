import os
import json
from openai import OpenAI
from dotenv import load_dotenv

# ==========================================
# 第1部分：Agent Loop (智能体主循环引擎)
# ==========================================

# 1. 加载环境变量 (Windows下务必使用 utf-8 编码读取)
env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        load_dotenv(stream=f)
else:
    print(f"警告：未找到环境变量文件 {env_path}")

# 2. 初始化大模型客户端
# 这里默认使用与 OpenAI 接口兼容的 DeepSeek，你已经在 .env 里配置好了
client = OpenAI(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.deepseek.com/v1")
)
model_name = os.getenv("MODEL_ID", "deepseek-chat")

# 3. 准备一个供 Agent 调用的本地函数 (这其实就是第2部分 Tools 的雏形)
def get_weather(location: str) -> str:
    """获取指定城市的天气"""
    print(f"  [系统日志] 正在执行本地函数 get_weather('{location}')...")
    # 模拟真实 API 调用
    weather_db = {
        "北京": "晴天, 25度",
        "上海": "下雨, 20度",
        "深圳": "多云, 28度",
        "广州": "雷阵雨, 30度"
    }
    return weather_db.get(location, f"抱歉，没有找到 {location} 的天气信息。")


# 4. Agent Loop 核心引擎 (The Engine)
def agent_loop(user_input: str):
    print(f"\n[用户]: {user_input}")
    
    # 初始化对话上下文 (Context)
    messages = [
        {"role": "system", "content": "你是一个有用的AI助手。如果用户问天气，请务必使用 get_weather 工具查询。在最终回复前，你可以多次调用工具。"},
        {"role": "user", "content": user_input}
    ]

    # 定义给模型看的工具说明 (OpenAI 函数调用格式)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "获取指定城市的天气情况",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "城市名称，例如：北京"}
                    },
                    "required": ["location"]
                }
            }
        }
    ]

    # === 核心：进入死循环 (Thought -> Action -> Observation) ===
    turn = 1
    while True:
        print(f"\n--- 🔄 第 {turn} 轮思考开始 ---")
        
        # 步骤 A：思考 (Thought) - 把上下文发给大模型
        print("  [Agent] 正在思考...")
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=tools,
            temperature=0.0 # Agent 任务通常把温度设为 0，以保证稳定的推理
        )
        
        message = response.choices[0].message
        
        # 将大模型的回复（可能包含文本，也可能包含工具调用指令）加入记忆
        # 这是必须的，否则大模型会“失忆”
        messages.append(message) 

        # 步骤 B：行动 (Action) - 判断模型是否要求调用工具
        if message.tool_calls:
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                
                print(f"  [Agent] 决定调用工具 🛠️: {func_name}({args})")
                
                # 执行真正的本地代码
                if func_name == "get_weather":
                    result = get_weather(args.get("location", ""))
                else:
                    result = "工具不存在"
                    
                print(f"  [Agent] 观察到结果 👀: {result}")
                
                # 步骤 C：观察 (Observation) - 把工具执行结果塞回上下文
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": func_name,
                    "content": str(result)
                })
            
            # 工具执行完毕，轮数+1，继续下一轮 while 循环！
            # 大模型将在下一轮中“看到”刚才塞入的工具执行结果，并据此继续思考。
            turn += 1
            continue 
            
        # 步骤 D：退出条件 - 模型没有调用工具，直接回复了纯文本
        else:
            print(f"\n[Agent 最终回复 🎯]: {message.content}")
            break # 任务完成，打破死循环！


if __name__ == "__main__":
    print("=======================================")
    print("  🚀 欢迎来到 Agent Loop 最小原型 🚀")
    print("=======================================")
    print("你可以尝试这样提问：")
    print(" 1. 北京的天气怎么样？")
    print(" 2. 上海和深圳的天气分别如何？ (测试模型一次调用多个工具/循环多轮)")
    print(" 3. 1+1等于几？ (测试模型不调用工具，直接退出循环)")
    
    while True:
        try:
            user_msg = input("\n请输入你的问题 (输入 q 退出): ")
            if user_msg.lower() == 'q':
                print("再见！")
                break
            if not user_msg.strip():
                continue
                
            agent_loop(user_msg)
            
        except KeyboardInterrupt:
            print("\n再见！")
            break
        except Exception as e:
            print(f"\n[发生错误]: {e}")
