import re
import html
import subprocess
import urllib.parse
import requests
from pydantic import BaseModel, Field
from typing import Type, List, Dict

# ==========================================
# 基础工具抽象
# ==========================================
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

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        
    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool
        
    def get_tool(self, name: str) -> BaseTool:
        return self._tools.get(name)
        
    def to_api_tools(self) -> List[dict]:
        return [t.to_api_schema() for t in self._tools.values()]


# ==========================================
# 工具 1：联网搜索 (WebSearchTool)
# ==========================================
class WebSearchToolInput(BaseModel):
    query: str = Field(description="需要搜索的关键词或问题")
    max_results: int = Field(default=5, ge=1, le=10, description="最大返回的结果数量")

class WebSearchTool(BaseTool):
    name = "web_search"
    description = "使用 DuckDuckGo 搜索引擎在互联网上查找实时信息。返回包含标题、链接和摘要的结果。"
    input_model = WebSearchToolInput
    
    def _clean_html(self, text: str) -> str:
        text = re.sub(r'<[^>]+>', '', text)
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def execute(self, **kwargs) -> str:
        args = self.input_model(**kwargs)
        query = args.query
        max_results = args.max_results
        
        print(f"  [WebSearch] 正在互联网搜索: `{query}` ...")
        
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        data = {"q": query}
        
        try:
            response = requests.post(url, headers=headers, data=data, timeout=10)
            response.raise_for_status()
            html_content = response.text
            
            snippet_pattern = re.compile(r'class="result__snippet[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
            title_pattern = re.compile(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
            
            snippets = snippet_pattern.findall(html_content)
            title_matches = title_pattern.findall(html_content)
            
            results = []
            for i, match in enumerate(title_matches):
                if i >= max_results:
                    break
                    
                raw_url, raw_title = match
                title = self._clean_html(raw_title)
                
                actual_url = raw_url
                if "uddg=" in raw_url:
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                    if "uddg" in parsed:
                        actual_url = parsed["uddg"][0]
                
                snippet = self._clean_html(snippets[i]) if i < len(snippets) else "无摘要"
                results.append(f"标题: {title}\n链接: {actual_url}\n摘要: {snippet}\n---")
                
            if not results:
                return "未找到相关结果。"
                
            return "\n".join(results)
            
        except Exception as e:
            return f"搜索请求失败: {str(e)}"


# ==========================================
# 工具 2：Bash 执行 (BashTool)
# ==========================================
class BashToolInput(BaseModel):
    command: str = Field(description="需要在终端中执行的 bash/powershell 命令")

class BashTool(BaseTool):
    name = "bash"
    description = "在本地系统中执行终端命令，用于查看文件、运行脚本、安装依赖等。"
    input_model = BashToolInput
    
    def execute(self, **kwargs) -> str:
        args = self.input_model(**kwargs)
        command = args.command
        
        print(f"  [Bash] 正在执行: `{command}`")
        
        try:
            result = subprocess.run(
                command, shell=True, 
                capture_output=True, text=True, timeout=15
            )
            
            output = result.stdout if result.returncode == 0 else result.stderr
            if not output.strip():
                return "命令执行成功，但没有输出。"
            return output
            
        except subprocess.TimeoutExpired:
            return "命令执行超时 (15秒)。"
        except Exception as e:
            return f"命令执行出错: {str(e)}"


# ==========================================
# 工具 3：保存长期记忆 (SaveMemoryTool) - 新增！
# ==========================================
class SaveMemoryToolInput(BaseModel):
    title: str = Field(description="记忆的简短标题，如'代码规范'、'用户偏好'")
    content: str = Field(description="需要永久保存的具体知识、经验或约定")
    importance: int = Field(default=3, ge=1, le=5, description="重要程度 1(低) - 5(高)")

class SaveMemoryTool(BaseTool):
    name = "save_memory"
    description = "当用户要求你记住某些规则、偏好或关键知识时使用。将重要信息永久保存到本地文件柜，以便跨会话使用。"
    input_model = SaveMemoryToolInput
    
    def execute(self, **kwargs) -> str:
        args = self.input_model(**kwargs)
        
        print(f"  [SaveMemory] 📝 正在写文件柜: {args.title} (重要度:{args.importance})")
        
        # 动态导入，避免循环引用
        from memory import save_memory
        return save_memory(args.title, args.content, args.importance)

# ==========================================
# 工具 4：写文件 (WriteFileTool)
# ==========================================
class WriteFileToolInput(BaseModel):
    file_path: str = Field(description="要写入的文件路径（例如 test.py）")
    content: str = Field(description="要写入的具体文本或代码内容")

class WriteFileTool(BaseTool):
    name = "write_file"
    description = "将文本或代码直接写入到本地文件中。在编写长篇代码时，请务必优先使用此工具，而不是使用 bash。"
    input_model = WriteFileToolInput
    
    def execute(self, **kwargs) -> str:
        args = self.input_model(**kwargs)
        file_path = args.file_path
        content = args.content
        
        print(f"  [WriteFile] 正在写入文件: `{file_path}`")
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"成功将内容写入 {file_path}"
        except Exception as e:
            return f"写入文件出错: {str(e)}"
