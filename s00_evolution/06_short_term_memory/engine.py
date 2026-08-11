import os
import json
from openai import OpenAI
from tools import ToolRegistry

# ==========================================
# 内存管理器 (MemoryManager) - 核心部分
# ==========================================
class MemoryManager:
    """
    负责监控上下文长度并在逼近阈值时触发：
    1. 微压缩 (Micro-compacting) - 扔掉草稿纸
    2. 全量压缩 (Full Compaction) - 写便签纸
    """
    def __init__(self, max_chars=4000):
        # 简单起见，我们用字符数代替真实的 Token 计算
        # 设得小一点 (4000字符)，方便测试时触发
        self.max_chars = max_chars

    def estimate_chars(self, messages: list) -> int:
        """估算当前消息列表的总字符数"""
        return sum(len(str(m)) for m in messages)

    def _micro_compact(self, messages: list) -> tuple[list, int]:
        """
        微压缩：扔掉旧草稿纸
        清理掉较早的、长篇大论的工具结果。
        """
        saved_chars = 0
        new_messages = []
        
        # 保留最近的 2 轮工具调用不被清理
        # 这里的 1 轮指的是一对 user/assistant/tool 消息
        # 简单实现：保留倒数 6 条消息内的工具结果
        keep_recent = 6
        total = len(messages)
        
        for i, msg in enumerate(messages):
            if msg["role"] == "tool" and (total - i > keep_recent):
                content = str(msg.get("content", ""))
                if len(content) > 100:
                    saved_chars += len(content)
                    # 替换为占位符
                    new_msg = msg.copy()
                    new_msg["content"] = "[已清理旧工具结果以节省空间]"
                    new_messages.append(new_msg)
                    continue
            new_messages.append(msg)
            
        return new_messages, saved_chars

    def _llm_compact(self, messages: list, client: OpenAI, model_id: str) -> list:
        """
        全量压缩：写便签纸
        如果微压缩不够，调用 LLM 对前半部分对话进行总结。
        """
        print("  [Memory] 📝 正在调用大模型生成全量记忆便签...")
        
        # 提取需要总结的“老消息”。为了防止破坏 OpenAI 的工具调用对 (tool_calls & tool)
        # 我们从后往前找，找到倒数第 2 个 user 消息的位置作为安全切割点
        safe_split_idx = 0
        user_count = 0
        for i in range(len(messages)-1, -1, -1):
            if messages[i]["role"] == "user":
                user_count += 1
                if user_count == 3:  # 保留最近的两个完整 user 轮次
                    safe_split_idx = i
                    break
                    
        if safe_split_idx == 0:
            # 如果找不到足够的轮次，就保守一点不压缩
            return messages
            
        older_messages = messages[:safe_split_idx]
        newer_messages = messages[safe_split_idx:]
        
        # 构造给 LLM 的总结提示词
        compact_prompt = (
            "请你对以上对话历史进行高度凝练的总结。\n"
            "你的总结需要包含：\n"
            "1. 用户的原始核心意图是什么？\n"
            "2. 我们已经尝试了哪些步骤？调用了什么工具？\n"
            "3. 发现了什么关键信息或遇到了什么错误？\n"
            "4. 下一步计划是什么？\n"
            "请直接输出总结，不要说废话。"
        )
        
        # 这里的总结请求不能带工具，防止幻觉
        compact_req_messages = older_messages + [{"role": "user", "content": compact_prompt}]
        
        try:
            response = client.chat.completions.create(
                model=model_id,
                messages=compact_req_messages,
                temperature=0.0
            )
            summary = response.choices[0].message.content
            print("  [Memory] ✅ 便签生成完毕！")
            
            # 构造新的系统提示（便签），替换掉原来的 older_messages
            boundary_msg = {
                "role": "user",
                "content": f"[系统提示：之前的对话因太长已被压缩，以下是之前的对话总结]\n\n{summary}"
            }
            
            return [boundary_msg] + newer_messages
            
        except Exception as e:
            print(f"  [Memory] ❌ 生成便签失败: {e}")
            return messages # 如果失败，原样返回

    def auto_compact(self, messages: list, client: OpenAI, model_id: str) -> list:
        """检查并执行压缩"""
        current_chars = self.estimate_chars(messages)
        
        if current_chars < self.max_chars:
            return messages
            
        print(f"\n  [Memory] ⚠️ 警告：当前上下文 ({current_chars} 字符) 接近阈值 ({self.max_chars})！")
        
        # 第一步：尝试微压缩（扔掉草稿）
        messages, saved = self._micro_compact(messages)
        if saved > 0:
            print(f"  [Memory] 🗑️ 执行微压缩，清理了 {saved} 个字符的旧工具输出。")
            current_chars = self.estimate_chars(messages)
        
        # 第二步：如果微压缩后依然超标，执行全量压缩（写便签）
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
    
    memory_manager = MemoryManager(max_chars=3000) # 设低点方便演示
    
    messages = [
        {
            "role": "system", 
            "content": "你是一个有用的AI助手。你可以使用工具。\n"
                       "【环境警告】当前系统是 Windows PowerShell。执行 bash 命令时：\n"
                       "1. 绝对禁止使用 `cat << EOF` 等 Heredoc 语法写文件！\n"
                       "2. 绝对禁止使用 `python -c` 尝试在终端里执行多行代码！\n"
                       "3. 如果你需要写代码或长文本，请务必调用专用的 `write_file` 工具来写文件，写完后再用 bash 执行。"
        },
        {"role": "user", "content": user_input}
    ]

    tools = registry.to_api_tools()

    turn = 1
    while True:
        # 在每次思考前，检查并自动压缩内存
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
            # 将模型的回复对象转为字典加入历史
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
