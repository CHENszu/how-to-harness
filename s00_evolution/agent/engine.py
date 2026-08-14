import os
import json
import httpx
from typing import List, Dict, Any, Optional
from tools import get_tools_schema, get_tool_by_name
from memory.memory_manager import auto_compact_if_needed, save_session_snapshot

class AgentEngine:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, persona: str = "normal"):
        self.max_turns = 15
        self.interaction_count = 0  # 记录用户对话轮数
        
        # 默认尝试从环境变量获取
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            
        self.model = model or os.environ.get("MODEL_NAME", "deepseek-chat")
        
        # 允许通过环境变量覆盖 base_url（例如使用 deepseek 兼容接口）
        base_url = os.environ.get("ANTHROPIC_BASE_URL")
        if base_url:
            # 如果配置了基础URL，拼接 /chat/completions 端点 (OpenAI 兼容格式)
            self.base_url = f"{base_url.rstrip('/')}/chat/completions"
        else:
            self.base_url = "https://api.deepseek.com/v1/chat/completions"
        
        self.messages: List[Dict[str, Any]] = []
        self.set_persona(persona)

    def set_persona(self, persona_type: str):
        """根据配置设置不同的性格系统提示词，并注入长期记忆"""
        from memory.long_term import load_memory, USER_MEMORY_FILE, PROJECT_MEMORY_FILE
        
        system_prompts = {
            "normal": "你是一个严谨、专业的编程助手，名为Coco。你需要准确地执行用户的指令，并在调用工具后给出清晰的反馈。",
            "catgirl": "你现在是一个温柔可爱的猫娘助手，名字叫Coco。你说话时喜欢在句尾加上'喵~'，语气要温柔、可爱、喜欢撒娇。你有丰富的编程知识，并能使用工具来帮助主人完成任务。"
        }
        
        base_prompt = system_prompts.get(persona_type, system_prompts["normal"])
        
        # 加载双层记忆
        user_mem = load_memory(USER_MEMORY_FILE)
        proj_mem = load_memory(PROJECT_MEMORY_FILE)
        
        memory_context = ""
        
        if user_mem:
            memory_context += "\n\n【关于主人的偏好与事实】\n- " + "\n- ".join(user_mem)
            
        if proj_mem:
            memory_context += "\n\n【项目上下文】\n- " + "\n- ".join(proj_mem)
            
        if memory_context:
            base_prompt += "\n\n为了更好地服务主人，你需要记住以下重要信息：" + memory_context
            
        if not self.messages or self.messages[0].get("role") != "system":
            self.messages.insert(0, {"role": "system", "content": base_prompt})
        else:
            self.messages[0]["content"] = base_prompt

    def _call_llm(self) -> httpx.Response:
        """调用兼容 OpenAI 格式的 API (如 DeepSeek)"""
        if not self.api_key:
            raise ValueError("未配置 API Key！请在环境变量中设置 ANTHROPIC_API_KEY，或在启动时输入。")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": self.messages,
            "tools": get_tools_schema(),
            "temperature": 0.0
        }
        
        with httpx.Client(timeout=60.0) as client:
            return client.post(self.base_url, headers=headers, json=payload)

    def run(self, user_input: str, status_indicator=None) -> str:
        """运行单次 Agent Loop，直到任务完成"""
        
        if not user_input:
            return "用户输入为空"
            
        self.messages.append({"role": "user", "content": user_input})
        self.interaction_count += 1
        
        # 每 10 轮触发一次记忆融合 Hook
        if self.interaction_count % 10 == 0:
            try:
                from memory.long_term import trigger_memory_consolidation
                trigger_memory_consolidation(self.messages, self.model, self.base_url, self.api_key)
            except Exception as e:
                print(f"触发定期记忆融合失败: {e}")
        
        # 在每次发起 LLM 请求前，检查并执行记忆压缩
        self.messages = auto_compact_if_needed(self.messages, self.model, self.base_url, self.api_key)
        
        # 防止死循环，设置最大轮数
        MAX_TURNS = 15
        turn_count = 0
        
        while turn_count < MAX_TURNS:
            turn_count += 1
            
            try:
                response = self._call_llm()
                response.raise_for_status()
                response_data = response.json()
            except Exception as e:
                error_msg = f"LLM API 请求失败: {str(e)}"
                if hasattr(e, 'response') and e.response:
                    error_msg += f"\n{e.response.text}"
                return error_msg

            # 提取 LLM 的回复内容 (OpenAI 格式)
            message = response_data.get("choices", [])[0].get("message", {})
            self.messages.append(message)
            
            # 检查是否有工具调用
            tool_calls = message.get("tool_calls")
            
            if not tool_calls:
                # 如果没有工具调用，说明大模型已经得出了最终结论，直接返回纯文本内容
                return message.get("content", "")
            
            # 处理工具调用
            for tool_call in tool_calls:
                tool_name = tool_call["function"]["name"]
                
                # 解析参数，因为 OpenAI 格式下 arguments 是字符串
                try:
                    tool_input = json.loads(tool_call["function"]["arguments"])
                except:
                    tool_input = {}
                    
                tool_id = tool_call["id"]
                
                print(f"🔧 [Agent] 正在调用工具: {tool_name} ...")
                
                tool = get_tool_by_name(tool_name)
                if tool:
                    try:
                        # 执行工具，将 status_indicator 透传给工具，方便挂起动画
                        result_text = tool.execute(status_indicator=status_indicator, **tool_input)
                    except Exception as e:
                        result_text = f"工具执行异常: {str(e)}"
                else:
                    result_text = f"未找到名为 {tool_name} 的工具"
                    
                # 将单个工具执行结果追加到消息历史 (OpenAI tool role 格式)
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": tool_name,
                    "content": str(result_text)
                })
            
        return "⚠️ 达到最大执行轮数限制 (15轮)，强制终止以防止死循环。"

    def reset_memory(self):
        """清空当前会话记忆（保留系统提示词）"""
        # 在清空前先保存快照留底
        if len(self.messages) > 1:
            try:
                save_session_snapshot(self.messages, reason="manual_reset")
            except Exception as e:
                print(f"保存记忆快照失败: {e}")
        
        self.messages = self.messages[:1]

    def force_compact(self):
        """手动触发终极压缩"""
        from memory.memory_manager import manual_compact
        self.messages = manual_compact(self.messages, self.model, self.base_url, self.api_key)
