#!/usr/bin/env python3
"""
s12_code_annotated.py - Task System (中文注释版)

核心思想：
复杂的项目不能指望大模型一口气写完，需要拆解成一个个小任务。
而且任务之间有先后顺序（比如先建表再写 API）。
我们将实现一个基于文件持久化的任务系统，支持：
1. 任务创建 (带依赖 blockedBy)
2. 任务认领 (claim -> in_progress)
3. 任务完成 (complete -> completed) 并自动解锁下游任务。
"""

import os, subprocess, json, time, random
from pathlib import Path
from dataclasses import dataclass, asdict

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

# ═══════════════════════════════════════════════════════════
#  NEW in s12: 任务系统 (Task System)
# ═══════════════════════════════════════════════════════════

# 任务持久化存储目录（相当于本地的小型数据库）
TASKS_DIR = WORKDIR / ".tasks"
TASKS_DIR.mkdir(exist_ok=True)

@dataclass
class Task:
    """定义单个任务的数据结构"""
    id: str
    subject: str
    description: str
    status: str          # 状态机：pending | in_progress | completed
    owner: str | None    # 谁在做这个任务（为多 Agent 协作预留）
    blockedBy: list[str] # 依赖的前置任务 ID 列表

def _task_path(task_id: str) -> Path:
    """根据 ID 获取任务 JSON 文件的路径"""
    return TASKS_DIR / f"{task_id}.json"

def save_task(task: Task):
    """将任务持久化保存到磁盘"""
    _task_path(task.id).write_text(json.dumps(asdict(task), indent=2, ensure_ascii=False), encoding="utf-8")

def load_task(task_id: str) -> Task:
    """从磁盘读取任务"""
    return Task(**json.loads(_task_path(task_id).read_text(encoding="utf-8")))

def list_tasks() -> list[Task]:
    """列出当前所有的任务"""
    return [Task(**json.loads(p.read_text(encoding="utf-8")))
            for p in sorted(TASKS_DIR.glob("task_*.json"))]

def can_start(task_id: str) -> bool:
    """
    检查一个任务是否可以开始。
    规则：它依赖的所有前置任务（blockedBy）必须都已经是 "completed" 状态。
    """
    task = load_task(task_id)
    for dep_id in task.blockedBy:
        # 如果前置依赖任务的文件不存在，也认为被阻塞
        if not _task_path(dep_id).exists():
            return False
        if load_task(dep_id).status != "completed":
            return False
    return True

# ── 供 Agent 调用的任务管理核心方法 ──

def create_task(subject: str, description: str = "", blockedBy: list[str] | None = None) -> Task:
    """创建新任务"""
    task = Task(
        id=f"task_{int(time.time())}_{random.randint(0, 9999):04d}",
        subject=subject,
        description=description,
        status="pending",
        owner=None,
        blockedBy=blockedBy or [],
    )
    save_task(task)
    return task

def get_task(task_id: str) -> str:
    """获取某个任务的详细 JSON 描述"""
    task = load_task(task_id)
    return json.dumps(asdict(task), indent=2, ensure_ascii=False)

def claim_task(task_id: str, owner: str = "agent") -> str:
    """
    认领任务（将状态变为 in_progress）。
    如果前置依赖没做完，认领会被拒绝。
    """
    task = load_task(task_id)
    if task.status != "pending":
        return f"Task {task_id} is {task.status}, cannot claim"
    
    if not can_start(task_id):
        # 找出到底是哪个讨厌的前置任务卡住了我
        deps = [d for d in task.blockedBy
                if not _task_path(d).exists() or load_task(d).status != "completed"]
        return f"Blocked by incomplete dependencies: {deps}"
        
    task.owner = owner
    task.status = "in_progress"
    save_task(task)
    print(f"  \033[36m[Task Claimed] {task.subject} → in_progress (负责人: {owner})\033[0m")
    return f"Successfully claimed {task.id} ({task.subject})"

def complete_task(task_id: str) -> str:
    """
    完成任务。
    完成之后，会自动扫描全局，看看有没有下游任务因为这个任务的完成而解锁。
    """
    task = load_task(task_id)
    if task.status != "in_progress":
        return f"Task {task_id} is {task.status}, cannot complete (must be in_progress first)"
        
    task.status = "completed"
    save_task(task)
    
    # 扫描并找出刚刚被解锁的下游任务
    unblocked = [t.subject for t in list_tasks()
                 if t.status == "pending" and t.blockedBy and can_start(t.id)]
                 
    print(f"  \033[32m[Task Completed] {task.subject} ✓\033[0m")
    msg = f"Completed {task.id} ({task.subject})"
    if unblocked:
        msg += f"\nUnblocked downstream tasks: {', '.join(unblocked)}"
        print(f"  \033[33m[Tasks Unblocked] 下游任务已解锁: {', '.join(unblocked)}\033[0m")
    return msg


# ═══════════════════════════════════════════════════════════
#  基础工具与包装 (为了适配 OpenAI 工具调用格式)
# ═══════════════════════════════════════════════════════════

def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR): raise ValueError(f"Path escapes workspace: {p}")
    return path

def run_bash(command: str) -> str:
    try:
        r = subprocess.run(command, shell=True, cwd=WORKDIR, capture_output=True, text=True, errors='replace', timeout=120)
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
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e: return f"Error: {e}"

# --- 为 Task System 包装的工具执行器 ---

def run_create_task(subject: str, description: str = "", blockedBy: list[str] | None = None) -> str:
    task = create_task(subject, description, blockedBy)
    deps = f" (blockedBy: {', '.join(blockedBy)})" if blockedBy else ""
    print(f"  \033[34m[Task Created] {task.subject}{deps}\033[0m")
    return f"Created {task.id}: {task.subject}{deps}"

def run_list_tasks() -> str:
    tasks = list_tasks()
    if not tasks:
        return "No tasks found. Use create_task to add some."
    lines = []
    for t in tasks:
        # pending=空心圆, in_progress=实心圆, completed=打钩
        icon = {"pending": "○", "in_progress": "●", "completed": "✓"}.get(t.status, "?")
        deps = f" (blockedBy: {', '.join(t.blockedBy)})" if t.blockedBy else ""
        owner = f" [{t.owner}]" if t.owner else ""
        lines.append(f"  {icon} {t.id}: {t.subject} [{t.status}]{owner}{deps}")
    return "\n".join(lines)

def run_get_task(task_id: str) -> str:
    try: return get_task(task_id)
    except Exception: return f"Error: Task {task_id} not found"

def run_claim_task(task_id: str) -> str:
    try: return claim_task(task_id, owner="agent")
    except Exception as e: return f"Error: {e}"

def run_complete_task(task_id: str) -> str:
    try: return complete_task(task_id)
    except Exception as e: return f"Error: {e}"

# 工具注册表
TOOLS = [
    {"type": "function", "function": {"name": "bash", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read file contents.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Write content to a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "create_task", "description": "Create a new task with optional blockedBy dependencies.", "parameters": {"type": "object", "properties": {"subject": {"type": "string"}, "description": {"type": "string"}, "blockedBy": {"type": "array", "items": {"type": "string"}}}, "required": ["subject"]}}},
    {"type": "function", "function": {"name": "list_tasks", "description": "List all tasks with status, owner, and dependencies.", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "get_task", "description": "Get full details of a specific task by ID.", "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}}},
    {"type": "function", "function": {"name": "claim_task", "description": "Claim a pending task. Sets owner, changes status to in_progress.", "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}}},
    {"type": "function", "function": {"name": "complete_task", "description": "Complete an in-progress task. Reports unblocked downstream tasks.", "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}}},
]

TOOL_HANDLERS = {
    "bash": run_bash, "read_file": run_read, "write_file": run_write,
    "create_task": run_create_task, "list_tasks": run_list_tasks,
    "get_task": run_get_task, "claim_task": run_claim_task, "complete_task": run_complete_task,
}


# ═══════════════════════════════════════════════════════════
#  FROM s10: Prompt 组装与上下文
# ═══════════════════════════════════════════════════════════

PROMPT_SECTIONS = {
    "identity": "You are a coding agent. Act, don't explain. Manage complex workflows using the task system.",
    "tools": "Available tools: bash, read_file, write_file, create_task, list_tasks, get_task, claim_task, complete_task.",
    "workspace": f"Working directory: {WORKDIR}",
}

def assemble_system_prompt(context: dict) -> str:
    sections = [PROMPT_SECTIONS["identity"], PROMPT_SECTIONS["tools"], PROMPT_SECTIONS["workspace"]]
    return "\n\n".join(sections)

_last_context_key, _last_prompt = None, None
def get_system_prompt(context: dict) -> str:
    global _last_context_key, _last_prompt
    key = json.dumps(context, sort_keys=True, ensure_ascii=False, default=str)
    if key == _last_context_key and _last_prompt:
        return _last_prompt
    _last_context_key = key
    _last_prompt = assemble_system_prompt(context)
    return _last_prompt

def update_context(context: dict, messages: list) -> dict:
    return {"workspace": str(WORKDIR)}


# ═══════════════════════════════════════════════════════════
#  Agent Loop (简化版，专注演示任务系统)
# ═══════════════════════════════════════════════════════════

def agent_loop(messages: list, context: dict):
    system = get_system_prompt(context)
    while True:
        formatted_messages = [{"role": "system", "content": system}] + messages
        
        try:
            response = client.chat.completions.create(
                model=MODEL, messages=formatted_messages,
                tools=TOOLS, max_tokens=8000
            )
        except Exception as e:
            messages.append({"role": "assistant", "content": f"[Error] {type(e).__name__}: {e}"})
            return

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
                print(str(output)[:300])
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": output})

        context = update_context(context, messages)
        system = get_system_prompt(context)


if __name__ == "__main__":
    print("s12: Task System — 持久化的任务依赖网络")
    print("输入问题，回车发送。输入 q 退出。\n")
    
    history = []
    context = update_context({}, [])
    
    while True:
        try:
            query = input("\033[36ms12 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
            
        turn_start = len(history)
        history.append({"role": "user", "content": query})
        
        agent_loop(history, context)
        context = update_context(context, history)
        
        for msg in history[turn_start:]:
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content", "")
            if content:
                print(content)
        print()
