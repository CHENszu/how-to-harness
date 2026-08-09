#!/usr/bin/env python3
"""
s01_code_annotated.py - The Agent Loop (中文注释版)

这里包含了打造一个 AI 程序员 Agent 的最核心机密：
一个无限循环，直到模型觉得事情做完了才停止。

    while 模型说要用工具（stop_reason == "tool_use"）:
        response = LLM(messages, tools)  # 把聊天记录和工具箱给模型
        execute tools                    # 在本地替它执行工具
        append results                   # 把执行结果追加到聊天记录里

这 30 行代码就是 Harness（载具）的骨架。
"""

import os
import subprocess

try:
    import readline
except ImportError:
    pass

from anthropic import Anthropic
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量（如 API_KEY）
load_dotenv(override=True)

if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

# 对于兼容 OpenAI 格式的 API (如 DeepSeek)，我们需要使用 OpenAI 客户端
import openai
client = openai.OpenAI(
    base_url=os.getenv("ANTHROPIC_BASE_URL") + "/v1" if not os.getenv("ANTHROPIC_BASE_URL").endswith("/v1") else os.getenv("ANTHROPIC_BASE_URL"),
    api_key=os.getenv("ANTHROPIC_API_KEY")
)
MODEL = os.environ["MODEL_ID"]

# System Prompt（系统提示词）：告诉模型它的身份和能做的事
SYSTEM = f"You are a coding agent at {os.getcwd()}. Use bash to solve tasks. Act, don't explain."

# ── 1. 定义工具箱 (目前只有 bash 一个工具) ────────────────────────────
TOOLS = [{
        "name": "bash",
        "description": "Run a shell command.", # 运行 shell 命令
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    }]

# ── 2. 工具的实际执行逻辑 ────────────────────────────────────────
def run_bash(command: str) -> str:
    """接收模型生成的 bash 命令，在本地实际执行并返回结果"""
    # 简单拦截一些危险命令（这只是最初级的防护）
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    
    try:
        # 实际跑 subprocess
        r = subprocess.run(command, shell=True, cwd=os.getcwd(),
                           capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        # 截断太长的输出，防止撑爆模型的 Context
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"
    except (FileNotFoundError, OSError) as e:
        return f"Error: {e}"

# ── 3. 核心模式：Agent Loop ───────────────────────────────────
def agent_loop(messages: list):
    """
    接收历史消息，不断去问模型，只要模型想用工具，就帮它执行并喂回结果。
    直到模型觉得没必要用工具了，才退出循环。
    """
    while True:
        # 去问大模型，记得带上 TOOLS 工具箱
        # 将消息转换为 OpenAI 格式
        formatted_messages = [{"role": "system", "content": SYSTEM}] + messages
        
        response = client.chat.completions.create(
            model=MODEL, messages=formatted_messages,
            tools=[{"type": "function", "function": t} for t in TOOLS],
            max_tokens=8000,
        )

        response_message = response.choices[0].message
        
        # 无论模型回复什么，先把它的话追加到聊天记录里
        messages.append({"role": "assistant", "content": response_message.content if response_message.content else "", "tool_calls": [t.model_dump() for t in response_message.tool_calls] if response_message.tool_calls else None})

        # 【退出条件】：如果模型没有要求调用工具（比如它在跟你讲闲话，或者汇报工作完成了）
        if response.choices[0].finish_reason != "tool_calls":
            return # 退出循环，结束这一轮的思考

        # 【继续条件】：模型说要用工具，我们就拦截这个请求，替它执行
        results = []
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                import json
                try:
                    args = json.loads(tool_call.function.arguments)
                except:
                    args = {}
                # 打印出模型想执行的命令（黄色字体，方便我们观察）
                print(f"\033[33m$ {args.get('command', '')}\033[0m")
                
                # 在本地真正地去执行 bash 命令
                output = run_bash(args.get("command", ""))
                print(output[:200]) # 打印前 200 个字符
                
                # 把执行结果包装成规定的格式
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": output,
                })


# ── 4. 程序入口：终端交互界面 ───────────────────────────────────
if __name__ == "__main__":
    print("s01: Agent Loop (中文注释版)")
    print("输入问题，回车发送。输入 q 退出。\n")

    history = []
    while True:
        try:
            query = input("\033[36ms01 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        
        # 用户的输入就是最初始的 message
        history.append({"role": "user", "content": query})
        
        # 把聊天记录丢给 agent_loop 去无限循环跑
        agent_loop(history)
        
        # 循环结束（说明模型不再调用工具了），打印出它的最终回答
        response_content = history[-1]["content"]
        print(response_content)
        print()
