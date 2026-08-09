#!/usr/bin/env python3
"""
s02_code_annotated.py - Tool Use (中文注释版)

这一节的核心思想是：
不要把工具的调用写死在 Agent 循环里，而是使用一个映射表（TOOL_HANDLERS）。
这样以后无论加多少个工具，Agent 的核心循环都不需要做任何修改。
"""

import os, subprocess
from pathlib import Path

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
WORKDIR = Path.cwd()

# 告诉大模型，你要用工具来解决问题
SYSTEM = f"You are a coding agent at {WORKDIR}. Use tools to solve tasks. Act, don't explain."


# ═══════════════════════════════════════════════════════════
#  1. 工具的实际执行逻辑 (Implementation)
# ═══════════════════════════════════════════════════════════

def run_bash(command: str) -> str:
    """运行 Bash 命令 (s01 原有的)"""
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(command, shell=True, cwd=WORKDIR,
                           capture_output=True, timeout=120)
        stdout = r.stdout.decode('utf-8', errors='replace') if r.stdout else ""
        stderr = r.stderr.decode('utf-8', errors='replace') if r.stderr else ""
        out = (stdout + stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"
    except (FileNotFoundError, OSError) as e:
        return f"Error: {e}"

def safe_path(p: str) -> Path:
    """【新增】安全检查：确保要操作的文件没有逃出当前工作区"""
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path

def run_read(path: str, limit: int | None = None) -> str:
    """【新增】读取文件工具"""
    try:
        lines = safe_path(path).read_text(encoding="utf-8").splitlines()
        # 如果模型只想看前几行，做一下截断
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"

def run_write(path: str, content: str) -> str:
    """【新增】写入文件工具"""
    try:
        file_path = safe_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True) # 自动创建不存在的目录
        file_path.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"

def run_edit(path: str, old_text: str, new_text: str) -> str:
    """【新增】编辑文件工具 (基于精准的字符串替换)"""
    try:
        file_path = safe_path(path)
        text = file_path.read_text(encoding="utf-8")
        if old_text not in text:
            return f"Error: text not found in {path}"
        # 只替换第一次匹配到的，防止误伤
        file_path.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"

def run_glob(pattern: str) -> str:
    """【新增】查找文件工具"""
    import glob as g
    try:
        results = []
        for match in g.glob(pattern, root_dir=WORKDIR):
            if (WORKDIR / match).resolve().is_relative_to(WORKDIR):
                results.append(match)
        return "\n".join(results) if results else "(no matches)"
    except Exception as e:
        return f"Error: {e}"


# ═══════════════════════════════════════════════════════════
#  2. 工具箱定义 (向大模型宣告)
# ═══════════════════════════════════════════════════════════

TOOLS = [
    {"name": "bash", "description": "Run a shell command.",
     "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to a file.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace exact text in a file once.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
    {"name": "glob", "description": "Find files matching a glob pattern.",
     "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}},
]


# ═══════════════════════════════════════════════════════════
#  3. 工具分发映射表 (Dispatch Map)
# ═══════════════════════════════════════════════════════════

# 这个字典把大模型生成的 "工具名称" 和对应的 "Python 函数" 绑定了起来
TOOL_HANDLERS = {
    "bash": run_bash, 
    "read_file": run_read, 
    "write_file": run_write,
    "edit_file": run_edit, 
    "glob": run_glob,
}


# ═══════════════════════════════════════════════════════════
#  4. 核心 Agent Loop
# ═══════════════════════════════════════════════════════════

def agent_loop(messages: list):
    while True:
        # 将消息转换为 OpenAI 格式
        formatted_messages = [{"role": "system", "content": SYSTEM}] + messages
        
        response = client.chat.completions.create(
            model=MODEL, messages=formatted_messages,
            tools=[{"type": "function", "function": t} for t in TOOLS],
            max_tokens=8000,
        )
        
        response_message = response.choices[0].message
        
        messages.append({"role": "assistant", "content": response_message.content if response_message.content else "", "tool_calls": [t.model_dump() for t in response_message.tool_calls] if response_message.tool_calls else None})

        if response.choices[0].finish_reason != "tool_calls":
            return

        results = []
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                import json
                try:
                    args = json.loads(tool_call.function.arguments)
                except:
                    args = {}
                    
                print(f"\033[33m> 准备使用工具: {tool_call.function.name}\033[0m")
                
                # 【核心改造点】查表分发，不再硬编码 if-else
                handler = TOOL_HANDLERS.get(tool_call.function.name)
                if handler:
                    output = handler(**args) 
                else:
                    output = f"Unknown tool: {tool_call.function.name}"
                    
                print(str(output)[:200])
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": output,
                })


if __name__ == "__main__":
    print("s02: Tool Use (中文注释版) — 在 s01 基础上加了 4 个原生工具")
    print("输入问题，回车发送。输入 q 退出。\n")

    history = []
    while True:
        try:
            query = input("\033[36ms02 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        response_content = history[-1]["content"]
        if isinstance(response_content, str):
            print(response_content)
        elif isinstance(response_content, list):
            for block in response_content:
                if isinstance(block, dict) and block.get("type") == "text":
                    print(block["text"])
                elif hasattr(block, "type") and block.type == "text":
                    print(block.text)
                elif isinstance(block, str):
                    print(block)
        print()
