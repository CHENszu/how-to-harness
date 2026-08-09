#!/usr/bin/env python3
"""
s06_code_annotated.py - Subagent (中文注释版)

核心思想：当主 Agent 觉得任务太复杂，或者需要进行大量的试错摸索时。
它可以调用 `task` 工具召唤一个小弟（Subagent）。
小弟拥有一个全新的、没有任何历史包袱的空白大脑（messages=[]），去专心完成这一个小任务。
完成之后，中间的试错记录全部丢弃，只把最终的文字结论汇报给老大。
"""

import ast, json, os, subprocess
from pathlib import Path

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
CURRENT_TODOS: list[dict] = []

# s06: 主 Agent 的系统提示词，鼓励它把复杂的子任务外包给小弟
SYSTEM = (
    f"You are a coding agent at {WORKDIR}. "
    "For complex sub-problems, use the task tool to spawn a subagent."
)

# s06: 子 Agent 的系统提示词。明确告诉它：做完就汇报，不准再往下派活了！
SUB_SYSTEM = (
    f"You are a coding agent at {WORKDIR}. "
    "Complete the task you were given, then return a concise summary. "
    "Do not delegate further."
)


# ═══════════════════════════════════════════════════════════
#  基础工具实现 (包含 UTF-8 修复)
# ═══════════════════════════════════════════════════════════

def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path

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

def _normalize_todos(todos):
    if isinstance(todos, str):
        try:
            todos = json.loads(todos)
        except json.JSONDecodeError:
            try:
                todos = ast.literal_eval(todos)
            except (SyntaxError, ValueError):
                return None, "Error: todos must be a list or JSON array string"
    if not isinstance(todos, list):
        return None, "Error: todos must be a list"
    for i, t in enumerate(todos):
        if not isinstance(t, dict):
            return None, f"Error: todos[{i}] must be an object"
        if "content" not in t or "status" not in t:
            return None, f"Error: todos[{i}] missing 'content' or 'status'"
        if t["status"] not in ("pending", "in_progress", "completed"):
            return None, f"Error: todos[{i}] has invalid status '{t['status']}'"
    return todos, None

def run_todo_write(todos: list) -> str:
    global CURRENT_TODOS
    todos, error = _normalize_todos(todos)
    if error: return error
    CURRENT_TODOS = todos
    lines = ["\n\033[33m## Current Tasks\033[0m"]
    for t in CURRENT_TODOS:
        icon = {"pending": " ", "in_progress": "\033[36m▸\033[0m", "completed": "\033[32m✓\033[0m"}[t["status"]]
        lines.append(f"  [{icon}] {t['content']}")
    print("\n".join(lines))
    return f"Updated {len(CURRENT_TODOS)} tasks"

# 主 Agent 的工具箱（包含了 todo_write）
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
    {"name": "todo_write", "description": "Create and manage a task list for your current coding session.",
     "parameters": {"type": "object", "properties": {"todos": {"type": "array", "items": {"type": "object", "properties": {"content": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}}, "required": ["content", "status"]}}}, "required": ["todos"]}},
]

TOOL_HANDLERS = {
    "bash": run_bash, "read_file": run_read, "write_file": run_write,
    "edit_file": run_edit, "glob": run_glob, "todo_write": run_todo_write,
}


# ═══════════════════════════════════════════════════════════
#  NEW in s06: 小弟（Subagent）的专属工具箱与逻辑
# ═══════════════════════════════════════════════════════════

# 小弟的工具箱里：没有 task 工具！防止无限套娃召唤孙子。也没有 todo_write，因为小任务不需要计划。
SUB_TOOLS = [
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

SUB_HANDLERS = {
    "bash": run_bash, "read_file": run_read, "write_file": run_write,
    "edit_file": run_edit, "glob": run_glob,
}

def extract_text(content) -> str:
    """提取大模型回复中的纯文本部分（丢弃调用工具的 JSON 代码块）"""
    if not isinstance(content, list):
        return str(content)
    return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")

def spawn_subagent(description: str) -> str:
    """召唤一个小弟去执行任务，执行完只返回一段总结文字"""
    print(f"\n\033[35m[小弟 (Subagent) 已召唤]\033[0m")
    
    # ！！！核心魔法！！！给小弟一个全新的、干净的上下文数组
    messages = [{"role": "user", "content": description}]  

    # 为了防止小弟发神经陷入死循环，最多允许它思考 30 轮
    for _ in range(30):  
        formatted_messages = [{"role": "system", "content": SUB_SYSTEM}] + messages
        response = client.chat.completions.create(
            model=MODEL, messages=formatted_messages,
            tools=[{"type": "function", "function": t} for t in SUB_TOOLS],
            max_tokens=8000,
        )
        
        response_message = response.choices[0].message
        messages.append({"role": "assistant", "content": response_message.content if response_message.content else "", "tool_calls": [t.model_dump() for t in response_message.tool_calls] if response_message.tool_calls else None})
        
        if response.choices[0].finish_reason != "tool_calls":
            break # 小弟说它干完了
            
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                try:
                    args = json.loads(tool_call.function.arguments)
                except:
                    args = {}

                # 注意：小弟干活，也要经过主流程的安全权限校验！
                blocked = trigger_hooks("PreToolUse", tool_call.function.name, args)
                if blocked:
                    messages.append({"role": "tool", "tool_call_id": tool_call.id,
                                     "name": tool_call.function.name, "content": str(blocked)})
                    continue
                    
                handler = SUB_HANDLERS.get(tool_call.function.name)
                output = handler(**args) if handler else f"Unknown: {tool_call.function.name}"
                trigger_hooks("PostToolUse", tool_call.function.name, args, output)
                
                # 打印灰色的日志，代表是小弟在干活
                print(f"  \033[90m[sub] {tool_call.function.name}: {str(output)[:100]}\033[0m")
                
                messages.append({"role": "tool", "tool_call_id": tool_call.id,
                                 "name": tool_call.function.name, "content": output})

    # 小弟干完活了，提取它最后一次说的总结文字
    result = extract_text(messages[-1]["content"])
    if not result:
        # 如果最后一条是工具结果，就倒着找它说的最后一句话
        for msg in reversed(messages):
            if msg["role"] == "assistant":
                result = extract_text(msg["content"])
                if result:
                    break
        if not result:
            result = "小弟工作了 30 轮还没搞定，被强行终止了。"
            
    print(f"\033[35m[小弟 (Subagent) 工作汇报完毕，已退场]\033[0m")
    
    # ！！！核心魔法！！！只把最后一段话返回给主 Agent。中间那几十条消息，全部随风飘散。
    return result  

# 把 task 工具注册到主 Agent 的工具箱里
TOOLS.append({
    "name": "task",
    "description": "Launch a subagent to handle a complex subtask. Returns only the final conclusion.",
    "parameters": {"type": "object", "properties": {"description": {"type": "string"}}, "required": ["description"]},
})
TOOL_HANDLERS["task"] = spawn_subagent


# ═══════════════════════════════════════════════════════════
#  FROM s04 (不变): Hook 系统
# ═══════════════════════════════════════════════════════════

HOOKS = {"UserPromptSubmit": [], "PreToolUse": [], "PostToolUse": [], "Stop": []}

def register_hook(event: str, callback):
    HOOKS[event].append(callback)

def trigger_hooks(event: str, *args):
    for callback in HOOKS[event]:
        result = callback(*args)
        if result is not None:
            return result
    return None

DENY_LIST = ["rm -rf /", "sudo", "shutdown", "reboot", "mkfs", "dd if="]

def permission_hook(tool_name, args):
    if tool_name == "bash":
        for p in DENY_LIST:
            if p in args.get("command", ""):
                print(f"\n\033[31m⛔ Blocked: '{p}'\033[0m")
                return "Permission denied"
    return None

def log_hook(tool_name, args):
    print(f"\033[90m[HOOK] {tool_name}\033[0m")
    return None

def context_inject_hook(query: str):
    print(f"\033[90m[HOOK] UserPromptSubmit: working in {WORKDIR}\033[0m")
    return None

def summary_hook(messages: list):
    tool_count = sum(1 for m in messages if m.get("role") == "tool")
    print(f"\033[90m[HOOK] Stop: session used {tool_count} tool calls\033[0m")
    return None

register_hook("UserPromptSubmit", context_inject_hook)
register_hook("PreToolUse", permission_hook)
register_hook("PreToolUse", log_hook)
register_hook("Stop", summary_hook)


# ═══════════════════════════════════════════════════════════
#  agent_loop — 跟 s05 一样
# ═══════════════════════════════════════════════════════════

def agent_loop(messages: list):
    rounds_since_todo = 0
    while True:
        if rounds_since_todo >= 3 and messages:
            messages.append({"role": "user",
                             "content": "<reminder>Update your todos.</reminder>"})
            rounds_since_todo = 0

        formatted_messages = [{"role": "system", "content": SYSTEM}] + messages
        response = client.chat.completions.create(
            model=MODEL, messages=formatted_messages,
            tools=[{"type": "function", "function": t} for t in TOOLS],
            max_tokens=8000,
        )
        
        response_message = response.choices[0].message
        messages.append({"role": "assistant", "content": response_message.content if response_message.content else "", "tool_calls": [t.model_dump() for t in response_message.tool_calls] if response_message.tool_calls else None})

        if response.choices[0].finish_reason != "tool_calls":
            force = trigger_hooks("Stop", messages)
            if force:
                messages.append({"role": "user", "content": force})
                continue
            return

        rounds_since_todo += 1
        
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                try:
                    args = json.loads(tool_call.function.arguments)
                except:
                    args = {}

                blocked = trigger_hooks("PreToolUse", tool_call.function.name, args)
                if blocked:
                    messages.append({"role": "tool", "tool_call_id": tool_call.id,
                                     "name": tool_call.function.name, "content": str(blocked)})
                    continue

                handler = TOOL_HANDLERS.get(tool_call.function.name)
                output = handler(**args) if handler else f"Unknown: {tool_call.function.name}"

                trigger_hooks("PostToolUse", tool_call.function.name, args, output)

                if tool_call.function.name == "todo_write":
                    rounds_since_todo = 0

                messages.append({"role": "tool", "tool_call_id": tool_call.id,
                                 "name": tool_call.function.name, "content": output})


if __name__ == "__main__":
    print("s06: Subagent (中文注释版) — 召唤小弟干脏活，干完只听汇报")
    print("输入问题，回车发送。输入 q 退出。\n")

    history = []
    while True:
        try:
            query = input("\033[36ms06 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
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
