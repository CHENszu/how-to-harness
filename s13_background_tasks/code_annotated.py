import os, json, time, re, subprocess, threading, random
from pathlib import Path
from dataclasses import dataclass, asdict

# 使用 OpenAI 兼容库
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)

WORKDIR = Path.cwd()
MEMORY_DIR = WORKDIR / ".memory"
MEMORY_DIR.mkdir(exist_ok=True)
MEMORY_INDEX = MEMORY_DIR / "MEMORY.md"

client = OpenAI(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.deepseek.com/v1")
)
MODEL = os.environ.get("MODEL_ID", "deepseek-chat")

# ═══════════════════════════════════════════════════════════
#  任务系统 (简化的 S12 任务系统，为了演示后台任务)
# ═══════════════════════════════════════════════════════════

TASKS_DIR = WORKDIR / ".tasks"
TASKS_DIR.mkdir(exist_ok=True)

@dataclass
class Task:
    id: str
    subject: str
    description: str
    status: str
    owner: str | None
    blockedBy: list[str]

def _task_path(task_id: str) -> Path: return TASKS_DIR / f"{task_id}.json"
def save_task(task: Task): _task_path(task.id).write_text(json.dumps(asdict(task), indent=2), encoding="utf-8")
def load_task(task_id: str) -> Task: return Task(**json.loads(_task_path(task_id).read_text(encoding="utf-8")))
def list_tasks() -> list[Task]: return [Task(**json.loads(p.read_text(encoding="utf-8"))) for p in sorted(TASKS_DIR.glob("task_*.json"))]

def create_task(subject: str, description: str = "", blockedBy: list[str] | None = None) -> Task:
    task = Task(id=f"task_{int(time.time())}_{random.randint(0, 9999):04d}", subject=subject, description=description, status="pending", owner=None, blockedBy=blockedBy or [])
    save_task(task)
    return task

def run_create_task(subject: str, description: str = "", blockedBy: list[str] | None = None) -> str:
    task = create_task(subject, description, blockedBy)
    print(f"  \033[34m[创建任务] {task.subject}\033[0m")
    return f"Created {task.id}: {task.subject}"

def run_list_tasks() -> str:
    tasks = list_tasks()
    if not tasks: return "No tasks."
    return "\n".join(f"  {'✓' if t.status=='completed' else '●' if t.status=='in_progress' else '○'} {t.id}: {t.subject} [{t.status}]" for t in tasks)


# ═══════════════════════════════════════════════════════════
#  核心新增: 后台任务系统 (Background Tasks)
# ═══════════════════════════════════════════════════════════

_bg_counter = 0
background_tasks: dict[str, dict] = {}   # bg_id → {tool_use_id, command, status}
background_results: dict[str, str] = {}   # bg_id → output
background_lock = threading.Lock()

def is_slow_operation(tool_name: str, args: dict) -> bool:
    """启发式判断：猜测哪些命令会很慢"""
    if tool_name != "bash": return False
    cmd = args.get("command", "").lower()
    slow_keywords = ["install", "build", "test", "deploy", "compile", "docker build", "pip install", "npm install", "cargo build", "pytest", "make"]
    return any(kw in cmd for kw in slow_keywords)

def should_run_background(tool_name: str, args: dict) -> bool:
    """决定是否在后台运行：模型显式请求优先，启发式判断兜底"""
    if args.get("run_in_background"): return True
    return is_slow_operation(tool_name, args)

def start_background_task(tool_call_id: str, tool_name: str, args: dict) -> str:
    """把慢操作扔到后台线程执行"""
    global _bg_counter
    _bg_counter += 1
    bg_id = f"bg_{_bg_counter:04d}"
    cmd = args.get("command", tool_name)

    def worker():
        handler = TOOL_HANDLERS.get(tool_name)
        result = handler(**args) if handler else f"未知工具: {tool_name}"
        with background_lock:
            background_tasks[bg_id]["status"] = "completed"
            background_results[bg_id] = result

    with background_lock:
        background_tasks[bg_id] = {
            "tool_use_id": tool_call_id,
            "command": cmd,
            "status": "running",
        }
    
    # daemon=True 意味着主程序退出时，这个线程也会被强行杀死
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    print(f"  \033[33m[后台启动] 分配了 {bg_id}: {cmd[:40]}\033[0m")
    return bg_id

def collect_background_results() -> list[str]:
    """收集已经完成的后台任务，转化为 <task_notification> 通知"""
    with background_lock:
        ready_ids = [bid for bid, task in background_tasks.items() if task["status"] == "completed"]
    
    notifications = []
    for bg_id in ready_ids:
        with background_lock:
            task = background_tasks.pop(bg_id)
            output = background_results.pop(bg_id, "")
        
        summary = output[:200] if len(output) > 200 else output
        notifications.append(
            f"<task_notification>\n"
            f"  <task_id>{bg_id}</task_id>\n"
            f"  <status>completed</status>\n"
            f"  <command>{task['command']}</command>\n"
            f"  <summary>{summary}</summary>\n"
            f"</task_notification>"
        )
        print(f"  \033[32m[后台完成] {bg_id}: {task['command'][:40]} (共 {len(output)} 个字符)\033[0m")
    return notifications


# ═══════════════════════════════════════════════════════════
#  常规工具与 Prompt 组装
# ═══════════════════════════════════════════════════════════

def run_bash(command: str, run_in_background: bool = False) -> str:
    # 注意：run_in_background 参数是在 agent_loop 的派发阶段处理的，不是在这里
    try:
        r = subprocess.run(command, shell=True, cwd=WORKDIR, capture_output=True, timeout=120)
        stdout = r.stdout.decode('utf-8', errors='replace') if r.stdout else ""
        stderr = r.stderr.decode('utf-8', errors='replace') if r.stderr else ""
        out = (stdout + stderr).strip()
        # 如果是后台任务，故意模拟一个慢操作
        if run_in_background or is_slow_operation("bash", {"command": command}):
            time.sleep(3) 
        return out[:50000] if out else "(无输出)"
    except subprocess.TimeoutExpired: return "Error: Timeout"

def run_read(path: str) -> str:
    try: return (WORKDIR / path).read_text(encoding="utf-8")
    except Exception as e: return f"Error: {e}"

TOOLS = [
    {"type": "function", "function": {"name": "bash", "description": "执行终端命令。如果预计耗时较长，请设置 run_in_background=true", "parameters": {"type": "object", "properties": {"command": {"type": "string"}, "run_in_background": {"type": "boolean"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "读取文件", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "create_task", "description": "创建任务", "parameters": {"type": "object", "properties": {"subject": {"type": "string"}, "description": {"type": "string"}}, "required": ["subject"]}}},
    {"type": "function", "function": {"name": "list_tasks", "description": "列出所有任务", "parameters": {"type": "object", "properties": {}}}},
]
TOOL_HANDLERS = {"bash": run_bash, "read_file": run_read, "create_task": run_create_task, "list_tasks": run_list_tasks}

def get_system_prompt() -> str:
    return (
        f"你是一个编码助手，当前目录: {WORKDIR}\n"
        "1. 如果你要执行 pip install, npm install, build 等慢速命令，必须在 bash 工具中设置 run_in_background=true。\n"
        "2. 后台任务启动后，你可以继续执行其他快操作（比如 read_file）。\n"
        "3. 当后台任务完成后，你会收到 <task_notification> 格式的通知。"
    )

# ═══════════════════════════════════════════════════════════
#  核心循环: 处理异步通知的注入
# ═══════════════════════════════════════════════════════════
def agent_loop(messages: list):
    system = get_system_prompt()
    while True:
        request_messages = [{"role": "system", "content": system}] + messages
        response = client.chat.completions.create(model=MODEL, messages=request_messages, tools=TOOLS, max_tokens=4000)
        msg = response.choices[0].message
        
        assistant_msg = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [{"id": t.id, "type": "function", "function": {"name": t.function.name, "arguments": t.function.arguments}} for t in msg.tool_calls]
        messages.append(assistant_msg)
        
        if msg.content: print(msg.content)
        if not msg.tool_calls: return

        # 收集所有的 tool_result 和 后台通知
        results = []
        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            print(f"\033[36m> 使用工具: {name}\033[0m")
            
            # 【分流】如果是慢操作，扔到后台
            if should_run_background(name, args):
                bg_id = start_background_task(tool_call.id, name, args)
                # 立即返回一个占位符结果给模型
                results.append({"role": "tool", "tool_call_id": tool_call.id, "name": name, 
                                "content": f"[后台任务 {bg_id} 已启动] 命令: {args.get('command', '')}。完成后会收到通知。"})
            else:
                # 如果是快操作，同步执行
                handler = TOOL_HANDLERS.get(name)
                output = handler(**args) if handler else f"未知工具: {name}"
                results.append({"role": "tool", "tool_call_id": tool_call.id, "name": name, "content": str(output)})

        # 【注入通知】在把工具结果发回给模型的同时，检查有没有已经完成的后台任务
        bg_notifications = collect_background_results()
        if bg_notifications:
            for notif in bg_notifications:
                # 注意：通知不能用 tool 角色，因为没有对应的 tool_call_id。
                # 只能作为一个普通的 user text 追加进去。
                results.append({"role": "user", "content": notif})
            print(f"  \033[32m[注入] {len(bg_notifications)} 个后台任务通知\033[0m")
            
        messages.extend(results)

if __name__ == "__main__":
    print("s13: Background Tasks — 慢操作放后台 (中文版)")
    print("试着输入：'请在后台运行 pip list，并在等待期间读取 README.md 文件'\n")
    history = []
    while True:
        try: query = input("\033[36ms13 >> \033[0m")
        except (EOFError, KeyboardInterrupt): break
        if not query.strip(): break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        print()