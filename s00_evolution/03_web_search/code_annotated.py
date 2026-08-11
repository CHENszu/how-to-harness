import os
import json
import re
import html
import urllib.parse
from pydantic import BaseModel, Field
from typing import Type, Dict, List
from openai import OpenAI
from dotenv import load_dotenv

# 为了保持脚本的独立性和易运行性，这里使用了 requests 同步库代替 httpx 异步库，原理完全一致。
import requests

# ==========================================
# 第3部分：WebSearchTool 联网搜索工具
# ==========================================

# 1. 基础工具抽象 (复用之前模块的概念)
class BaseTool:
    name: str = ""
    description: str = ""
    input_model: Type[BaseModel] = None
    
    def to_api_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema()
            }
        }
        
    def execute(self, **kwargs) -> str:
        raise NotImplementedError


# 2. Pydantic 参数校验模型
class WebSearchToolInput(BaseModel):
    query: str = Field(description="需要搜索的关键词或问题")
    max_results: int = Field(default=5, ge=1, le=10, description="最大返回的结果数量")


# 3. WebSearchTool 核心实现
class WebSearchTool(BaseTool):
    name = "web_search"
    description = "使用 DuckDuckGo 搜索引擎在互联网上查找信息。返回包含标题、链接和摘要的结果。"
    input_model = WebSearchToolInput
    
    def _clean_html(self, text: str) -> str:
        """简单的 HTML 标签清理工具"""
        text = re.sub(r'<[^>]+>', '', text)
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def execute(self, **kwargs) -> str:
        # 1. 校验参数
        args = self.input_model(**kwargs)
        query = args.query
        max_results = args.max_results
        
        print(f"  [WebSearch] 正在互联网搜索: `{query}` ...")
        
        # 2. 构造 DuckDuckGo HTML 搜索请求
        # 为什么用 html 版？因为它不需要复杂的 API Key，也不需要渲染 JS。
        url = "https://html.duckduckgo.com/html/"
        headers = {
            # 伪装成浏览器，防止被直接拦截
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        data = {"q": query}
        
        try:
            # 3. 发送网络请求
            response = requests.post(url, headers=headers, data=data, timeout=10)
            response.raise_for_status()
            html_content = response.text
            
            # 4. 使用正则解析结果 (OpenHarness 的巧妙之处，不依赖 bs4)
            results = []
            
            # 匹配 DuckDuckGo 的结果卡片
            snippet_pattern = re.compile(r'class="result__snippet[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
            title_pattern = re.compile(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
            
            snippets = snippet_pattern.findall(html_content)
            title_matches = title_pattern.findall(html_content)
            
            for i, match in enumerate(title_matches):
                if i >= max_results:
                    break
                    
                raw_url, raw_title = match
                
                # 清洗标题
                title = self._clean_html(raw_title)
                
                # 处理 DuckDuckGo 的跳转链接，提取真实 URL
                actual_url = raw_url
                if "uddg=" in raw_url:
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                    if "uddg" in parsed:
                        actual_url = parsed["uddg"][0]
                
                # 匹配对应的摘要片段
                snippet = self._clean_html(snippets[i]) if i < len(snippets) else "无摘要"
                
                results.append(f"标题: {title}\n链接: {actual_url}\n摘要: {snippet}\n---")
                
            if not results:
                return "未找到相关结果。可能是网络请求被拦截，或者关键词太生僻。"
                
            return "\n".join(results)
            
        except Exception as e:
            return f"搜索请求失败: {str(e)}"


# 4. 简易注册中心
class ToolRegistry:
    def __init__(self):
        self._tools = {}
    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool
    def get_tool(self, name: str) -> BaseTool:
        return self._tools.get(name)
    def to_api_tools(self) -> List[dict]:
        return [t.to_api_schema() for t in self._tools.values()]


# ==========================================
# 集成到 Agent Loop
# ==========================================
def agent_loop_with_web(user_input: str):
    print(f"\n[用户]: {user_input}")
    
    # 1. 加载环境变量
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            load_dotenv(stream=f)
            
    client = OpenAI(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.deepseek.com/v1")
    )
    
    # 2. 注册 WebSearch 工具
    registry = ToolRegistry()
    registry.register(WebSearchTool())
    
    messages = [
        {"role": "system", "content": "你是一个有用的AI助手。遇到你不确定的实时信息或知识时，请主动调用 web_search 工具在互联网上搜索。请根据搜索到的结果来回答用户。"},
        {"role": "user", "content": user_input}
    ]

    tools = registry.to_api_tools()

    turn = 1
    while True:
        print(f"\n--- 🔄 第 {turn} 轮思考开始 ---")
        print("  [Agent] 正在思考...")
        
        response = client.chat.completions.create(
            model=os.getenv("MODEL_ID", "deepseek-chat"),
            messages=messages,
            tools=tools,
            temperature=0.0
        )
        
        message = response.choices[0].message
        messages.append(message) 

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
                    
                print(f"  [Agent] 观察到结果 👀:\n{result}")
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": func_name,
                    "content": str(result)
                })
            
            turn += 1
            continue 
        else:
            print(f"\n[Agent 最终回复 🎯]: {message.content}")
            break

if __name__ == "__main__":
    print("=======================================")
    print("  🌐 欢迎来到 Web Search 测试 🌐")
    print("=======================================")
    print("你可以尝试提问实时问题，例如：")
    print(" 1. 请查一下2024年巴黎奥运会中国队获得了多少金牌？")
    print(" 2. Python 3.12 是什么时候发布的？")
    
    while True:
        try:
            user_msg = input("\n请输入你的问题 (输入 q 退出): ")
            if user_msg.lower() == 'q':
                break
            if not user_msg.strip():
                continue
                
            agent_loop_with_web(user_msg)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n[发生错误]: {e}")
