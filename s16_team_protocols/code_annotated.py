#!/usr/bin/env python3
"""
s16: Team Protocols — request-response protocol + request_id + dispatch + state machine.

Run:  python s16_team_protocols/code.py
Need: pip install anthropic python-dotenv + .env with ANTHROPIC_API_KEY

Changes from s15:
  - ProtocolState dataclass (request_id, type, sender, status, created_at)
  - pending_requests dict: tracks in-flight protocol requests
  - dispatch_message: routes incoming messages by type to handlers
  - request_shutdown: Lead sends shutdown protocol request
  - request_plan: Lead asks teammate to submit plan
  - handle_shutdown_request / handle_plan_response: teammate receives & responds
  - match_response: Lead correlates response to request via request_id (with type validation)
  - Teammate idle loop: waits for inbox messages instead of exiting after 10 rounds
  - Unified consume_lead_inbox: protocol routing + injection into history
  - 3 new Lead tools: request_shutdown, request_plan, review_plan
  - 1 new teammate tool: submit_plan

ASCII flow:
  Lead: BUS.send("shutdown_request", {request_id}) ──────→ teammate inbox
  Teammate: dispatch → handler → BUS.send("shutdown_response", {request_id}) ─→ Lead inbox
  Lead: consume_lead_inbox → match_response(request_id) → pending_requests[req_id].status = approved
"""

import os, subprocess, json, time, random, threading
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field

try:
    import readline
    readline.parse_and_bind('set bind-tty-special-chars off')
except ImportError:
    pass

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)
client = OpenAI(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.deepseek.com/v1")
)

WORKDIR = Path.cwd()
MEMORY_DIR = WORKDIR / ".memory"
MEMORY_INDEX = MEMORY_DIR / "MEMORY.md"
MODEL = os.environ["MODEL_ID"]

# ── Task System (from s12, synced) ──

TASKS_DIR = WORKDIR / ".tasks"
TASKS_DIR.mkdir(exist_ok=True)


@dataclass
class Task:
    id: str
    subject: str
    description: str
    status: str          # pending | in_progress | completed
    owner: str | None
    blockedBy: list[str]


def _task_path(task_id: str) -> Path:
    return TASKS_DIR / f"{task_id}.json"


def create_task(subject: str, description: str = "",
                blockedBy: list[str] | None = None) -> Task:
    task = Task(
        id=f"task_{int(time.time())}_{random.randint(0, 9999):04d}",
        subject=subject, description=description,
        status="pending", owner=None,
        blockedBy=blockedBy or [],
    )
    save_task(task)
    return task


def save_task(task: Task):
    _task_path(task.id).write_text(json.dumps(asdict(task), indent=2))


def load_task(task_id: str) -> Task:
    return Task(**json.loads(_task_path(task_id).read_text()))


def list_tasks() -> list[Task]:
    return [Task(**json.loads(p.read_text()))
            for p in sorted(TASKS_DIR.glob("task_*.json"))]


def get_task(task_id: str) -> str:
    """Return full task details as JSON."""
    task = load_task(task_id)
    return json.dumps(asdict(task), indent=2)


def can_start(task_id: str) -> bool:
    """Check if all blockedBy dependencies are completed.
    Missing dependencies are treated as blocked."""
    task = load_task(task_id)
    for dep_id in task.blockedBy:
        if not _task_path(dep_id).exists():
            return False
        if load_task(dep_id).status != "completed":
            return False
    return True


def claim_task(task_id: str, owner: str = "agent") -> str:
    task = load_task(task_id)
    if task.status != "pending":
        return f"Task {task_id} is {task.status}, cannot claim"
    if not can_start(task_id):
        deps = [d for d in task.blockedBy
                if not _task_path(d).exists() or load_task(d).status != "completed"]
        return f"Blocked by: {deps}"
    task.owner = owner
    task.status = "in_progress"
    save_task(task)
    print(f"  \033[36m[claim] {task.subject} → in_progress (owner: {owner})\033[0m")
    return f"Claimed {task.id} ({task.subject})"


def complete_task(task_id: str) -> str:
    task = load_task(task_id)
    if task.status != "in_progress":
        return f"Task {task_id} is {task.status}, cannot complete"
    task.status = "completed"
    save_task(task)
    unblocked = [t.subject for t in list_tasks()
                 if t.status == "pending" and t.blockedBy and can_start(t.id)]
    print(f"  \033[32m[complete] {task.subject} ✓\033[0m")
    msg = f"Completed {task.id} ({task.subject})"
    if unblocked:
        msg += f"\nUnblocked: {', '.join(unblocked)}"
        print(f"  \033[33m[unblocked] {', '.join(unblocked)}\033[0m")
    return msg


# ── Prompt Assembly (from s10, synced) ──

PROMPT_SECTIONS = {
    "identity": "You are a coding agent. Act, don't explain.",
    "tools": "Available tools: bash, read_file, write_file, "
             "get_task, create_task, list_tasks, claim_task, complete_task, "
             "spawn_teammate, send_message, check_inbox, "
             "request_shutdown, request_plan, review_plan.",
    "workspace": f"Working directory: {WORKDIR}",
    "memory": "Relevant memories are injected below when available.",
}


def assemble_system_prompt(context: dict) -> str:
    sections = [PROMPT_SECTIONS["identity"],
                PROMPT_SECTIONS["tools"],
                PROMPT_SECTIONS["workspace"]]
    memories = context.get("memories", "")
    if memories:
        sections.append(f"Relevant memories:\n{memories}")
    return "\n\n".join(sections)


_last_context_key, _last_prompt = None, None


def get_system_prompt(context: dict, role_name: str = "lead") -> str:
    global _last_context_key, _last_prompt
    key = json.dumps(context, sort_keys=True, ensure_ascii=False, default=str)
    # 队友不使用缓存
    if role_name == "lead" and key == _last_context_key and _last_prompt:
        return _last_prompt
    
    sections = [PROMPT_SECTIONS["identity"],
                PROMPT_SECTIONS["tools"],
                PROMPT_SECTIONS["workspace"]]
    memories = context.get("memories", "")
    if memories:
        sections.append(f"Relevant memories:\n{memories}")
    prompt = "\n\n".join(sections)
    
    if role_name == "lead":
        _last_context_key = key
        _last_prompt = prompt
        
    return prompt


# ── Tools ──

def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_bash(command: str, run_in_background: bool = False) -> str:
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
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


# Task tools

def run_create_task(subject: str, description: str = "",
                    blockedBy: list[str] | None = None) -> str:
    task = create_task(subject, description, blockedBy)
    deps = f" (blockedBy: {', '.join(blockedBy)})" if blockedBy else ""
    print(f"  \033[34m[create] {task.subject}{deps}\033[0m")
    return f"Created {task.id}: {task.subject}{deps}"


def run_list_tasks() -> str:
    tasks = list_tasks()
    if not tasks:
        return "No tasks. Use create_task to add some."
    lines = []
    for t in tasks:
        icon = {"pending": "○", "in_progress": "●",
                "completed": "✓"}.get(t.status, "?")
        deps = f" (blockedBy: {', '.join(t.blockedBy)})" if t.blockedBy else ""
        owner = f" [{t.owner}]" if t.owner else ""
        lines.append(f"  {icon} {t.id}: {t.subject} "
                     f"[{t.status}]{owner}{deps}")
    return "\n".join(lines)


def run_get_task(task_id: str) -> str:
    try:
        return get_task(task_id)
    except FileNotFoundError:
        return f"Error: Task {task_id} not found"


def run_claim_task(task_id: str) -> str:
    return claim_task(task_id, owner="agent")


def run_complete_task(task_id: str) -> str:
    return complete_task(task_id)


# ── Background Tasks (from s13, synced) ──

_bg_counter = 0
background_tasks: dict[str, dict] = {}
background_results: dict[str, str] = {}
background_lock = threading.Lock()


def is_slow_operation(tool_name: str, tool_input: dict) -> bool:
    """Fallback heuristic: commands likely to take > 30s."""
    if tool_name != "bash":
        return False
    cmd = tool_input.get("command", "").lower()
    slow_keywords = ["install", "build", "test", "deploy", "compile",
                     "docker build", "pip install", "npm install",
                     "cargo build", "pytest", "make"]
    return any(kw in cmd for kw in slow_keywords)


def should_run_background(tool_name: str, tool_input: dict) -> bool:
    """Model explicit request takes priority; fallback to heuristic."""
    if tool_input.get("run_in_background"):
        return True
    return is_slow_operation(tool_name, tool_input)


def start_background_task(block) -> str:
    """Run tool in a daemon thread. Returns background task ID."""
    global _bg_counter
    _bg_counter += 1
    bg_id = f"bg_{_bg_counter:04d}"
    cmd = block.input.get("command", block.name)

    def worker():
        result = execute_tool(block)
        with background_lock:
            background_tasks[bg_id]["status"] = "completed"
            background_results[bg_id] = result

    with background_lock:
        background_tasks[bg_id] = {
            "tool_use_id": block.id,
            "command": cmd,
            "status": "running",
        }
    threading.Thread(target=worker, daemon=True).start()
    print(f"  \033[33m[background] dispatched {bg_id}: {cmd[:40]}\033[0m")
    return bg_id


def collect_background_results() -> list[str]:
    """Collect completed background results as task_notification messages."""
    with background_lock:
        ready_ids = [bid for bid, task in background_tasks.items()
                     if task["status"] == "completed"]
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
            f"</task_notification>")
        print(f"  \033[32m[background done] {bg_id}: "
              f"{task['command'][:40]} ({len(output)} chars)\033[0m")
    return notifications


# ── MessageBus (from s15) ──

MAILBOX_DIR = WORKDIR / ".mailboxes"
MAILBOX_DIR.mkdir(exist_ok=True)


class MessageBus:
    """File-based message bus. Each agent has a .jsonl inbox.
    Read is destructive: read_text + unlink (consumes messages).
    Teaching version: no file locking; real CC uses proper-lockfile."""

    def send(self, from_agent: str, to_agent: str, content: str,
             msg_type: str = "message", metadata: dict = None):
        msg = {"from": from_agent, "to": to_agent,
               "content": content, "type": msg_type,
               "ts": time.time(), "metadata": metadata or {}}
        inbox = MAILBOX_DIR / f"{to_agent}.jsonl"
        with open(inbox, "a") as f:
            f.write(json.dumps(msg) + "\n")
        print(f"  \033[33m[bus] {from_agent} → {to_agent}: "
              f"({msg_type}) {content[:50]}\033[0m")

    def read_inbox(self, agent: str) -> list[dict]:
        inbox = MAILBOX_DIR / f"{agent}.jsonl"
        if not inbox.exists():
            return []
        msgs = [json.loads(line) for line in inbox.read_text().splitlines()
                if line.strip()]
        inbox.unlink()  # consume: read + delete
        return msgs


BUS = MessageBus()
active_teammates: dict[str, bool] = {}
team_lock = threading.Lock()

# ── Protocol State (s16 new) ──

@dataclass
class ProtocolState:
    request_id: str
    type: str       # "shutdown" | "plan_approval"
    sender: str
    target: str
    status: str     # pending | approved | rejected
    payload: str    # plan text or shutdown reason
    created_at: float = field(default_factory=time.time)


pending_requests: dict[str, ProtocolState] = {}


def new_request_id() -> str:
    return f"req_{random.randint(0, 999999):06d}"


def match_response(response_type: str, request_id: str, approve: bool):
    """Correlate a response to the original request via request_id.
    Validates that response_type matches the request type."""
    state = pending_requests.get(request_id)
    if not state:
        print(f"  \033[31m[protocol] unknown request_id: {request_id}\033[0m")
        return
    # Validate response type matches request type
    if state.type == "shutdown" and response_type != "shutdown_response":
        print(f"  \033[31m[protocol] type mismatch: expected shutdown_response, "
              f"got {response_type}\033[0m")
        return
    if state.type == "plan_approval" and response_type != "plan_approval_response":
        print(f"  \033[31m[protocol] type mismatch: expected plan_approval_response, "
              f"got {response_type}\033[0m")
        return
    if state.status != "pending":
        print(f"  \033[33m[protocol] {request_id} already {state.status}, "
              f"ignoring duplicate\033[0m")
        return
    state.status = "approved" if approve else "rejected"
    icon = "✓" if approve else "✗"
    color = "32" if approve else "31"
    print(f"  \033[{color}m[protocol] {state.type} {icon} "
          f"({request_id}: {state.status})\033[0m")


# ── Unified Lead Inbox Consumer (s16 fix) ──
# Both check_inbox tool and main loop call this function.
# Protocol responses are routed via match_response before returning.

def consume_lead_inbox(route_protocol: bool = True) -> list[dict]:
    """Read Lead's inbox. Route protocol responses, return all messages.
    Called by both run_check_inbox() and main loop to avoid
    messages being consumed without protocol routing."""
    msgs = BUS.read_inbox("lead")
    if not msgs:
        return []
    if route_protocol:
        for msg in msgs:
            meta = msg.get("metadata", {})
            req_id = meta.get("request_id", "")
            msg_type = msg.get("type", "")
            if req_id and msg_type.endswith("_response"):
                approve = meta.get("approve", False)
                match_response(msg_type, req_id, approve)
    return msgs


# ── Teammate Thread (s16: idle loop + dispatch) ──

def spawn_teammate_thread(name: str, role: str, prompt: str) -> str:
    """Launch a teammate in a background thread."""
    name = name.lower().replace(" ", "_")
    with team_lock:
        if name in active_teammates or name == "lead":
            return f"Error: name '{name}' is already in use."
        active_teammates[name] = True

    system = (f"You are '{name}', a {role}. "
              f"Use tools to complete tasks. Act, don't explain.")

    def handle_inbox_message(name: str, msg: dict, messages: list) -> bool:
        """Dispatch incoming protocol messages by type.
        Returns True if teammate should stop."""
        msg_type = msg.get("type", "message")
        meta = msg.get("metadata", {})
        req_id = meta.get("request_id", "")

        if msg_type == "shutdown_request":
            BUS.send(name, "lead", "Shutting down gracefully.",
                     "shutdown_response",
                     {"request_id": req_id, "approve": True})
            print(f"  \033[35m[protocol] {name} approved shutdown "
                  f"({req_id})\033[0m")
            return True  # stop the loop

        if msg_type == "plan_approval_response":
            approve = meta.get("approve", False)
            if approve:
                messages.append({"role": "user",
                    "content": f"[Plan approved] Proceed with the task."})
            else:
                messages.append({"role": "user",
                    "content": f"[Plan rejected] Feedback: {msg['content']}"})

        return False  # continue

    def run():
        try:
            print(f"  \033[35m[Team] 召唤队友 {name} 成功\033[0m")
            messages = [{"role": "user", "content": prompt}]
            
            sub_tools = [
                {"type": "function", "function": {"name": "bash", "description": "Run a shell command.",
                 "parameters": {"type": "object",
                                "properties": {"command": {"type": "string"}},
                                "required": ["command"]}}},
                {"type": "function", "function": {"name": "read_file", "description": "Read file contents.",
                 "parameters": {"type": "object",
                                "properties": {"path": {"type": "string"}},
                                "required": ["path"]}}},
                {"type": "function", "function": {"name": "write_file", "description": "Write content to a file.",
                 "parameters": {"type": "object",
                                "properties": {"path": {"type": "string"},
                                               "content": {"type": "string"}},
                                "required": ["path", "content"]}}},
                {"type": "function", "function": {"name": "send_message",
                 "description": "Send a message to another agent.",
                 "parameters": {"type": "object",
                                "properties": {"to": {"type": "string"},
                                               "content": {"type": "string"}},
                                "required": ["to", "content"]}}},
                {"type": "function", "function": {"name": "submit_plan",
                 "description": "Submit a plan for approval.",
                 "parameters": {"type": "object",
                                "properties": {"plan": {"type": "string"}},
                                "required": ["plan"]}}},
            ]
            sub_handlers = {
                "bash": run_bash, "read_file": run_read, "write_file": run_write,
                "send_message": lambda to, content: (BUS.send(name, to, content), "Sent")[1],
                "submit_plan": lambda plan: _teammate_submit_plan(name, plan)
            }

            # idle loop: teammates run until shutdown_request
            while True:
                # 1. read inbox (blocks if protocol message handles it)
                inbox = BUS.read_inbox(name)
                stop_requested = False
                for msg in inbox:
                    if handle_inbox_message(name, msg, messages):
                        stop_requested = True
                if stop_requested:
                    break

                if inbox:
                    inbox_text = "\n".join(f"From {m['from']}: {m['content'][:200]}" for m in inbox)
                    messages.append({"role": "user", "content": f"<inbox>\n{inbox_text}\n</inbox>"})
                elif len(messages) > 1 and messages[-1]["role"] == "assistant":
                    time.sleep(1)
                    continue

                response = client.chat.completions.create(
                    model=MODEL, 
                    messages=[{"role": "system", "content": system}] + messages[-20:],
                    tools=sub_tools, max_tokens=8000)
                response_message = response.choices[0].message
                
                if response_message.content:
                    messages.append({"role": "assistant", "content": response_message.content})
                    
                if not response_message.tool_calls:
                    continue
                    
                messages.append(response_message.model_dump(exclude_unset=True))
                results = []
                for tool_call in response_message.tool_calls:
                    block_name = tool_call.function.name
                    block_input = json.loads(tool_call.function.arguments)
                    handler = sub_handlers.get(block_name)
                    output = handler(**block_input) if handler else "Unknown"
                    results.append({"role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "name": block_name,
                                    "content": str(output)})
                for res in results:
                    messages.append(res)

            with team_lock:
                active_teammates.pop(name, None)
            print(f"  \033[35m[Team] 队友 {name} 体面退出\033[0m")
        except Exception as e:
            print(f"  \033[31m[Team] 队友 {name} 崩溃: {e}\033[0m")
            with team_lock:
                active_teammates.pop(name, None)

    threading.Thread(target=run, daemon=True).start()
    return f"Spawned teammate '{name}' as '{role}'"


def _teammate_submit_plan(from_name: str, plan: str) -> str:
    """Teammate submits a plan to Lead for approval.

    Note: This is a protocol-level request, not a code-level gate.
    After submitting, the teammate's thread continues running — it can
    still call bash/write/etc. Real enforcement relies on the model
    waiting for the approval response before acting. Code-level tool
    gating would require blocking the teammate's tool dispatch until
    approval arrives.
    """
    req_id = new_request_id()
    pending_requests[req_id] = ProtocolState(
        request_id=req_id, type="plan_approval",
        sender=from_name, target="lead",
        status="pending", payload=plan)
    BUS.send(from_name, "lead", plan,
             "plan_approval_request",
             {"request_id": req_id})
    return f"Plan submitted ({req_id}). Waiting for approval..."


# ── Lead Protocol Tools (s16 new) ──

def run_request_shutdown(teammate: str) -> str:
    req_id = new_request_id()
    pending_requests[req_id] = ProtocolState(
        request_id=req_id, type="shutdown",
        sender="lead", target=teammate,
        status="pending", payload="")
    BUS.send("lead", teammate, "Please shut down gracefully.",
             "shutdown_request",
             {"request_id": req_id})
    print(f"  \033[35m[protocol] shutdown_request → {teammate} "
          f"({req_id})\033[0m")
    return f"Shutdown request sent to {teammate} (req: {req_id})"


def run_request_plan(teammate: str, task: str) -> str:
    """Lead asks a teammate to submit a plan for a task."""
    BUS.send("lead", teammate, f"Please submit a plan for: {task}",
             "message")
    return f"Asked {teammate} to submit a plan"


def run_review_plan(request_id: str, approve: bool, feedback: str = "") -> str:
    state = pending_requests.get(request_id)
    if not state:
        return f"Request {request_id} not found"
    if state.status != "pending":
        return f"Request {request_id} already {state.status}"
    state.status = "approved" if approve else "rejected"
    BUS.send("lead", state.sender, feedback or ("Approved" if approve else "Rejected"),
             "plan_approval_response",
             {"request_id": request_id, "approve": approve})
    icon = "✓" if approve else "✗"
    print(f"  \033[32m[protocol] plan {icon} ({request_id})\033[0m")
    return f"Plan {'approved' if approve else 'rejected'} ({request_id})"


# ── Other Lead Tool Handlers ──

def run_spawn_teammate(name: str, role: str, prompt: str) -> str:
    return spawn_teammate_thread(name, role, prompt)


def run_send_message(to: str, content: str) -> str:
    BUS.send("lead", to, content)
    return f"Sent to {to}"


def run_check_inbox() -> str:
    """Check Lead's inbox. Routes protocol responses via match_response."""
    msgs = consume_lead_inbox(route_protocol=True)
    if not msgs:
        return "(inbox empty)"
    lines = []
    for m in msgs:
        meta = m.get("metadata", {})
        req_id = meta.get("request_id", "")
        tag = f" [{m['type']} req:{req_id}]" if req_id else f" [{m['type']}]"
        lines.append(f"  [{m['from']}]{tag} {m['content'][:200]}")
    return "\n".join(lines)


# ── Tool Dispatch ──

def execute_tool(block, tools: list[dict] = None) -> str:
    """Execute a tool call block, return output."""
    handler = {
        "bash": run_bash, "read_file": run_read, "write_file": run_write,
        "create_task": run_create_task, "list_tasks": run_list_tasks,
        "get_task": run_get_task, "claim_task": run_claim_task,
        "complete_task": run_complete_task,
        "spawn_teammate": run_spawn_teammate,
        "send_message": run_send_message, "check_inbox": run_check_inbox,
        "request_shutdown": run_request_shutdown,
        "request_plan": run_request_plan, "review_plan": run_review_plan,
    }.get(block.name)
    if handler:
        try:
            return handler(**block.input)
        except Exception as e:
            return f"Error executing tool {block.name}: {str(e)}. Please check your arguments and try again."
    return f"Unknown tool: {block.name}"


# ── Tool Definitions ──

TOOLS = [
    {"name": "bash", "description": "Run a shell command.",
     "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to a file.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "create_task", "description": "Create a new task.",
     "parameters": {"type": "object", "properties": {"description": {"type": "string"}}, "required": ["description"]}},
    {"name": "list_tasks", "description": "List all tasks.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_task", "description": "Get task details.",
     "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}},
    {"name": "claim_task", "description": "Claim a task.",
     "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]}},
    {"name": "complete_task", "description": "Complete a task.",
     "parameters": {"type": "object", "properties": {"task_id": {"type": "string"}, "result": {"type": "string"}}, "required": ["task_id", "result"]}},
    {"name": "schedule_cron", "description": "Schedule a cron job.",
     "parameters": {"type": "object", "properties": {"prompt": {"type": "string"}, "cron_expr": {"type": "string"}}, "required": ["prompt", "cron_expr"]}},
    {"name": "list_crons", "description": "List all cron jobs.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"name": "cancel_cron", "description": "Cancel a cron job.",
     "parameters": {"type": "object", "properties": {"job_id": {"type": "string"}}, "required": ["job_id"]}},
    {"name": "spawn_teammate", "description": "Spawn a teammate.",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "role": {"type": "string"}, "prompt": {"type": "string"}}, "required": ["name", "role", "prompt"]}},
    {"name": "send_message", "description": "Send a message.",
     "parameters": {"type": "object", "properties": {"to": {"type": "string"}, "content": {"type": "string"}}, "required": ["to", "content"]}},
    {"name": "check_inbox", "description": "Check your inbox.",
     "parameters": {"type": "object", "properties": {}, "required": []}},
    {"name": "request_shutdown", "description": "Request a teammate to shutdown.",
     "parameters": {"type": "object", "properties": {"teammate": {"type": "string"}}, "required": ["teammate"]}},
    {"name": "request_plan", "description": "Request a teammate to submit a plan.",
     "parameters": {"type": "object", "properties": {"teammate": {"type": "string"}, "task": {"type": "string"}}, "required": ["teammate", "task"]}},
    {"name": "review_plan", "description": "Review and approve/reject a plan.",
     "parameters": {"type": "object", "properties": {"request_id": {"type": "string"}, "approve": {"type": "boolean"}}, "required": ["request_id", "approve"]}},
]


# ── Context ──

def update_context(context: dict, messages: list) -> dict:
    """Derive context from real state."""
    memories = ""
    if MEMORY_INDEX.exists():
        content = MEMORY_INDEX.read_text().strip()
        if content:
            memories = content
    return {
        "enabled_tools": [t["name"] for t in TOOLS],
        "workspace": str(WORKDIR),
        "memories": memories,
    }


# ── Agent Loop ──

def agent_loop(messages: list, context: dict, tools: list[dict],
               role_name: str = "lead") -> dict:
    system = get_system_prompt(context, role_name)
    while True:
        try:
            response = client.chat.completions.create(
                model=MODEL, 
                messages=[{"role": "system", "content": system}] + messages,
                tools=[{"type": "function", "function": t} for t in tools], 
                max_tokens=8000
            )
            response_message = response.choices[0].message
        except Exception as e:
            messages.append({"role": "assistant", "content": f"[Error] {type(e).__name__}: {e}"})
            return context

        if response_message.content:
            messages.append({"role": "assistant", "content": response_message.content})
            if role_name == "lead":
                print(response_message.content)
                
        if not response_message.tool_calls:
            return context

        results = []
        messages.append(response_message.model_dump(exclude_unset=True))
        
        for tool_call in response_message.tool_calls:
            block_name = tool_call.function.name
            block_input = json.loads(tool_call.function.arguments)
            
            class Block: pass
            block = Block()
            block.id = tool_call.id
            block.name = block_name
            block.input = block_input

            print(f"\033[36m> {block.name}\033[0m")

            if should_run_background(block.name, block.input):
                bg_id = start_background_task(block)
                results.append({"role": "tool",
                                "tool_call_id": block.id,
                                "name": block.name,
                                "content": f"[Background task {bg_id} started] "
                                           f"Result will be available when complete."})
            else:
                output = execute_tool(block, tools)
                print(str(output)[:300])
                results.append({"role": "tool",
                                "tool_call_id": block.id,
                                "name": block.name,
                                "content": str(output)})

        for res in results:
            messages.append(res)

        # Merge background tool results + notifications into one user message
        bg_notifications = collect_background_results()
        if bg_notifications:
            user_content = "\n".join(bg_notifications)
            messages.append({"role": "user", "content": user_content})
            
        context = update_context(context, messages)
        system = get_system_prompt(context, role_name)


if __name__ == "__main__":
    print("s16: Team Protocols — 队友之间要有约定 (中文版)")
    print("试着输入：'请召唤一个名为 alice 的后端开发队友，让她创建一个 schema.sql 文件，等她完成后走正规流程让她关机 (request_shutdown)。'\n")
    history = []
    context = update_context({}, [])
    while True:
        try:
            query = input("\033[36ms16 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        
        # 简化版主循环，不再使用 run_agent_turn_locked
        agent_loop(history, context, TOOLS, "lead")
        context = update_context(context, history)
        
        # 打印最后一次回答
        msg = history[-1]
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            content = msg.get("content", "")
            if isinstance(content, str):
                pass
            else:
                for block in content:
                    if getattr(block, "type", None) == "text":
                        print(block.text)
                    elif isinstance(block, dict) and block.get("type") == "text":
                        print(block.get("text", ""))

        # Check inbox → route protocol + inject into history
        inbox_msgs = consume_lead_inbox()
        if inbox_msgs:
            inbox_text = "\n".join(
                f"From {m['from']}: {m['content'][:200]}" for m in inbox_msgs)
            history.append({"role": "user",
                            "content": f"[Inbox]\n{inbox_text}"})
            print(f"\n\033[33m[Inbox] 老大收到 {len(inbox_msgs)} 条新消息\033[0m")

        # 播报所有小弟已经完成
        active = []
        with team_lock:
            active = list(active_teammates.keys())
        if not active:
            print("  \033[35m[Team] 所有队友均已完成工作并退场\033[0m")
            
        print()
