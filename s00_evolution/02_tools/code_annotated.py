import os
import json
import subprocess
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List
from openai import OpenAI
from dotenv import load_dotenv

# ==========================================
# 第2部分：Tools (工具抽象与注册机制)
# ==========================================

# 1. 基础工具抽象类 (BaseTool)
class BaseTool:
    name: str = ""
    description: str = ""
    input_model: Type[BaseModel] = None
    
    def to_api_schema(self) -> dict:
        """将 Pydantic 模型转换为供大模型识别的 JSON Schema"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema()
            }
        }
        
    def execute(self, **kwargs) -> str:
        """工具的具体执行逻辑，由子类实现"""
        raise NotImplementedError

# 2. 具体的终端调用工具 (BashTool)
class BashToolInput(BaseModel):
    command: str = Field(..., description="要执行的 shell 命令，Windows下请使用 cmd/powershell 兼容命令")
    
class BashTool(BaseTool):
    name = "bash"
    description = "在本地终端执行 Shell 命令并返回结果。注意：禁止执行阻塞性或交互式命令。"
    input_model = BashToolInput
    
    def execute(self, **kwargs) -> str:
        # Pydantic 强类型校验
        validated_args = self.input_model(**kwargs)
        cmd = validated_args.command
        print(f"  [BashTool] 正在底层终端执行命令: `{cmd}`")
        
        try:
            # 模拟 asyncio.create_subprocess_shell，这里用简单的 subprocess，Windows 下需指定 shell=True
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=10
            )
            # 有时错误信息会在 stderr，所以做个简单的合并
            output = result.stdout if result.stdout else result.stderr
            return output.strip() if output else "命令执行成功，无输出。"
        except subprocess.TimeoutExpired:
            return "错误：命令执行超时"
        except Exception as e:
            return f"执行出错: {str(e)}"

# 3. 工具注册中心 (ToolRegistry)
class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        
    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool
        
    def get_tool(self, name: str) -> BaseTool:
        return self._tools.get(name)
        
    def to_api_tools(self) -> List[dict]:
        """暴漏给大模型的所有工具说明书"""
        return [tool.to_api_schema() for tool in self._tools.values()]

# ==========================================
# 集成到 Agent Loop (使用真实模型)
# ==========================================
def agent_loop_with_registry(user_input: str):
    print(f"\n[用户]: {user_input}")
    
    # 1. 加载环境变量 (Windows下务必使用 utf-8 编码读取)
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            load_dotenv(stream=f)
    else:
        print(f"警告：未找到环境变量文件 {env_path}")
            
    # 2. 初始化客户端
    client = OpenAI(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.deepseek.com/v1")
    )
    model_name = os.getenv("MODEL_ID", "deepseek-chat")
    
    # 3. 注册工具
    registry = ToolRegistry()
    registry.register(BashTool())
    
    # 初始化上下文
    messages = [
        {"role": "system", "content": "你是一个有用的AI助手，你可以通过 bash 工具执行终端命令来帮助用户完成任务。"},
        {"role": "user", "content": user_input}
    ]

    # 获取动态的工具说明书
    tools = registry.to_api_tools()

    turn = 1
    while True:
        print(f"\n--- 🔄 第 {turn} 轮思考开始 ---")
        print("  [Agent] 正在思考...")
        
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=tools,
            temperature=0.0
        )
        
        message = response.choices[0].message
        messages.append(message) 

        # 如果模型决定调用工具
        if message.tool_calls:
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                args_str = tool_call.function.arguments
                
                print(f"  [Agent] 决定调用工具 🛠️: {func_name}({args_str})")
                
                # 从注册中心获取工具
                target_tool = registry.get_tool(func_name)
                
                if target_tool:
                    try:
                        args = json.loads(args_str)
                        # 执行工具
                        result = target_tool.execute(**args)
                    except Exception as e:
                        result = f"工具参数解析或执行失败: {e}"
                else:
                    result = f"找不到名为 {func_name} 的工具"
                    
                print(f"  [Agent] 观察到结果 👀: \n{result}")
                
                # 塞回工具执行结果
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": func_name,
                    "content": str(result)
                })
            
            turn += 1
            continue 
        else:
            print(f"\n[Agent 最终回复 🎯]: {message.content}")
            break

if __name__ == "__main__":
    print("=======================================")
    print("  🚀 欢迎来到 Tools 架构测试 🚀")
    print("=======================================")
    print("你可以尝试这样提问：")
    print(" 1. 当前目录下有哪些文件？")
    print(" 2. 用 python 帮我算一下 2的10次方")
    
    while True:
        try:
            user_msg = input("\n请输入你的问题 (输入 q 退出): ")
            if user_msg.lower() == 'q':
                print("再见！")
                break
            if not user_msg.strip():
                continue
                
            agent_loop_with_registry(user_msg)
            
        except KeyboardInterrupt:
            print("\n再见！")
            break
        except Exception as e:
            print(f"\n[发生错误]: {e}")
