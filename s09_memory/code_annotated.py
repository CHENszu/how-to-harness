#!/usr/bin/env python3
"""
s09_code_annotated.py - Memory System (中文注释版)

核心思想：给 Agent 添加长期记忆能力，跨越会话（Session）和压缩的限制。
我们不会把所有记忆都强塞给大模型（太贵），而是：
1. 【索引】：在 SYSTEM prompt 里面只放记忆的目录（MEMORY.md）。
2. 【按需加载】：每轮对话前，根据用户当前说的话，去目录里查一下有没有相关的详细记忆文件，有的话就动态塞进上下文。
3. 【自动提取】：每一轮对话结束时，在后台用另一个 prompt 偷偷扫描一下刚才的对话，看有没有什么值得记住的偏好/规则，有就写进硬盘。
4. 【做梦整理】：记忆文件多了以后，定期触发“做梦（Consolidate）”，把重复的合并，过时的删掉。
"""

import ast, json, os, subprocess, time, re
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

TRANSCRIPT_DIR = WORKDIR / ".transcripts"
TOOL_RESULTS_DIR = WORKDIR / ".task_outputs" / "tool-results"

# ═══════════════════════════════════════════════════════════
#  NEW in s09: 记忆系统核心组件 (Memory System)
# ═══════════════════════════════════════════════════════════

# 本地记忆目录，类似于大脑海马体
MEMORY_DIR = WORKDIR / ".memory"
MEMORY_DIR.mkdir(exist_ok=True)
# 记忆的索引文件（目录），会被放进 SYSTEM prompt
MEMORY_INDEX = MEMORY_DIR / "MEMORY.md"

def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """解析 Markdown 文件头的 YAML 元数据 (Frontmatter)"""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, parts[2].strip()

def write_memory_file(name: str, mem_type: str, description: str, body: str):
    """写入单个记忆文件（带 YAML 头部），并更新索引"""
    slug = name.lower().replace(" ", "-").replace("/", "-")
    filename = f"{slug}.md"
    filepath = MEMORY_DIR / filename
    filepath.write_text(
        f"---\nname: {name}\ndescription: {description}\ntype: {mem_type}\n---\n\n{body}\n",
        encoding="utf-8"
    )
    _rebuild_index()
    return filepath

def _rebuild_index():
    """重建 MEMORY.md 索引，一行一个记忆摘要"""
    lines = []
    for f in sorted(MEMORY_DIR.glob("*.md")):
        if f.name == "MEMORY.md":
            continue
        raw = f.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(raw)
        name = meta.get("name", f.stem)
        desc = meta.get("description", body.split("\n")[0][:80])
        lines.append(f"- [{name}]({f.name}) — {desc}")
    MEMORY_INDEX.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")

def read_memory_index() -> str:
    """读取记忆索引，准备注入 SYSTEM"""
    if not MEMORY_INDEX.exists():
        return ""
    text = MEMORY_INDEX.read_text(encoding="utf-8").strip()
    return text if text else ""

def list_memory_files() -> list[dict]:
    """列出所有具体的记忆文件和它们的元数据"""
    result = []
    for f in sorted(MEMORY_DIR.glob("*.md")):
        if f.name == "MEMORY.md":
            continue
        raw = f.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(raw)
        result.append({
            "filename": f.name,
            "name": meta.get("name", f.stem),
            "description": meta.get("description", ""),
            "type": meta.get("type", "user"),
            "body": body,
        })
    return result

def select_relevant_memories(messages: list, max_items: int = 5) -> list[str]:
    """
    [按需加载核心逻辑]：
    拿最近的对话和所有记忆的目录，去问一次大模型（Side-query）：
    '你看现在聊的，需要查阅哪些记忆？请返回记忆的序号。'
    """
    files = list_memory_files()
    if not files:
        return []

    # 提取最近的用户发言作为上下文
    recent_texts = []
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                recent_texts.append(content)
            if len(recent_texts) >= 3:
                break
    recent = " ".join(reversed(recent_texts))[:2000]
    if not recent.strip():
        return []

    # 构建带序号的记忆目录
    catalog_lines = []
    for i, f in enumerate(files):
        catalog_lines.append(f"{i}: {f['name']} — {f['description']}")
    catalog = "\n".join(catalog_lines)

    prompt = (
        "Given the recent conversation and the memory catalog below, "
        "select the indices of memories that are clearly relevant. "
        "Return ONLY a JSON array of integers, e.g. [0, 3]. "
        "If none are relevant, return [].\n\n"
        f"Recent conversation:\n{recent}\n\n"
        f"Memory catalog:\n{catalog}"
    )

    try:
        # 发起一次廉价的短查询，找出相关的记忆文件
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
        )
        text = response.choices[0].message.content or ""
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        if match:
            indices = json.loads(match.group())
            selected = []
            for idx in indices:
                if isinstance(idx, int) and 0 <= idx < len(files):
                    selected.append(files[idx]["filename"])
                    if len(selected) >= max_items:
                        break
            return selected
    except Exception:
        pass

    # 如果 API 调用失败，降级为简单的关键词匹配
    keywords = [w.lower() for w in recent.split() if len(w) > 3]
    selected = []
    for f in files:
        text = (f["name"] + " " + f["description"]).lower()
        if any(kw in text for kw in keywords):
            selected.append(f["filename"])
            if len(selected) >= max_items:
                break
    return selected

def load_memories(messages: list) -> str:
    """把被选中的记忆文件的完整内容加载出来，拼成一段文字"""
    selected_files = select_relevant_memories(messages)
    if not selected_files:
        return ""
    
    parts = ["<relevant_memories>"]
    for filename in selected_files:
        path = MEMORY_DIR / filename
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    parts.append("</relevant_memories>")
    return "\n\n".join(parts)

def extract_memories(messages: list):
    """
    [自动提取逻辑]：
    每一轮对话结束时，悄悄看一眼最近 10 条对话，看有没有什么值得记住的新知识或用户偏好。
    如果有，提取出来并存到本地 `.memory/` 下。
    """
    dialogue_parts = []
    for msg in messages[-10:]:
        role = msg.get("role", "?")
        content = msg.get("content", "")
        if isinstance(content, str) and content.strip():
            dialogue_parts.append(f"{role}: {content}")
    dialogue = "\n".join(dialogue_parts)
    if not dialogue.strip():
        return

    existing = list_memory_files()
    existing_desc = "\n".join(f"- {m['name']}: {m['description']}" for m in existing) if existing else "(none)"

    prompt = (
        "Extract user preferences, constraints, or project facts from this dialogue.\n"
        "Return a JSON array. Each item: {name, type, description, body}.\n"
        "- name: short kebab-case identifier (e.g. 'user-preference-tabs')\n"
        "- type: one of 'user' (user preference), 'feedback' (guidance), "
        "'project' (project fact), 'reference' (external pointer)\n"
        "- description: one-line summary for index lookup\n"
        "- body: full detail in markdown\n"
        "If nothing new or already covered by existing memories, return [].\n\n"
        f"Existing memories:\n{existing_desc}\n\n"
        f"Dialogue:\n{dialogue[:4000]}"
    )

    try:
        response = client.chat.completions.create(
            model=MODEL, messages=[{"role": "user", "content": prompt}], max_tokens=800
        )
        text = response.choices[0].message.content or ""
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if not match: return
        items = json.loads(match.group())
        if not items: return
        
        count = 0
        for mem in items:
            name = mem.get("name", f"memory_{int(time.time())}")
            mem_type = mem.get("type", "user")
            desc = mem.get("description", "")
            body = mem.get("body", "")
            if desc and body:
                write_memory_file(name, mem_type, desc, body)
                count += 1
        if count:
            print(f"\n\033[33m[Memory: 自动提取了 {count} 条新记忆]\033[0m")
    except Exception:
        pass

CONSOLIDATE_THRESHOLD = 10

def consolidate_memories():
    """
    [记忆整理逻辑（做梦）]：
    当记忆文件过多（比如超过 10 个），丢给大模型一次性整理：去重、合并、淘汰。
    """
    files = list_memory_files()
    if len(files) < CONSOLIDATE_THRESHOLD:
        return

    catalog = "\n\n".join(
        f"## {f['filename']}\nname: {f['name']}\ndescription: {f['description']}\n{f['body']}"
        for f in files
    )

    prompt = (
        "Consolidate the following memory files. Rules:\n"
        "1. Merge duplicates into one\n"
        "2. Remove outdated/contradicted memories\n"
        "3. Keep the total under 30 memories\n"
        "4. Preserve important user preferences above all\n"
        "Return a JSON array. Each item: {name, type, description, body}.\n\n"
        f"{catalog[:16000]}"
    )

    try:
        response = client.chat.completions.create(
            model=MODEL, messages=[{"role": "user", "content": prompt}], max_tokens=3000
        )
        text = response.choices[0].message.content or ""
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if not match: return
        items = json.loads(match.group())

        # 删除旧记忆（保留 MEMORY.md 索引）
        for f in MEMORY_DIR.glob("*.md"):
            if f.name != "MEMORY.md":
                f.unlink()

        for mem in items:
            name = mem.get("name", f"memory_{int(time.time())}")
            mem_type = mem.get("type", "user")
            desc = mem.get("description", "")
            body = mem.get("body", "")
            if desc and body:
                write_memory_file(name, mem_type, desc, body)

        print(f"\n\033[33m[Memory: 记忆大整理完成，{len(files)} 条 -> {len(items)} 条]\033[0m")
    except Exception:
        pass


# 构建 SYSTEM prompt，把记忆的“目录”拼进去
def build_system() -> str:
    index = read_memory_index()
    memories_section = f"\n\nMemories available:\n{index}" if index else ""
    return (
        f"You are a coding agent at {WORKDIR}."
        f"{memories_section}\n"
        "Relevant memories are injected below. Respect user preferences from memory.\n"
        "When the user says 'remember' or expresses a clear preference, extract it as a memory."
    )

SUB_SYSTEM = f"You are a coding agent at {WORKDIR}. Complete the task, return a summary. Do not delegate further."


# ═══════════════════════════════════════════════════════════
#  FROM s02-s08: 工具实现及压缩管线
# ═══════════════════════════════════════════════════════════
def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR): raise ValueError(f"Path escapes workspace: {p}")
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

TOOLS = [
    {"name": "bash", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace exact text in a file once.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
    {"name": "glob", "description": "Find files matching a glob pattern.", "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}},
]
TOOL_HANDLERS = {"bash": run_bash, "read_file": run_read, "write_file": run_write, "edit_file": run_edit, "glob": run_glob}

# -- 压缩流水线 (s08) --
CONTEXT_LIMIT = 50000; KEEP_RECENT = 3; PERSIST_THRESHOLD = 30000
def estimate_size(msgs): return len(str(msgs))

def snip_compact(messages, max_messages=50):
    if len(messages) <= max_messages: return messages
    keep_head, keep_tail = 3, max_messages - 3
    return messages[:keep_head] + [{"role": "user", "content": f"[snipped {len(messages) - keep_head - keep_tail} messages from middle]"}] + messages[-keep_tail:]

def micro_compact(messages):
    blocks = [(mi, msg) for mi, msg in enumerate(messages) if msg.get("role") == "tool"]
    if len(blocks) <= KEEP_RECENT: return messages
    for _, msg in blocks[:-KEEP_RECENT]:
        if len(str(msg.get("content", ""))) > 120:
            msg["content"] = "[Earlier tool result compacted. Re-run if needed.]"
    return messages

def persist_large(tid, out):
    if len(out) <= PERSIST_THRESHOLD: return out
    TOOL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    p = TOOL_RESULTS_DIR / f"{tid}.txt"
    if not p.exists(): p.write_text(out, encoding="utf-8")
    return f"<persisted-output>\nFull output saved to: {p}\nPreview:\n{out[:2000]}\n</persisted-output>"

def tool_result_budget(messages, max_budget=200_000):
    tool_msgs = [msg for msg in messages if msg.get("role") == "tool"]
    total = sum(len(str(m.get("content", ""))) for m in tool_msgs)
    if total <= max_budget: return messages
    for msg in sorted(tool_msgs, key=lambda m: len(str(m.get("content", ""))), reverse=True):
        if total <= max_budget: break
        c = str(msg.get("content", ""))
        if len(c) <= PERSIST_THRESHOLD: continue
        msg["content"] = persist_large(msg.get("tool_call_id", "unknown"), c)
        total = sum(len(str(m.get("content", ""))) for m in tool_msgs)
    return messages

def compact_history(messages):
    conv = json.dumps(messages, default=str)[:80000]
    r = client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content":
        "Summarize this coding-agent conversation so work can continue.\n"
        "Preserve: 1. current goal, 2. key findings, 3. files changed, 4. remaining work, 5. user constraints.\n\n" + conv}],
        max_tokens=2000)
    summary = r.choices[0].message.content or ""
    return [{"role": "user", "content": f"[Compacted]\n\n{summary}"}]


# ═══════════════════════════════════════════════════════════
#  agent_loop — 主循环（注入记忆与提取记忆）
# ═══════════════════════════════════════════════════════════

def agent_loop(messages: list):
    # s09 核心：在每轮用户发言时，查一下记忆，加载相关的详细内容
    memories_content = load_memories(messages)
    memory_turn = len(messages) - 1 if messages and isinstance(messages[-1].get("content"), str) else None
    
    # 动态构建 SYSTEM prompt（里面包含最新的记忆目录）
    system = build_system()

    while True:
        # 保存一个压缩前的快照，用于稍后高精度地提取新记忆
        pre_compress = [m.copy() for m in messages]

        # s08: 执行四层压缩流水线
        messages[:] = tool_result_budget(messages)
        messages[:] = snip_compact(messages)
        messages[:] = micro_compact(messages)
        if estimate_size(messages) > CONTEXT_LIMIT:
            print("[auto compact触发，正在摘要...]")
            messages[:] = compact_history(messages)

        request_messages = messages
        # 把相关的记忆具体内容“偷偷”塞进这轮发送的 messages 里，但不修改原本的 messages 列表
        if memories_content and memory_turn is not None and memory_turn < len(messages):
            request_messages = messages.copy()
            request_messages[memory_turn] = {
                **messages[memory_turn],
                "content": memories_content + "\n\n" + messages[memory_turn]["content"],
            }

        formatted_messages = [{"role": "system", "content": system}] + request_messages
        response = client.chat.completions.create(
            model=MODEL, messages=formatted_messages,
            tools=[{"type": "function", "function": t} for t in TOOLS], max_tokens=8000
        )
        response_message = response.choices[0].message
        
        # 记录助手的回复
        messages.append({
            "role": "assistant",
            "content": response_message.content or "",
            "tool_calls": [t.model_dump() for t in response_message.tool_calls] if response_message.tool_calls else None
        })

        # 如果大模型决定不用工具了，说明这一轮思考结束了
        if response.choices[0].finish_reason != "tool_calls":
            # s09 核心：对话告一段落时，扫描刚才未压缩的完整对话，提取值得记住的东西
            extract_memories(pre_compress)
            consolidate_memories()
            return

        # 如果需要调工具，执行工具并存入结果
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                print(f"\033[36m> {tool_call.function.name}\033[0m")
                args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                handler = TOOL_HANDLERS.get(tool_call.function.name)
                output = handler(**args) if handler else f"Unknown: {tool_call.function.name}"
                print(str(output)[:200])
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": output})

if __name__ == "__main__":
    print("s09: Memory — 跨越会话的长期记忆术")
    print("输入问题，回车发送。输入 q 退出。\n")
    history = []
    while True:
        try: query = input("\033[36ms09 >> \033[0m")
        except (EOFError, KeyboardInterrupt): break
        if query.strip().lower() in ("q", "exit", ""): break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        content = history[-1].get("content", "")
        if content:
            print(content)
        print()
