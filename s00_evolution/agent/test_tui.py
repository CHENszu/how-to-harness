import time
import threading
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.application import get_app
from rich.console import Console

console = Console()

class AppState:
    def __init__(self):
        self.is_running = False
        self.status_text = ""

app_state = AppState()

class DummyStatus:
    def update(self, text):
        app_state.status_text = text
        get_app().invalidate()

def worker(text):
    app_state.is_running = True
    app_state.status_text = "Starting..."
    get_app().invalidate()
    
    time.sleep(1)
    console.print(f"[bold cyan]User said:[/bold cyan] {text}")
    
    app_state.status_text = "Thinking..."
    get_app().invalidate()
    time.sleep(2)
    
    app_state.status_text = "Calling tool..."
    get_app().invalidate()
    console.print("[yellow]Tool log: doing something...[/yellow]")
    time.sleep(2)
    
    console.print("[bold green]Agent:[/bold green] I am done!")
    
    app_state.is_running = False
    app_state.status_text = ""
    get_app().invalidate()

def bottom_toolbar():
    if app_state.is_running:
        return HTML(f'<b><style bg="ansiyellow" fg="black"> RUNNING </style></b> {app_state.status_text}')
    else:
        return HTML('<b><style bg="ansiblue" fg="white"> IDLE </style></b> Ready.')

def main():
    session = PromptSession(bottom_toolbar=bottom_toolbar)
    with patch_stdout():
        while True:
            try:
                text = session.prompt('❯ ')
                if text.lower() == 'quit':
                    break
                if text.strip():
                    threading.Thread(target=worker, args=(text,)).start()
            except KeyboardInterrupt:
                continue
            except EOFError:
                break

if __name__ == '__main__':
    main()
