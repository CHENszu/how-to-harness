import os
import json
from datetime import datetime
from typing import List, Dict, Any
from .token_estimation import estimate_message_tokens, get_autocompact_threshold

MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(MEMORY_DIR)
DATA_DIR = os.path.join(MEMORY_DIR, "data")
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def save_session_snapshot(messages: List[Dict[str, Any]], reason: str = "manual") -> str:
    """保存当前会话的快照到 sessions 目录"""
    if not os.path.exists(SESSIONS_DIR):
        os.makedirs(SESSIONS_DIR)
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"session_{timestamp}_{reason}.json"
    filepath = os.path.join(SESSIONS_DIR, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)
        
    return filepath

def auto_compact_if_needed(messages: List[Dict[str, Any]], model: str, base_url: str, api_key: str) -> List[Dict[str, Any]]:
    """检查是否超过阈值，如果超过则触发三级压缩策略"""
    threshold = get_autocompact_threshold(model)
    current_tokens = estimate_message_tokens(messages)
    
    if current_tokens <= threshold:
        return messages # 未超标，安全
        
    print(f"\n⚠️ [Memory] 触发自动记忆压缩! 当前 Tokens 估算: {current_tokens} > 阈值: {threshold}")
    
    # 压缩前先做个快照留底
    save_session_snapshot(messages, reason="pre_compact")
    
    # === 阶段 1: Microcompact (微压缩) ===
    messages = _microcompact(messages)
    new_tokens = estimate_message_tokens(messages)
    if new_tokens <= threshold:
        print(f"✅ [Memory] 阶段1微压缩成功，释放后 Tokens: {new_tokens}")
        return messages
        
    # === 阶段 3: Full Compact (LLM总结) ===
    # 跳过复杂的阶段2折叠，直接让大模型对除最近对话外的历史进行总结
    print(f"⚠️ [Memory] 微压缩后 Tokens({new_tokens}) 仍超标，启动 Full Compact 终极压缩...")
    return manual_compact(messages, model, base_url, api_key)

def manual_compact(messages: List[Dict[str, Any]], model: str, base_url: str, api_key: str) -> List[Dict[str, Any]]:
    """
    手动/终极压缩：使用大模型总结早期对话。
    保留 system prompt 和最近的 4 条消息，中间的所有消息总结成一条 user prompt。
    """
    if len(messages) <= 6:
        print("ℹ️ [Memory] 当前对话较短，无需压缩。")
        return messages
        
    system_prompt = messages[0] if messages[0].get("role") == "system" else None
    
    # 保留最近的 4 条消息 (大概是两轮对话)
    recent_messages = messages[-4:]
    
    # 需要被总结的早期消息
    old_messages = messages[1:-4] if system_prompt else messages[:-4]
    
    print(f"🔄 [Memory] 正在总结 {len(old_messages)} 条早期对话...")
    
    history_text = ""
    for msg in old_messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        # 如果是复杂的工具调用内容，这里粗略转为字符串
        if not isinstance(content, str):
            content = str(content)[:200] + "...(truncated)"
        history_text += f"[{role}]: {content}\n"
        
    summary_prompt = f"""
    请作为客观的摘要程序，将以下长篇对话历史压缩为一段简明扼要的摘要。
    
    要求：
    1. 必须保留所有已确认的决定、关键上下文和已执行的操作。
    2. 丢弃所有的寒暄、思考过程和重复的错误重试。
    3. 以“【历史摘要】”开头。
    
    【待总结的对话历史】：
    {history_text}
    """
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": summary_prompt}
        ],
        "temperature": 0.2
    }
    
    try:
        import httpx
        is_anthropic = "anthropic.com" in base_url
        
        if is_anthropic:
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            payload["max_tokens"] = 1024
        else:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "content-type": "application/json"
            }
        
        with httpx.Client(timeout=60.0) as client:
            response = client.post(base_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            if is_anthropic:
                summary = data["content"][0]["text"]
            else:
                summary = data["choices"][0]["message"]["content"]
            
            # 重新组装压缩后的 messages
            compacted_messages = []
            if system_prompt:
                compacted_messages.append(system_prompt)
                
            compacted_messages.append({"role": "user", "content": summary})
            compacted_messages.extend(recent_messages)
            
            # 保存压缩后的快照以便对比
            save_session_snapshot(compacted_messages, reason="post_compact")
            print("✅ [Memory] Full Compact 压缩完成！")
            return compacted_messages
            
    except Exception as e:
        print(f"❌ [Memory] Full Compact 总结失败，保留原消息: {e}")
        return messages

def _microcompact(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """微压缩：专门截断冗长的工具返回结果 (role: tool)"""
    # 考虑到我们用的是兼容格式，需要处理 tool_calls 的结果
    # 策略：如果工具返回的文本非常长（例如超过 3000 字符），则将其截断
    
    MAX_TOOL_RESULT_LENGTH = 3000
    compacted_messages = []
    
    for msg in messages:
        # 深拷贝以防修改原引用
        new_msg = dict(msg)
        if new_msg.get("role") == "tool" and isinstance(new_msg.get("content"), str):
            content = new_msg["content"]
            if len(content) > MAX_TOOL_RESULT_LENGTH:
                # 保留前 1500 和后 1500
                truncated = content[:1500] + f"\n\n... [中间 {len(content) - 3000} 个字符已在 Microcompact 阶段被系统自动丢弃以节省空间] ...\n\n" + content[-1500:]
                new_msg["content"] = truncated
        compacted_messages.append(new_msg)
        
    return compacted_messages
