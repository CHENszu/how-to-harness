import time
import threading
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.formatted_text import HTML
from rich.console import Console

console = Console()

def worker():
    with console.status("Working...", spinner="dots"):
        time.sleep(2)
        console.print("[green]Step 1 done[/green]")
        time.sleep(2)
        console.print("[green]Step 2 done[/green]")

def bottom_toolbar():
    return HTML('<b><style bg="ansired">  Coco Agent  </style></b> Type something...')

def main():
    session = PromptSession(bottom_toolbar=bottom_toolbar)
    with patch_stdout():
        while True:
            text = session.prompt('> ')
            if text == 'quit':
                break
            
            console.print(f"You said: {text}")
            t = threading.Thread(target=worker)
            t.start()

if __name__ == '__main__':
    main()
