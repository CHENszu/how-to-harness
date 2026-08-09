#!/usr/bin/env python3
"""
s10_code_annotated.py - System Prompt 运行时组装 (中文注释版)

核心思想：
不要用写死的一长串字符串作为 SYSTEM PROMPT。
把 Prompt 拆分成多个独立的小模块（Section），比如：身份设定、工具列表、记忆区。
在运行时，通过检测真实的环境状态（Context），动态把需要的模块拼装起来。
并且利用简单的本地缓存，在状态未变时避免重复拼装。
"""

import os, subprocess, json
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

# 为了演示按需加载，保留记忆目录的定义
MEMORY_DIR = WORKDIR / ".memory"
MEMORY_INDEX = MEMORY_DIR / "MEMORY.md"


# ═══════════════════════════════════════════════════════════
#  NEW in s10: Prompt 模块化定义与拼装
# ═══════════════════════════════════════════════════════════

# 将大段的 Prompt 拆解成不同主题的字典
PROMPT_SECTIONS = {
    "identity": "You are a coding agent. Act, don't explain. Solve tasks directly.",
}

def assemble_system_prompt(context: dict) -> str:
    """根据当前的真实状态 (Context)，动态选择并拼装 Prompt 模块"""
    sections = []

    # 1. 始终加载的部分：身份与核心行为原则
    sections.append(PROMPT_SECTIONS["identity"])

    # 2. 动态加载的部分：根据传入的上下文动态渲染工具列表
    tools = ", ".join(context.get("enabled_tools", []))
    if tools:
        sections.append(f"Available tools: {tools}.")
    
    sections.append(f"Working directory: {context.get('workspace', WORKDIR)}")

    # 3. 按需加载的部分：只有当记忆内容真正存在时，才加入记忆段落
    memories = context.get("memories", "")
    if memories:
        sections.append(f"Relevant memories:\n{memories}")

    return "\n\n".join(sections)


# 用于缓存上一次拼装结果的全局变量
_last_context_key = None
_last_prompt = None

def get_system_prompt(context: dict) -> str:
    """
    带缓存的 Prompt 获取器。
    将 context 序列化成 JSON 字符串作为 Key，如果环境没变，直接返回上次拼好的结果。
    """
    global _last_context_key, _last_prompt
    # 使用 json.dumps 保证稳定序列化（字典排序），不用 hash() 是因为 hash 每次进程重启可能不同
    key = json.dumps(context, sort_keys=True, ensure_ascii=False, default=str)
    
    if key == _last_context_key and _last_prompt:
        print("  \033[90m[cache hit] system prompt unchanged (缓存命中，未重组)\033[0m")
        return _last_prompt
        
    _last_context_key = key
    _last_prompt = assemble_system_prompt(context)

    # 打印日志，展示本次拼装到底启用了哪些模块
    loaded = ["identity", "tools", "workspace"]
    if context.get("memories"):
        loaded.append("memory")
    print(f"  \033[32m[assembled] sections: {', '.join(loaded)}\033[0m")
    
    return _last_prompt


# ═══════════════════════════════════════════════════════════
#  FROM s02: 基础工具实现 (简化版，包含编码修复)
# ═══════════════════════════════════════════════════════════

def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path

def run_bash(command: str) -> str:
    try:
        r = subprocess.run(command, shell=True, cwd=WORKDIR, capture_output=True, timeout=120, text=True, errors='replace')
        out = ((r.stdout if r.stdout else "") + (r.stderr if r.stderr else "")).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired: return "Error: Timeout (120s)"

def run_read(path: str, limit: int | None = None) -> str:
    try:
        lines = safe_path(path).read_text(encoding="utf-8").splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)
    except Exception as e: return f"Error: {e}"

def run_write(path: str, content: str) -> str:
    try:
        file_path = safe_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e: return f"Error: {e}"

TOOLS = [
    {"type": "function", "function": {"name": "bash", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read file contents.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Write content to a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
]
TOOL_HANDLERS = {"bash": run_bash, "read_file": run_read, "write_file": run_write}


# ═══════════════════════════════════════════════════════════
#  NEW in s10: 环境上下文评估
# ═══════════════════════════════════════════════════════════

def update_context(context: dict, messages: list) -> dict:
    """
    侦测当前的真实运行状态，生成 Context。
    不是去搜用户说了什么关键词，而是看硬盘上到底有没有文件、系统里到底挂载了什么工具。
    """
    memories = ""
    if MEMORY_INDEX.exists():
        content = MEMORY_INDEX.read_text(encoding="utf-8").strip()
        if content:
            memories = content
            
    return {
        "enabled_tools": list(TOOL_HANDLERS.keys()),
        "workspace": str(WORKDIR),
        "memories": memories,
    }


# ═══════════════════════════════════════════════════════════
#  Agent Loop
# ═══════════════════════════════════════════════════════════

def agent_loop(messages: list, context: dict):
    """主循环：使用动态组装的 System Prompt 替代硬编码"""
    
    # 第一次拿 Prompt，会触发 [assembled]
    system = get_system_prompt(context)
    
    while True:
        # OpenAI 格式组装 messages
        formatted_messages = [{"role": "system", "content": system}] + messages
        
        response = client.chat.completions.create(
            model=MODEL, messages=formatted_messages,
            tools=TOOLS, max_tokens=8000
        )
        response_message = response.choices[0].message
        
        messages.append({
            "role": "assistant",
            "content": response_message.content or "",
            "tool_calls": [t.model_dump() for t in response_message.tool_calls] if response_message.tool_calls else None
        })
        
        if response.choices[0].finish_reason != "tool_calls":
            return

        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                print(f"\033[36m> {tool_call.function.name}\033[0m")
                args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                handler = TOOL_HANDLERS.get(tool_call.function.name)
                output = handler(**args) if handler else f"Unknown: {tool_call.function.name}"
                print(str(output)[:200])
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": output})

        # 每轮工具调用完后，重新评估环境状态（比如工具刚刚创建了记忆文件），并更新 System Prompt（命中缓存则跳过拼装）
        context = update_context(context, messages)
        system = get_system_prompt(context)


if __name__ == "__main__":
    print("s10: System Prompt — 运行时动态组装")
    print("输入问题，回车发送。输入 q 退出。\n")
    
    history = []
    # 初始化时的环境状态
    context = update_context({}, [])
    
    while True:
        try:
            query = input("\033[36ms10 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
            
        history.append({"role": "user", "content": query})
        
        # 传入历史记录和当前上下文
        agent_loop(history, context)
        
        # 更新状态（防止在循环外有些状态变更没被捕捉到）
        context = update_context(context, history)
        
        # 打印输出
        content = history[-1].get("content", "")
        if content:
            print(content)
        print()
