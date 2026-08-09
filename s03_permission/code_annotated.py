#!/usr/bin/env python3
"""
s03_code_annotated.py - Permission System (中文注释版)

核心思想：在工具执行之前，插入一个“权限判断流水线”（Permission Pipeline）。
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

SYSTEM = f"You are a coding agent at {WORKDIR}. All destructive operations require user approval."

# ═══════════════════════════════════════════════════════════
#  FROM s02 (不变): 工具实现与分发
# ═══════════════════════════════════════════════════════════

def run_bash(command: str) -> str:
    try:
        r = subprocess.run(command, shell=True, cwd=WORKDIR,
                           capture_output=True, timeout=120)
        stdout = r.stdout.decode('utf-8', errors='replace') if r.stdout else ""
        stderr = r.stderr.decode('utf-8', errors='replace') if r.stderr else ""
        out = (stdout + stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"

def run_read(path: str, limit: int | None = None) -> str:
    try:
        lines = safe_path(path).read_text(encoding="utf-8").splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"

def run_write(path: str, content: str) -> str:
    try:
        file_path = safe_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"

def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        file_path = safe_path(path)
        text = file_path.read_text(encoding="utf-8")
        if old_text not in text:
            return f"Error: text not found in {path}"
        file_path.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
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
#  NEW in s03: 三道权限安全闸门
# ═══════════════════════════════════════════════════════════

# 【闸门 1】硬拒绝列表：命中这些词，直接报错拦截
DENY_LIST = ["rm -rf /", "sudo", "shutdown", "reboot", "mkfs", "dd if=", "> /dev/sda"]

def check_deny_list(command: str) -> str | None:
    for pattern in DENY_LIST:
        if pattern in command:
            return f"Blocked: '{pattern}' is on the deny list"
    return None

# 【闸门 2】规则匹配列表：命中这些规则，需要去问人类
PERMISSION_RULES = [
    {
        "tools": ["read_file", "write_file", "edit_file"],
        # 检查：操作的文件路径是否跳出了当前工作区？
        "check": lambda args: not (WORKDIR / args.get("path", "")).resolve().is_relative_to(WORKDIR),
        "message": "警告：正在尝试读写工作区之外的文件！"
    },
    {
        "tools": ["bash"],
        # 检查：bash 命令里是不是包含危险操作，比如 rm、修改权限等
        "check": lambda args: any(kw in args.get("command", "") for kw in ["rm ", "> /etc/", "chmod 777"]),
        "message": "警告：正在执行具有破坏性的 bash 命令！"
    },
]

def check_rules(tool_name: str, args: dict) -> str | None:
    for rule in PERMISSION_RULES:
        if tool_name in rule["tools"] and rule["check"](args):
            return rule["message"] # 命中规则，返回警告信息
    return None

# 【闸门 3】用户审批：把选择权交给人类
def ask_user(tool_name: str, args: dict, reason: str) -> str:
    print(f"\n\033[33m⚠  {reason}\033[0m")
    print(f"   准备执行工具: {tool_name}({args})")
    choice = input("   是否允许执行? [y/N] ").strip().lower()
    return "allow" if choice in ("y", "yes") else "deny"

# 【组装流水线】：把三道闸门串起来
def check_permission(tool_name: str, args: dict) -> bool:
    # 1. 检查硬拒绝
    if tool_name == "bash":
        reason = check_deny_list(args.get("command", ""))
        if reason:
            print(f"\n\033[31m⛔ {reason}\033[0m")
            return False # 直接拦截

    # 2. 检查警告规则
    reason = check_rules(tool_name, args)
    if reason:
        # 3. 命中规则，询问人类
        decision = ask_user(tool_name, args, reason)
        if decision == "deny":
            return False # 人类拒绝了，拦截
            
    return True # 没有命中规则，或者人类同意了，放行！

# ═══════════════════════════════════════════════════════════
#  agent_loop (修改了循环体，加入了权限判断)
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

                print(f"\033[36m> 模型尝试调用工具: {tool_call.function.name}\033[0m")

                # 【核心改造点】在执行前，先过一遍安全流水线
                if not check_permission(tool_call.function.name, args):
                    # 权限被拒绝，把这个结果喂给模型，让它知道自己被拦截了
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.function.name,
                        "content": "Permission denied."
                    })
                    continue # 跳过下面的真实执行

                # 权限通过，正常查表分发执行
                handler = TOOL_HANDLERS.get(tool_call.function.name)
                output = handler(**args) if handler else f"Unknown: {tool_call.function.name}"
                print(str(output)[:200])
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": output,
                })


if __name__ == "__main__":
    print("s03: Permission (中文注释版) — 每次执行工具前先过安检")
    print("输入问题，回车发送。输入 q 退出。\n")

    history = []
    while True:
        try:
            query = input("\033[36ms03 >> \033[0m")
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
