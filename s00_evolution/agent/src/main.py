import sys
import os
import logging
from dotenv import load_dotenv
from engine import AgentEngine
from tools import AVAILABLE_TOOLS
from config_manager import load_config, save_config

logger = logging.getLogger(__name__)

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
            '/compact': '手动将当前长对话压缩成摘要 (Full Compact)',
            '/tools': '显示当前已挂载的工具列表及说明',
            '/config': '查看当前运行配置 (模型、接口等)',
            '/persona': '切换助手性格 (正常/猫娘)'
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
    
    # 加载持久化配置
    config_data = load_config()
    
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
        engine = AgentEngine(
            model=config_data.get("model"), 
            persona=config_data.get("persona", "normal")
        )
        
    # 初始化交互式输入 Session
    session = PromptSession(completer=SlashCommandCompleter(), style=prompt_style)
    
    while True:
        try:
            user_input = session.prompt("\n❯ You: ", style=prompt_style)
            if not user_input.strip():
                continue
                
            if user_input.lower() in ['exit', 'quit', '/exit', '/quit']:
                console.print("👋 [bold blue]再见！[/bold blue]")
                
                # 退出前保存快照并提取长期记忆
                if len(engine.messages) > 1:
                    try:
                        from memory.memory_manager import save_session_snapshot
                        from memory.long_term import trigger_memory_consolidation
                        save_session_snapshot(engine.messages, reason="exit")
                        trigger_memory_consolidation(engine.messages, engine.model, engine.base_url, engine.api_key)
                    except Exception as e:
                        logger.error(f"保存记忆快照或提取长期记忆失败: {e}")
                        
                break
                
            # 处理斜杠命令
            if user_input.startswith("/"):
                cmd = user_input.strip().lower()
                if cmd == "/new":
                    # 重置 Agent 引擎的消息历史
                    engine.messages = [{"role": "system", "content": engine.system_prompt}]
                    console.print("✨ [bold green]记忆已清空，开启全新对话。[/bold green]")
                    continue
                
                elif cmd == "/compact":
                    with console.status("[bold yellow]正在启动后台摘要模型进行 Full Compact...[/bold yellow]", spinner="dots"):
                        engine.force_compact()
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
                    table.add_row("Persona", "猫娘 (catgirl)" if config_data.get("persona") == "catgirl" else "正常 (normal)")
                    
                    console.print(table)
                    continue
                
                elif cmd == "/persona":
                    from rich.prompt import Prompt
                    console.print("\n[bold cyan]请选择 Coco 的性格:[/bold cyan]")
                    console.print("1. 正常 (专业助手)")
                    console.print("2. 猫娘 (温柔可爱)")
                    
                    current_choice = "2" if config_data.get("persona") == "catgirl" else "1"
                    choice = Prompt.ask("输入序号", choices=["1", "2"], default=current_choice)
                    
                    if choice == "1":
                        engine.set_persona("normal")
                        config_data["persona"] = "normal"
                        console.print("✨ [bold green]已切换为【正常】性格。[/bold green]")
                    elif choice == "2":
                        engine.set_persona("catgirl")
                        config_data["persona"] = "catgirl"
                        console.print("✨ [bold magenta]已切换为【温柔猫娘】性格喵~[/bold magenta]")
                        
                    save_config(config_data)
                    continue
                
                else:
                    console.print(f"⚠️ [yellow]未知的命令: {cmd}。目前支持: /new, /tools, /config, /persona[/yellow]")
                    continue
                
            # 将 status 对象传递给 engine，以便内部工具调用时可以挂起/恢复
            with console.status("[bold purple]🤔 Coco 正在思考及执行任务...[/bold purple]", spinner="dots") as status_indicator:
                # 调用 Agent Loop
                response = engine.run(user_input, status_indicator=status_indicator)
            
            console.print("\n[bold purple]🤖 Coco:[/bold purple]")
            console.print(Markdown(response))
            console.print("-" * 50, style="dim")
            
        except (KeyboardInterrupt, EOFError):
            console.print("\n👋 [bold blue]再见！[/bold blue]")
            # 退出前保存快照并提取长期记忆
            if len(engine.messages) > 1:
                try:
                    from memory.memory_manager import save_session_snapshot
                    from memory.long_term import trigger_memory_consolidation
                    save_session_snapshot(engine.messages, reason="interrupt")
                    trigger_memory_consolidation(engine.messages, engine.model, engine.base_url, engine.api_key)
                except Exception as e:
                    logger.error(f"保存记忆快照或提取长期记忆失败: {e}")
            break
        except Exception as e:
            console.print(f"\n❌ [bold red]发生未捕获的错误: {e}[/bold red]")
            sys.exit(1)

if __name__ == "__main__":
    main()