#!/usr/bin/env python3
"""
s08_code_annotated.py - Context Compact (中文注释版)

核心思想：当大模型干活越来越多，对话历史（messages）越来越长，必然会把 API 的上下文窗口撑爆。
我们在每次请求大模型之前，插入一个“四层清洗流水线”：
L1 (snip_compact): 掐头去尾，把中间很久以前聊的废话删掉。
L2 (micro_compact): 把很久以前调用工具产生的长文本（比如读过的旧文件）替换成一句话占位符。
L3 (tool_result_budget): 如果刚刚执行的命令输出太大（比如 cat 了一个 20MB 的文件），直接拦截存到本地硬盘，只给大模型看前 2000 个字的预览。
L4 (compact_history): 如果上面 3 招用完还是太长，就花钱调一次 API，让大模型把前面的对话总结成一段摘要，然后清空历史。

原则：便宜的处理先跑，花钱/破坏性的处理后跑。
"""

import ast, json, os, subprocess, time
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

# s08 新增：用来存放长文本的本地目录
TRANSCRIPT_DIR = WORKDIR / ".transcripts"
TOOL_RESULTS_DIR = WORKDIR / ".task_outputs" / "tool-results"

CURRENT_TODOS: list[dict] = []

# ═══════════════════════════════════════════════════════════
#  FROM s07: 技能系统 (保持不变)
# ═══════════════════════════════════════════════════════════
SKILLS_DIR = WORKDIR / "skills"
SKILL_REGISTRY: dict[str, dict] = {}

def _scan_skills():
    if not SKILLS_DIR.exists(): return
    import yaml
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir(): continue
        manifest = d / "SKILL.md"
        if manifest.exists():
            raw = manifest.read_text(encoding="utf-8")
            parts = raw.split("---", 2)
            meta = yaml.safe_load(parts[1]) if len(parts) >= 3 else {}
            name = meta.get("name", d.name)
            desc = meta.get("description", raw.split("\n")[0].lstrip("#").strip())
            SKILL_REGISTRY[name] = {"name": name, "description": desc, "content": raw}
_scan_skills()

def build_system() -> str:
    catalog = "\n".join(f"- **{s['name']}**: {s['description']}" for s in SKILL_REGISTRY.values()) if SKILL_REGISTRY else "(no skills found)"
    return f"You are a coding agent at {WORKDIR}. Skills available:\n{catalog}\nUse load_skill to get full details."

SYSTEM = build_system()
SUB_SYSTEM = f"You are a coding agent at {WORKDIR}. Complete the task, return a summary. Do not delegate further."


# ═══════════════════════════════════════════════════════════
#  FROM s02-s07: 工具实现 (包含 UTF-8 修复)
# ═══════════════════════════════════════════════════════════
def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR): raise ValueError(f"Path escapes workspace: {p}")
    return path

def run_bash(command: str) -> str:
    try:
        r = subprocess.run(command, shell=True, cwd=WORKDIR, capture_output=True, timeout=120)
        out = ((r.stdout.decode('utf-8','replace') if r.stdout else "") + (r.stderr.decode('utf-8','replace') if r.stderr else "")).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired: return "Error: Timeout (120s)"

def run_read(path: str, limit: int | None = None) -> str:
    try:
        lines = safe_path(path).read_text(encoding="utf-8").splitlines()
        if limit and limit < len(lines): lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)
    except Exception as e: return f"Error: {e}"

def run_write(path: str, content: str) -> str:
    try:
        file_path = safe_path(path); file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8"); return f"Wrote {len(content)} bytes"
    except Exception as e: return f"Error: {e}"

def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        file_path = safe_path(path)
        text = file_path.read_text(encoding="utf-8")
        if old_text not in text: return f"Error: text not found"
        file_path.write_text(text.replace(old_text, new_text, 1), encoding="utf-8"); return f"Edited {path}"
    except Exception as e: return f"Error: {e}"

def run_glob(pattern: str) -> str:
    import glob as g
    try:
        results = [m for m in g.glob(pattern, root_dir=WORKDIR) if (WORKDIR / m).resolve().is_relative_to(WORKDIR)]
        return "\n".join(results) if results else "(no matches)"
    except Exception as e: return f"Error: {e}"

def run_todo_write(todos: list) -> str:
    global CURRENT_TODOS
    if isinstance(todos, str): todos = json.loads(todos)
    CURRENT_TODOS = todos
    lines = ["\n\033[33m## Current Tasks\033[0m"]
    for t in CURRENT_TODOS:
        icon = {"pending": " ", "in_progress": "\033[36m▸\033[0m", "completed": "\033[32m✓\033[0m"}.get(t.get("status","pending"), "?")
        lines.append(f"  [{icon}] {t.get('content','')}")
    print("\n".join(lines))
    return f"Updated {len(CURRENT_TODOS)} tasks"

def extract_text(content) -> str:
    if not isinstance(content, list): return str(content)
    return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")

def spawn_subagent(description: str) -> str:
    print(f"\n\033[35m[小弟 (Subagent) 已召唤]\033[0m")
    messages = [{"role": "user", "content": description}]
    for _ in range(30):
        formatted_messages = [{"role": "system", "content": SUB_SYSTEM}] + messages
        response = client.chat.completions.create(model=MODEL, messages=formatted_messages,
            tools=[{"type": "function", "function": t} for t in SUB_TOOLS], max_tokens=8000)
        response_message = response.choices[0].message
        messages.append({"role": "assistant", "content": response_message.content or "", "tool_calls": [t.model_dump() for t in response_message.tool_calls] if response_message.tool_calls else None})
        if response.choices[0].finish_reason != "tool_calls": break
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                handler = SUB_HANDLERS.get(tool_call.function.name)
                output = handler(**args) if handler else f"Unknown: {tool_call.function.name}"
                print(f"  \033[90m[sub] {tool_call.function.name}: {str(output)[:100]}\033[0m")
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": output})
    result = extract_text(messages[-1]["content"])
    print(f"\033[35m[小弟 (Subagent) 工作完毕]\033[0m")
    return result or "Subagent stopped without final answer."

def load_skill(name: str) -> str:
    return SKILL_REGISTRY.get(name, {}).get("content", f"Skill not found: {name}")


SUB_TOOLS = [
    {"name": "bash", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace exact text in a file once.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
    {"name": "glob", "description": "Find files matching a glob pattern.", "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}},
]
SUB_HANDLERS = {"bash": run_bash, "read_file": run_read, "write_file": run_write, "edit_file": run_edit, "glob": run_glob}

TOOLS = SUB_TOOLS + [
    {"name": "todo_write", "description": "Create and manage a task list.", "parameters": {"type": "object", "properties": {"todos": {"type": "array", "items": {"type": "object", "properties": {"content": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}}, "required": ["content", "status"]}}}, "required": ["todos"]}},
    {"name": "task", "description": "Launch a subagent.", "parameters": {"type": "object", "properties": {"description": {"type": "string"}}, "required": ["description"]}},
    {"name": "load_skill", "description": "Load skill content.", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    # s08 新增工具：模型可以主动要求进行对话压缩摘要
    {"name": "compact", "description": "Summarize earlier conversation to free context space.", "parameters": {"type": "object", "properties": {"focus": {"type": "string"}}}},
]
TOOL_HANDLERS = {"bash": run_bash, "read_file": run_read, "write_file": run_write, "edit_file": run_edit, "glob": run_glob, "todo_write": run_todo_write, "task": spawn_subagent, "load_skill": load_skill}


# ═══════════════════════════════════════════════════════════
#  NEW in s08: 四层压缩管线 (Four-Layer Compaction Pipeline)
# ═══════════════════════════════════════════════════════════

CONTEXT_LIMIT = 50000 # 当消息字符串总长度超过 5 万字符时触发 LLM 摘要
KEEP_RECENT = 3       # L2 压缩时，只保留最近 3 个工具调用的完整结果
PERSIST_THRESHOLD = 30000 # L3 压缩时，单个输出超过 3 万字符就写到硬盘

def estimate_size(msgs): 
    return len(str(msgs))

# --- L1: 掐头去尾 (裁掉中间老旧的聊天记录) ---
def snip_compact(messages, max_messages=50):
    if len(messages) <= max_messages: return messages
    keep_head, keep_tail = 3, max_messages - 3
    snipped = len(messages) - keep_head - keep_tail
    # 插入一个占位符告诉模型这里被删了
    return messages[:keep_head] + [{"role": "user", "content": f"[snipped {snipped} messages from conversation middle]"}] + messages[-keep_tail:]

# --- L2: 旧结果占位 (把很久以前的读文件、长输出给替换掉) ---
def collect_tool_results(messages):
    blocks = []
    for mi, msg in enumerate(messages):
        if msg.get("role") != "tool": continue
        blocks.append((mi, msg))
    return blocks

def micro_compact(messages):
    tool_results = collect_tool_results(messages)
    if len(tool_results) <= KEEP_RECENT: return messages
    for _, msg in tool_results[:-KEEP_RECENT]:
        if len(str(msg.get("content", ""))) > 120:
            msg["content"] = "[Earlier tool result compacted. Re-run if needed.]"
    return messages

# --- L3: 超大结果落盘 (防止一次读取把内存干爆) ---
def persist_large_output(tool_use_id, output):
    if len(output) <= PERSIST_THRESHOLD: return output
    TOOL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = TOOL_RESULTS_DIR / f"{tool_use_id}.txt"
    if not path.exists(): path.write_text(output, encoding="utf-8")
    # 只返回给模型一个路径和前 2000 个字的预览
    return f"<persisted-output>\nFull output saved to: {path}\nPreview:\n{output[:2000]}\n</persisted-output>"

def tool_result_budget(messages, max_bytes=200_000):
    # 如果最后一次对话是 tool 返回的，且特别大，就进行落盘
    last = messages[-1] if messages else None
    if not last or last.get("role") != "tool": return messages
    
    content = str(last.get("content", ""))
    if len(content) > max_bytes:
        last["content"] = persist_large_output(last.get("tool_call_id", "unknown"), content)
    return messages

# --- L4: LLM 全量摘要 (花钱调 API，清空记忆) ---
def write_transcript(messages):
    """备份当前完整对话，防止丢失"""
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    path = TRANSCRIPT_DIR / f"transcript_{int(time.time())}.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for msg in messages: f.write(json.dumps(msg, default=str) + "\n")
    return path

def summarize_history(messages):
    """调用大模型，生成前情提要"""
    conversation = json.dumps(messages, default=str)[:80000]
    prompt = ("Summarize this coding-agent conversation so work can continue.\n"
              "Preserve: 1. current goal, 2. key findings/decisions, 3. files read/changed, "
              "4. remaining work, 5. user constraints.\nBe compact but concrete.\n\n" + conversation)
    response = client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": prompt}], max_tokens=2000)
    return response.choices[0].message.content or "(empty summary)"

def compact_history(messages):
    transcript_path = write_transcript(messages)
    print(f"\n\033[33m[上下文过长，正在触发 LLM 全量压缩摘要... 备份: {transcript_path}]\033[0m")
    summary = summarize_history(messages)
    # 返回一条干干净净的总结消息，替换掉原来的几十条长篇大论
    return [{"role": "user", "content": f"[Compacted History 历史摘要]\n\n{summary}"}]


# ═══════════════════════════════════════════════════════════
#  agent_loop
# ═══════════════════════════════════════════════════════════

def agent_loop(messages: list):
    rounds_since_todo = 0
    while True:
        # ！！！ s08 核心：在发给大模型之前，先跑三层便宜的预处理清洗 ！！！
        messages[:] = tool_result_budget(messages)    # L3: 存大文件
        messages[:] = snip_compact(messages)          # L1: 裁中间
        messages[:] = micro_compact(messages)         # L2: 裁旧结果

        # ！！！ s08 核心：如果洗完还是超过 5万字，就花钱跑 L4 摘要清洗 ！！！
        if estimate_size(messages) > CONTEXT_LIMIT:
            messages[:] = compact_history(messages)

        if rounds_since_todo >= 3 and messages:
            messages.append({"role": "user", "content": "<reminder>Update your todos.</reminder>"})
            rounds_since_todo = 0

        formatted_messages = [{"role": "system", "content": SYSTEM}] + messages
        
        try:
            response = client.chat.completions.create(
                model=MODEL, messages=formatted_messages,
                tools=[{"type": "function", "function": t} for t in TOOLS],
                max_tokens=8000,
            )
        except Exception as e:
            # 终极应急手段：如果 API 还是报上下文太长，强行截断重试
            if "maximum context length" in str(e).lower() or "too many tokens" in str(e).lower():
                print("\033[31m[API 报错超长，触发应急强行压缩...]\033[0m")
                messages[:] = compact_history(messages)
                continue
            raise

        response_message = response.choices[0].message
        messages.append({"role": "assistant", "content": response_message.content or "", "tool_calls": [t.model_dump() for t in response_message.tool_calls] if response_message.tool_calls else None})

        if response.choices[0].finish_reason != "tool_calls":
            return

        rounds_since_todo += 1
        
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                # 模型主动调用 compact 工具
                if tool_call.function.name == "compact":
                    messages[:] = compact_history(messages)
                    messages.append({"role": "tool", "tool_call_id": tool_call.id, "name": "compact", "content": "[已完成压缩摘要]"})
                    break # 结束当前轮，拿着新摘要重新思考
                    
                try:
                    args = json.loads(tool_call.function.arguments)
                except:
                    args = {}

                handler = TOOL_HANDLERS.get(tool_call.function.name)
                output = handler(**args) if handler else f"Unknown: {tool_call.function.name}"

                if tool_call.function.name == "todo_write":
                    rounds_since_todo = 0

                messages.append({"role": "tool", "tool_call_id": tool_call.id, "name": tool_call.function.name, "content": output})


if __name__ == "__main__":
    print("s08: Context Compact (中文注释版) — 记忆清理术（四层压缩策略）")
    print("输入问题，回车发送。输入 q 退出。\n")

    history = []
    while True:
        try:
            query = input("\033[36ms08 >> \033[0m")
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
