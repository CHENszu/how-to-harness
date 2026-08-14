import tiktoken
import json
from typing import List, Dict, Any

# 安全估算系数 (OpenHarness/Claude Code 官方设定)
TOKEN_ESTIMATION_PADDING = 4 / 3 

def get_tokenizer():
    # 默认使用 cl100k_base (GPT-4 / Claude 常用分词器的近似)
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None

_tokenizer = get_tokenizer()

def estimate_tokens(text: str) -> int:
    """估算单段文本的 Token 数量"""
    if not text:
        return 0
    if _tokenizer:
        return len(_tokenizer.encode(text))
    # 降级方案：粗略估计 (每 4 个字符约 1 个 token)
    return len(text) // 4

def estimate_message_tokens(messages: List[Dict[str, Any]]) -> int:
    """估算整个对话历史的 Token 总数 (包含 Padding)"""
    total = 0
    for msg in messages:
        # 计算角色和内容的 token
        total += estimate_tokens(msg.get("role", ""))
        content = msg.get("content", "")
        
        # 处理 OpenAI 格式的复杂 content (可能是字符串，也可能是 list)
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    total += estimate_tokens(block["text"])
        
        # 如果是 Assistant 调用的工具
        if "tool_calls" in msg:
            for tool_call in msg["tool_calls"]:
                total += estimate_tokens(tool_call.get("function", {}).get("name", ""))
                total += estimate_tokens(tool_call.get("function", {}).get("arguments", ""))
        
        # 如果是工具返回的结果 (role: tool)
        if msg.get("role") == "tool":
            total += estimate_tokens(str(msg.get("name", "")))
            total += estimate_tokens(str(msg.get("content", "")))
            
    # 乘以安全系数，确保宁多勿少
    return int(total * TOKEN_ESTIMATION_PADDING)

def get_autocompact_threshold(model: str) -> int:
    """获取触发自动压缩的阈值"""
    # 默认模型上下文窗口
    context_window = 128_000 
    
    if "claude-3-5" in model.lower() or "opus" in model.lower() or "sonnet" in model.lower():
        context_window = 200_000
    
    # 预留给 Summary 输出的空间
    reserved_for_summary = 20_000
    # 预留的安全缓冲空间
    buffer_tokens = 13_000
    
    threshold = context_window - reserved_for_summary - buffer_tokens
    # 兜底保护，至少为 10000
    return max(threshold, 10_000)
