import asyncio
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

async def agent_task():
    for i in range(5):
        await asyncio.sleep(1)
        print(f"Agent thinking... {i}")

async def main():
    session = PromptSession()
    with patch_stdout():
        while True:
            # We can start a background task
            bg_task = asyncio.create_task(agent_task())
            
            # Wait for user input
            try:
                result = await session.prompt_async('You: ')
                if result == 'quit':
                    break
                print(f"You typed: {result}")
            except (EOFError, KeyboardInterrupt):
                break

if __name__ == '__main__':
    asyncio.run(main())
