import sys
import os
from dotenv import load_dotenv
from engine import AgentEngine
from tools import AVAILABLE_TOOLS

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from rich.table import Table

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style

console = Console()

class SlashCommandCompleter(Completer):
    def __init__(self):
        self.commands = {
            '/new': '清空当前上下文记忆，开启全新对话',
            '/tools': '显示当前已挂载的工具列表及说明',
            '/config': '查看当前运行配置 (模型、接口等)'
        }

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith('/'):
            for cmd, desc in self.commands.items():
                if cmd.startswith(text):
                    yield Completion(
                        cmd,
                        start_position=-len(text),
                        display=cmd,
                        display_meta=desc
                    )

prompt_style = Style.from_dict({
    'prompt': 'ansigreen bold',
})

def print_welcome():
    welcome_text = Text()
    welcome_text.append("支持的功能：\n", style="bold")
    welcome_text.append("  • ", style="dim")
    welcome_text.append("bash", style="cyan")
    welcome_text.append(": 运行 PowerShell 指令\n")
    welcome_text.append("  • ", style="dim")
    welcome_text.append("web_search", style="cyan")
    welcome_text.append(": 网络搜索 (基于 DuckDuckGo)\n")
    welcome_text.append("  • ", style="dim")
    welcome_text.append("web_fetch", style="cyan")
    welcome_text.append(": 抓取网页文本\n")

    panel = Panel(
        welcome_text,
        title="🤖 [bold blue]Coco[/bold blue] (Agent Harness)",
        title_align="left",
        border_style="blue",
        padding=(1, 2)
    )
    console.print(panel)

def main():
    # 加载当前目录下的 .env 文件
    load_dotenv()
    
    print_welcome()
    
    # 检查并要求输入 API Key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        api_key = console.input("🔑 [yellow]未检测到 ANTHROPIC_API_KEY 环境变量。[/yellow]\n[bold]请输入您的 Anthropic API Key:[/bold] ").strip()
        if not api_key:
            console.print("❌ [red]未提供 API Key，程序退出。[/red]")
            sys.exit(1)
        # 将用户输入的 key 放入环境变量，供引擎读取
        os.environ["ANTHROPIC_API_KEY"] = api_key
    
    # 初始化引擎
    with console.status("[bold green]正在初始化 Coco 引擎...[/bold green]", spinner="dots"):
        engine = AgentEngine()
        
    # 初始化交互式输入 Session
    session = PromptSession(completer=SlashCommandCompleter(), style=prompt_style)
    
    while True:
        try:
            user_input = session.prompt("\n❯ You: ", style=prompt_style)
            if not user_input.strip():
                continue
                
            if user_input.lower() in ['exit', 'quit', '/exit', '/quit']:
                console.print("👋 [bold blue]再见！[/bold blue]")
                break
                
            # 处理斜杠命令
            if user_input.startswith("/"):
                cmd = user_input.strip().lower()
                if cmd == "/new":
                    # 重置 Agent 引擎的消息历史
                    engine.messages = [{"role": "system", "content": engine.system_prompt}]
                    console.print("✨ [bold green]记忆已清空，开启全新对话。[/bold green]")
                    continue
                
                elif cmd == "/tools":
                    # 显示可用工具列表
                    table = Table(title="🔧 已挂载的工具列表", show_header=True, header_style="bold magenta")
                    table.add_column("工具名称", style="cyan", width=20)
                    table.add_column("功能描述", style="white")
                    
                    for t in AVAILABLE_TOOLS:
                        table.add_row(t.name, t.description.strip().split('\n')[0]) # 只取第一行描述
                    
                    console.print(table)
                    continue
                
                elif cmd == "/config":
                    # 显示当前配置
                    table = Table(title="⚙️ 当前运行配置", show_header=True, header_style="bold magenta")
                    table.add_column("配置项", style="cyan")
                    table.add_column("当前值", style="yellow")
                    
                    table.add_row("Model", engine.model)
                    table.add_row("Base URL", engine.base_url)
                    
                    console.print(table)
                    continue
                
                else:
                    console.print(f"⚠️ [yellow]未知的命令: {cmd}。目前支持: /new, /tools, /config[/yellow]")
                    continue
                
            with console.status("[bold purple]🤔 Coco 正在思考及执行任务...[/bold purple]", spinner="dots"):
                # 调用 Agent Loop
                response = engine.run(user_input)
            
            console.print("\n[bold purple]🤖 Coco:[/bold purple]")
            console.print(Markdown(response))
            console.print("-" * 50, style="dim")
            
        except (KeyboardInterrupt, EOFError):
            console.print("\n👋 [bold blue]再见！[/bold blue]")
            break
        except Exception as e:
            console.print(f"\n❌ [bold red]发生未捕获的错误: {e}[/bold red]")
            sys.exit(1)

if __name__ == "__main__":
    main()