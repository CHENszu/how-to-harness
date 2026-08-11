import os
import json
from openai import OpenAI
from tools import ToolRegistry
from memory import search_memory

# ==========================================
# 内存管理器 (MemoryManager) - 处理短期记忆 (复用 06 的逻辑)
# ==========================================
class MemoryManager:
    def __init__(self, max_chars=4000):
        self.max_chars = max_chars

    def estimate_chars(self, messages: list) -> int:
        return sum(len(str(m)) for m in messages)

    def _micro_compact(self, messages: list) -> tuple[list, int]:
        saved_chars = 0
        new_messages = []
        keep_recent = 6
        total = len(messages)
        
        for i, msg in enumerate(messages):
            if msg["role"] == "tool" and (total - i > keep_recent):
                content = str(msg.get("content", ""))
                if len(content) > 100:
                    saved_chars += len(content)
                    new_msg = msg.copy()
                    new_msg["content"] = "[已清理旧工具结果以节省空间]"
                    new_messages.append(new_msg)
                    continue
            new_messages.append(msg)
            
        return new_messages, saved_chars

    def _llm_compact(self, messages: list, client: OpenAI, model_id: str) -> list:
        print("  [Memory] 📝 正在调用大模型生成短期记忆便签...")
        
        safe_split_idx = 0
        user_count = 0
        for i in range(len(messages)-1, -1, -1):
            if messages[i]["role"] == "user":
                user_count += 1
                if user_count == 3:
                    safe_split_idx = i
                    break
                    
        if safe_split_idx == 0:
            # 即使找不到足够的 user 轮次，如果消息数量很多，也必须切分
            # 强制保留最近的 6 条消息
            if len(messages) > 6:
                safe_split_idx = len(messages) - 6
            else:
                return messages
            
        older_messages = messages[:safe_split_idx]
        newer_messages = messages[safe_split_idx:]
        
        compact_prompt = (
            "请你对以上对话历史进行高度凝练的总结。\n"
            "你的总结需要包含：\n"
            "1. 用户的原始核心意图是什么？\n"
            "2. 我们已经尝试了哪些步骤？调用了什么工具？\n"
            "3. 发现了什么关键信息或遇到了什么错误？\n"
            "4. 下一步计划是什么？\n"
            "请直接输出总结，不要说废话。"
        )
        
        compact_req_messages = older_messages + [{"role": "user", "content": compact_prompt}]
        
        try:
            response = client.chat.completions.create(
                model=model_id,
                messages=compact_req_messages,
                temperature=0.0
            )
            summary = response.choices[0].message.content
            print("  [Memory] ✅ 便签生成完毕！")
            
            boundary_msg = {
                "role": "user",
                "content": f"[系统提示：之前的对话因太长已被压缩，以下是之前的对话总结]\n\n{summary}"
            }
            
            return [boundary_msg] + newer_messages
            
        except Exception as e:
            print(f"  [Memory] ❌ 生成便签失败: {e}")
            return messages

    def auto_compact(self, messages: list, client: OpenAI, model_id: str) -> list:
        current_chars = self.estimate_chars(messages)
        if current_chars < self.max_chars:
            return messages
            
        print(f"\n  [Memory] ⚠️ 警告：当前上下文 ({current_chars} 字符) 接近阈值 ({self.max_chars})！")
        
        messages, saved = self._micro_compact(messages)
        if saved > 0:
            print(f"  [Memory] 🗑️ 执行微压缩，清理了 {saved} 个字符的旧工具输出。")
            current_chars = self.estimate_chars(messages)
        
        if current_chars >= self.max_chars:
            print("  [Memory] ⚠️ 微压缩后依然过长，触发全量压缩！")
            messages = self._llm_compact(messages, client, model_id)
            
        print(f"  [Memory] 🟢 压缩完成，当前上下文长度: {self.estimate_chars(messages)} 字符。\n")
        return messages


# ==========================================
# 核心循环 (Agent Loop)
# ==========================================
def run_agent_loop(user_input: str, registry: ToolRegistry):
    print(f"\n[用户]: {user_input}")
    
    client = OpenAI(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.deepseek.com/v1")
    )
    model_id = os.getenv("MODEL_ID", "deepseek-chat")
    
    memory_manager = MemoryManager(max_chars=3000)
    
    # ----------------------------------------------------
    # 新增：在开始前检索长期记忆并注入 System Prompt
    # ----------------------------------------------------
    print("  [System] 🔍 正在检索长期记忆文件柜...")
    retrieved_memory = search_memory(user_input, top_k=2)
    
    memory_context = ""
    if retrieved_memory:
        print("  [System] 🧠 找到相关的长期记忆，已注入当前上下文！")
        memory_context = (
            "\n\n==========================================\n"
            "以下是检索到的相关【长期记忆】（知识库、偏好、经验）：\n"
            f"{retrieved_memory}\n"
            "请在回复和决策时严格参考上述记忆内容。\n"
            "==========================================\n"
        )
    else:
        print("  [System] 💨 未找到强相关的长期记忆。")
    # ----------------------------------------------------
    
    system_prompt = (
        "你是一个有用的AI助手。你可以使用工具。\n"
        "【环境警告】当前系统是 Windows PowerShell。执行 bash 命令时：\n"
        "1. 绝对禁止使用 `cat << EOF` 等 Heredoc 语法写文件！\n"
        "2. 绝对禁止使用 `python -c` 尝试在终端里执行多行代码！\n"
        "3. 如果你需要写代码或长文本，请务必调用专用的 `write_file` 工具来写文件，写完后再用 bash 执行。\n"
        "当用户明确要求你记住某条重要规则、个人偏好、或核心经验时，请**主动调用 `save_memory` 工具**将其持久化保存。\n"
        f"{memory_context}"
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]

    tools = registry.to_api_tools()

    turn = 1
    while True:
        messages = memory_manager.auto_compact(messages, client, model_id)
        
        print(f"\n--- 🔄 第 {turn} 轮思考开始 ---")
        print("  [Agent] 正在思考...")
        
        try:
            response = client.chat.completions.create(
                model=model_id,
                messages=messages,
                tools=tools,
                temperature=0.0
            )
            
            message = response.choices[0].message
            msg_dict = {"role": "assistant"}
            if message.content:
                msg_dict["content"] = message.content
            if message.tool_calls:
                msg_dict["tool_calls"] = [
                    {"id": t.id, "type": "function", "function": {"name": t.function.name, "arguments": t.function.arguments}}
                    for t in message.tool_calls
                ]
            messages.append(msg_dict)

            if message.tool_calls:
                for tool_call in message.tool_calls:
                    func_name = tool_call.function.name
                    args_str = tool_call.function.arguments
                    
                    print(f"  [Agent] 决定调用工具 🛠️: {func_name}({args_str})")
                    
                    target_tool = registry.get_tool(func_name)
                    if target_tool:
                        try:
                            args = json.loads(args_str)
                            result = target_tool.execute(**args)
                        except Exception as e:
                            result = f"执行失败: {e}"
                    else:
                        result = f"找不到工具 {func_name}"
                        
                    print_res = str(result)
                    if len(print_res) > 300:
                        print_res = print_res[:300] + "\n...[已截断显示]"
                    print(f"  [Agent] 观察到结果 👀:\n{print_res}")
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": str(result)
                    })
                
                turn += 1
                continue 
            else:
                print(f"\n[Agent 最终回复 🎯]:\n{message.content}")
                break
                
        except Exception as e:
            print(f"\n[循环发生错误]: {e}")
            break
