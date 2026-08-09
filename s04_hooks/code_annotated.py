#!/usr/bin/env python3
"""
s04_code_annotated.py - Hook System (中文注释版)

核心思想：把所有额外逻辑（如权限检查、日志、通知等）从 agent_loop 循环里抽离出来。
把它们变成独立的函数，挂载（注册）到四个关键生命周期的 Hook（钩子）上。
保持核心循环的绝对干净。
"""

import os, subprocess
from pathlib import Path
import json

try:
    import readline
except ImportError:
    pass

from dotenv import load_dotenv

load_dotenv(override=True)

if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

import openai
client = openai.OpenAI(
    base_url=os.getenv("ANTHROPIC_BASE_URL") + "/v1" if not os.getenv("ANTHROPIC_BASE_URL").endswith("/v1") else os.getenv("ANTHROPIC_BASE_URL"),
    api_key=os.getenv("ANTHROPIC_API_KEY")
)
MODEL = os.environ["MODEL_ID"]
WORKDIR = Path.cwd()

SYSTEM = f"You are a coding agent at {WORKDIR}. Use tools to solve tasks. Act, don't explain."

# ═══════════════════════════════════════════════════════════
#  FROM s02 (不变): 工具实现与分发
# ═══════════════════════════════════════════════════════════

def run_bash(command: str) -> str:
    try:
        # 在 Windows 上执行命令，如果遇到编码问题，统一使用 utf-8 并忽略错误
        r = subprocess.run(command, shell=True, cwd=WORKDIR,
                           capture_output=True, timeout=120)
        
        # 安全地解码，防止 gbk 报错
        stdout = r.stdout.decode('utf-8', errors='replace') if r.stdout else ""
        stderr = r.stderr.decode('utf-8', errors='replace') if r.stderr else ""
        
        out = (stdout + stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"

def run_read(path: str, limit: int | None = None) -> str:
    try:
        file_path = (WORKDIR / path).resolve()
        lines = file_path.read_text().splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"

def run_write(path: str, content: str) -> str:
    try:
        file_path = (WORKDIR / path).resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"

def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        file_path = (WORKDIR / path).resolve()
        text = file_path.read_text()
        if old_text not in text:
            return f"Error: text not found in {path}"
        file_path.write_text(text.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"

def run_glob(pattern: str) -> str:
    import glob as g
    try:
        results = []
        for match in g.glob(pattern, root_dir=WORKDIR):
            if (WORKDIR / match).resolve().is_relative_to(WORKDIR):
                results.append(match)
        return "\n".join(results) if results else "(no matches)"
    except Exception as e:
        return f"Error: {e}"

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

TOOL_HANDLERS = {
    "bash": run_bash, "read_file": run_read, "write_file": run_write,
    "edit_file": run_edit, "glob": run_glob,
}

# ═══════════════════════════════════════════════════════════
#  NEW in s04: Hook System (钩子系统)
# ═══════════════════════════════════════════════════════════

# 注册表：存放四个生命周期的所有钩子函数
HOOKS = {"UserPromptSubmit": [], "PreToolUse": [], "PostToolUse": [], "Stop": []}

def register_hook(event: str, callback):
    """把自定义的函数挂载到指定的生命周期事件上"""
    HOOKS[event].append(callback)

def trigger_hooks(event: str, *args):
    """循环执行注册在某个生命周期上的所有函数"""
    for callback in HOOKS[event]:
        result = callback(*args)
        # 如果钩子函数返回了非 None 的值，说明它想打断当前流程（比如权限被拒绝了）
        if result is not None:  
            return result
    return None

# -----------------------------------------------------------
# 开始编写具体的钩子逻辑（脱离了主循环）
# -----------------------------------------------------------

DENY_LIST = ["rm -rf /", "sudo", "shutdown", "reboot", "mkfs", "dd if="]
DESTRUCTIVE = ["rm ", "> /etc/", "chmod 777"]

def permission_hook(tool_name: str, args: dict):
    """【执行前 Hook】s03 的权限安检逻辑，现在搬到这里来了"""
    if tool_name == "bash":
        for pattern in DENY_LIST:
            if pattern in args.get("command", ""):
                print(f"\n\033[31m⛔ Blocked: '{pattern}'\033[0m")
                return "Permission denied by deny list"
        for kw in DESTRUCTIVE:
            if kw in args.get("command", ""):
                print(f"\n\033[33m⚠  Potentially destructive command\033[0m")
                print(f"   Tool: {tool_name}({args})")
                choice = input("   Allow? [y/N] ").strip().lower()
                if choice not in ("y", "yes"):
                    return "Permission denied by user"
                    
    if tool_name in ("read_file", "write_file", "edit_file"):
        path = args.get("path", "")
        if not (WORKDIR / path).resolve().is_relative_to(WORKDIR):
            print(f"\n\033[33m⚠  Access outside workspace\033[0m")
            print(f"   Tool: {tool_name}({args})")
            choice = input("   Allow? [y/N] ").strip().lower()
            if choice not in ("y", "yes"):
                return "Permission denied by user"
    return None

def log_hook(tool_name: str, args: dict):
    """【执行前 Hook】在每次工具调用前打印一条日志"""
    args_preview = str(list(args.values())[:2])[:60]
    print(f"\033[90m[HOOK] {tool_name}({args_preview})\033[0m")
    return None

def large_output_hook(tool_name: str, args: dict, output: str):
    """【执行后 Hook】如果工具输出结果超过10万字，发出警告"""
    if len(str(output)) > 100000:
        print(f"\033[33m[HOOK] ⚠ Large output from {tool_name}: {len(str(output))} chars\033[0m")
    return None

def context_inject_hook(query: str):
    """【提交输入时 Hook】在用户发消息前打印当前工作目录"""
    print(f"\033[90m[HOOK] UserPromptSubmit: working in {WORKDIR}\033[0m")
    return None

def summary_hook(messages: list):
    """【退出前 Hook】统计本次对话大模型一共调用了多少次工具"""
    tool_count = sum(1 for m in messages if m.get("role") == "tool")
    print(f"\033[90m[HOOK] Stop: session used {tool_count} tool calls\033[0m")
    return None

# 把写好的逻辑挂载到对应的生命周期上
register_hook("UserPromptSubmit", context_inject_hook)
register_hook("PreToolUse", permission_hook)  # 权限检查排在前面
register_hook("PreToolUse", log_hook)         # 检查过了再打印日志
register_hook("PostToolUse", large_output_hook)
register_hook("Stop", summary_hook)


# ═══════════════════════════════════════════════════════════
#  agent_loop — 循环里不再写死业务逻辑，只负责触发 Hook
# ═══════════════════════════════════════════════════════════

def agent_loop(messages: list):
    while True:
        formatted_messages = [{"role": "system", "content": SYSTEM}] + messages
        
        response = client.chat.completions.create(
            model=MODEL, messages=formatted_messages,
            tools=[{"type": "function", "function": t} for t in TOOLS],
            max_tokens=8000,
        )
        
        response_message = response.choices[0].message
        messages.append({"role": "assistant", "content": response_message.content if response_message.content else "", "tool_calls": [t.model_dump() for t in response_message.tool_calls] if response_message.tool_calls else None})

        if response.choices[0].finish_reason != "tool_calls":
            # 【退出前触发 Stop 钩子】
            force = trigger_hooks("Stop", messages)
            if force:
                # 钩子说还不能退，强行往聊天记录塞一段话让模型继续跑
                messages.append({"role": "user", "content": force})
                continue
            return

        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                try:
                    args = json.loads(tool_call.function.arguments)
                except:
                    args = {}

                # 【执行前触发 PreToolUse 钩子】(包含了权限检查和日志)
                blocked = trigger_hooks("PreToolUse", tool_call.function.name, args)
                if blocked:
                    # 某个钩子（比如权限钩子）打断了流程
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.function.name,
                        "content": str(blocked)
                    })
                    continue

                # 正常执行
                handler = TOOL_HANDLERS.get(tool_call.function.name)
                output = handler(**args) if handler else f"Unknown: {tool_call.function.name}"
                
                # 【执行后触发 PostToolUse 钩子】(包含了输出超长警告)
                trigger_hooks("PostToolUse", tool_call.function.name, args, output) 

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": output,
                })


if __name__ == "__main__":
    print("s04: Hooks (中文注释版) — 扩展逻辑挂在钩子上，循环保持纯净")
    print("输入问题，回车发送。输入 q 退出。\n")

    history = []
    while True:
        try:
            query = input("\033[36ms04 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
            
        # 【输入前触发 UserPromptSubmit 钩子】
        trigger_hooks("UserPromptSubmit", query)
        
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
