from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style

class SlashCommandCompleter(Completer):
    def __init__(self):
        self.commands = {
            '/new': '清空当前上下文记忆，开启全新对话',
            '/clear': '清空当前上下文记忆，开启全新对话 (同 /new)',
            '/tools': '显示当前已挂载的工具列表及说明',
            '/config': '查看当前运行配置 (模型、接口等)',
            '/exit': '退出 Coco (同 /quit)',
            '/quit': '退出 Coco (同 /exit)'
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

style = Style.from_dict({
    'prompt': 'ansigreen bold',
})

def main():
    session = PromptSession(completer=SlashCommandCompleter(), style=style)
    print("Type / to see auto-completions")
    try:
        user_input = session.prompt("\n❯ You: ")
        print(f"You entered: {user_input}")
    except (KeyboardInterrupt, EOFError):
        print("bye")

if __name__ == "__main__":
    main()