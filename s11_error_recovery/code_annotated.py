#!/usr/bin/env python3
"""
s11_code_annotated.py - Error Recovery (中文注释版)

核心思想：给大模型调用套上“复活甲”。
在生产环境中，API 随时会因为限流(429)、过载(529)、上下文超限(prompt_too_long)或回答过长(max_tokens)而报错中断。
我们需要在主循环中捕捉这些错误，并执行对应的恢复策略（升级Token、压缩上下文、指数退避重试），而不是直接让程序崩溃。
"""

import os, subprocess, time, random, json
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
PRIMARY_MODEL = os.environ["MODEL_ID"]
# 备用模型，如果主模型过载，会尝试切到这个
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL_ID")

WORKDIR = Path.cwd()
MEMORY_DIR = WORKDIR / ".memory"
MEMORY_INDEX = MEMORY_DIR / "MEMORY.md"

# ═══════════════════════════════════════════════════════════
#  NEW in s11: 错误恢复相关的常量定义
# ═══════════════════════════════════════════════════════════

# 为了方便测试“输出截断”，这里将默认的最大 token 调得很小 (例如 500)
# 正常生产环境 DEFAULT 可以是 8000，ESCALATED 可以是 64000
DEFAULT_MAX_TOKENS = 500
ESCALATED_MAX_TOKENS = 8000

MAX_RECOVERY_RETRIES = 3    # 截断后最多允许模型“续写”几次
MAX_RETRIES = 10            # 遇到 429/529 等网络错误时，最多重试几次
BASE_DELAY_MS = 500         # 指数退避的基础等待时间（毫秒）
MAX_CONSECUTIVE_529 = 3     # 连续遇到几次 529 过载错误后，切换到备用模型

# 让模型接着往下说的系统指令（直接接续，不要寒暄）
CONTINUATION_PROMPT = (
    "Output token limit hit. Resume directly — "
    "no apology, no recap. Pick up mid-thought."
)

class RecoveryState:
    """用来在一次 agent_loop 中追踪当前的错误恢复状态"""
    def __init__(self):
        self.has_escalated = False               # 是否已经升级过 max_tokens
        self.recovery_count = 0                  # 当前已经续写了几次
        self.consecutive_529 = 0                 # 连续过载的次数
        self.has_attempted_reactive_compact = False # 是否已经尝试过紧急上下文压缩
        self.current_model = PRIMARY_MODEL       # 当前正在使用的模型


# ═══════════════════════════════════════════════════════════
#  NEW in s11: 恢复策略的具体实现
# ═══════════════════════════════════════════════════════════

def retry_delay(attempt: int) -> float:
    """计算指数退避的等待时间，并加入随机抖动 (Jitter)"""
    # 公式：500ms * (2^尝试次数)，最大不超过 32秒
    base = min(BASE_DELAY_MS * (2 ** attempt), 32000) / 1000
    # 加入 0 ~ 25% 的随机抖动，防止并发请求形成“雷暴”
    jitter = random.uniform(0, base * 0.25)
    return base + jitter

def with_retry(fn, state: RecoveryState):
    """
    包装器：专门处理网络层面的瞬态错误 (429 限流 / 529 过载)。
    对于其他不可恢复的错误（比如 API Key 填错），直接抛出给外层处理。
    """
    for attempt in range(MAX_RETRIES):
        try:
            result = fn()
            state.consecutive_529 = 0  # 成功调用，重置过载计数器
            return result
        except Exception as e:
            name = type(e).__name__
            msg = str(e).lower()

            # 匹配 429 限流错误
            if "ratelimit" in name.lower() or "429" in msg:
                delay = retry_delay(attempt)
                print(f"  \033[33m[429 Rate Limit] 触发限流，准备重试 {attempt+1}/{MAX_RETRIES}，等待 {delay:.1f}秒\033[0m")
                time.sleep(delay)
                continue

            # 匹配 529 过载错误
            if "overloaded" in name.lower() or "529" in msg or "timeout" in msg:
                state.consecutive_529 += 1
                # 如果连续过载且配置了备用模型，尝试降级
                if state.consecutive_529 >= MAX_CONSECUTIVE_529:
                    if FALLBACK_MODEL:
                        state.current_model = FALLBACK_MODEL
                        state.consecutive_529 = 0
                        print(f"  \033[31m[529 Overload x{MAX_CONSECUTIVE_529}] 连续过载，正在将模型切换为备用模型：{FALLBACK_MODEL}\033[0m")
                    else:
                        state.consecutive_529 = 0
                        print(f"  \033[31m[529 Overload x{MAX_CONSECUTIVE_529}] 无备用模型，继续死磕重试\033[0m")
                
                delay = retry_delay(attempt)
                print(f"  \033[33m[529/Timeout] 服务器过载，准备重试 {attempt+1}/{MAX_RETRIES}，等待 {delay:.1f}秒\033[0m")
                time.sleep(delay)
                continue

            # 不是这两种错误，把异常抛给外层
            raise
            
    raise RuntimeError(f"已达到最大重试次数 ({MAX_RETRIES})，无法恢复。")

def is_prompt_too_long_error(e: Exception) -> bool:
    """判断是不是上下文太长导致的错误"""
    msg = str(e).lower()
    return (("prompt" in msg and "long" in msg)
            or "prompt_is_too_long" in msg
            or "context_length_exceeded" in msg
            or "max_context_window" in msg)

def reactive_compact(messages: list) -> list:
    """
    被动防御：紧急上下文压缩。
    当 API 真的抱怨太长了，我们强行把前面的对话全部丢掉，只保留最后 5 条。
    """
    print("  \033[31m[Reactive Compact] 触发紧急压缩：裁剪掉早期的上下文，仅保留最近 5 条\033[0m")
    tail = messages[-5:]
    return [{"role": "user", "content": "[Reactive compact] Earlier conversation trimmed. Continue from where you left off."}, *tail]


# ═══════════════════════════════════════════════════════════
#  FROM s10: Prompt 组装与基础工具
# ═══════════════════════════════════════════════════════════

PROMPT_SECTIONS = {
    "identity": "You are a coding agent. Act, don't explain. Solve tasks directly.",
}

def assemble_system_prompt(context: dict) -> str:
    sections = [PROMPT_SECTIONS["identity"]]
    tools = ", ".join(context.get("enabled_tools", []))
    if tools: sections.append(f"Available tools: {tools}.")
    sections.append(f"Working directory: {context.get('workspace', WORKDIR)}")
    memories = context.get("memories", "")
    if memories: sections.append(f"Relevant memories:\n{memories}")
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
        file_path.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e: return f"Error: {e}"

TOOLS = [
    {"type": "function", "function": {"name": "bash", "description": "Run a shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read file contents.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Write content to a file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
]
TOOL_HANDLERS = {"bash": run_bash, "read_file": run_read, "write_file": run_write}

def update_context(context: dict, messages: list) -> dict:
    memories = ""
    if MEMORY_INDEX.exists():
        content = MEMORY_INDEX.read_text(encoding="utf-8").strip()
        if content: memories = content
    return {"enabled_tools": list(TOOL_HANDLERS.keys()), "workspace": str(WORKDIR), "memories": memories}


# ═══════════════════════════════════════════════════════════
#  Agent Loop - 加入外层错误恢复
# ═══════════════════════════════════════════════════════════

def agent_loop(messages: list, context: dict):
    system = get_system_prompt(context)
    state = RecoveryState()
    max_tokens = DEFAULT_MAX_TOKENS

    while True:
        formatted_messages = [{"role": "system", "content": system}] + messages
        
        # 1. 尝试调用 API，内层通过 with_retry 挡住了 429 和 529
        try:
            response = with_retry(
                lambda: client.chat.completions.create(
                    model=state.current_model, 
                    messages=formatted_messages,
                    tools=TOOLS, 
                    max_tokens=max_tokens
                ),
                state
            )
        except Exception as e:
            # 2. 如果抛出的错是 prompt_too_long，走紧急压缩逻辑
            if is_prompt_too_long_error(e):
                if not state.has_attempted_reactive_compact:
                    messages[:] = reactive_compact(messages)
                    state.has_attempted_reactive_compact = True
                    continue  # 压缩完，重试！
                
                print("  \033[31m[Unrecoverable] 压缩后依然超出上下文限制，无法继续\033[0m")
                messages.append({"role": "assistant", "content": "[Error] Context too large, cannot continue."})
                return

            # 其他没见过的严重错误，打印日志并直接退出
            name = type(e).__name__
            print(f"  \033[31m[Unrecoverable] 发生严重错误 {name}: {str(e)[:100]}\033[0m")
            messages.append({"role": "assistant", "content": f"[Error] {name}: {str(e)[:200]}"})
            return

        response_message = response.choices[0].message

        # 3. 处理输出被截断的情况 (length)
        if response.choices[0].finish_reason == "length":
            # 第一次截断：不保存残缺结果，直接把 Token 上限放大然后重试一模一样的请求
            if not state.has_escalated:
                max_tokens = ESCALATED_MAX_TOKENS
                state.has_escalated = True
                print(f"  \033[33m[max_tokens] 输出被截断，准备升级 Token 上限重试: {DEFAULT_MAX_TOKENS} -> {ESCALATED_MAX_TOKENS}\033[0m")
                continue
                
            # 第二次及以上截断（64K 也撑不住了）：保存残缺结果，强制让它接着刚才的话茬往下续写
            # 注意：由于截断可能包含不完整的 tool_calls，而 API 强制要求有 tool_calls 时必须紧跟 tool 结果，
            # 因此在续写时强制剔除未完成的 tool_calls，避免抛出 400 BadRequest 错误。
            messages.append({
                "role": "assistant",
                "content": response_message.content or "",
                "tool_calls": None
            })
            
            if state.recovery_count < MAX_RECOVERY_RETRIES:
                messages.append({"role": "user", "content": CONTINUATION_PROMPT})
                state.recovery_count += 1
                print(f"  \033[33m[max_tokens] Token 仍然不足，发起续写请求 {state.recovery_count}/{MAX_RECOVERY_RETRIES}\033[0m")
                continue
                
            print("  \033[31m[max_tokens] 达到最大续写次数限制，停止生成\033[0m")
            return

        # 正常生成完毕，将助手的话存入历史
        messages.append({
            "role": "assistant",
            "content": response_message.content or "",
            "tool_calls": [t.model_dump() for t in response_message.tool_calls] if response_message.tool_calls else None
        })

        if response.choices[0].finish_reason != "tool_calls":
            return

        # 执行工具
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                print(f"\033[36m> {tool_call.function.name}\033[0m")
                args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                handler = TOOL_HANDLERS.get(tool_call.function.name)
                output = handler(**args) if handler else f"Unknown: {tool_call.function.name}"
                print(str(output)[:200])
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": output})

        context = update_context(context, messages)
        system = get_system_prompt(context)


if __name__ == "__main__":
    print("s11: Error Recovery — 错误恢复与自动重试机制")
    print("输入问题，回车发送。输入 q 退出。\n")
    
    history = []
    context = update_context({}, [])
    
    while True:
        try:
            query = input("\033[36ms11 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
            
        turn_start = len(history)
        history.append({"role": "user", "content": query})
        
        agent_loop(history, context)
        context = update_context(context, history)
        
        # 打印助手在这个回合说的所有话
        for msg in history[turn_start:]:
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content", "")
            if content:
                print(content)
        print()
