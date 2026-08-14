import os
import json
import httpx
from typing import List, Dict, Any, Optional
from tools import get_tools_schema, get_tool_by_name

class AgentEngine:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
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
        
        self.system_prompt = (
            "You are a helpful AI assistant. You have access to tools to help the user. "
            "When asked to perform tasks, use the appropriate tools. "
            "You are running on a Windows machine."
        )
        
        # 消息历史，初始化时放入 system prompt
        self.messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt}
        ]

    def set_persona(self, persona_type: str):
        """切换系统提示词（性格）"""
        if persona_type == "catgirl":
            self.system_prompt = (
                "你现在是一个温柔可爱的猫娘助手，名字叫Coco。你说话时喜欢在句尾加上'喵~'，"
                "语气要温柔、可爱、喜欢撒娇。你有丰富的编程知识，并能使用工具来帮助主人完成任务。"
                "You are running on a Windows machine."
            )
        else:
            self.system_prompt = (
                "You are a helpful AI assistant. You have access to tools to help the user. "
                "When asked to perform tasks, use the appropriate tools. "
                "You are running on a Windows machine."
            )
        # 更新当前消息历史中的 system prompt
        if self.messages and self.messages[0].get("role") == "system":
            self.messages[0]["content"] = self.system_prompt
        else:
            self.messages.insert(0, {"role": "system", "content": self.system_prompt})

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
        
        self.messages.append({"role": "user", "content": user_input})
        
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
