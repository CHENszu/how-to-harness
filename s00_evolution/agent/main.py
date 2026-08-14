import sys
import os
from dotenv import load_dotenv
from engine import AgentEngine

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown

console = Console()

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
    welcome_text.append(": 抓取网页文本\n\n")
    
    welcome_text.append("输入 ", style="dim")
    welcome_text.append("'exit'", style="bold red")
    welcome_text.append(" 或 ", style="dim")
    welcome_text.append("'quit'", style="bold red")
    welcome_text.append(" 退出。", style="dim")

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
    
    while True:
        try:
            user_input = console.input("\n[bold green]❯ You:[/bold green] ")
            if not user_input.strip():
                continue
                
            if user_input.lower() in ['exit', 'quit']:
                console.print("👋 [bold blue]再见！[/bold blue]")
                break
                
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