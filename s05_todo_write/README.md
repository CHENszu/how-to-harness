# 第五课：TodoWrite —— 没有计划的 Agent，做着做着就偏了

## 核心概念：为什么要教 Agent 做计划？

设想你给大模型下达一个复杂任务：
> "把所有的 Python 文件改成 snake_case 命名，然后跑测试，修好所有失败的测试。"

如果没有计划机制，Agent 开始干活的流程通常是：
改了 3 个文件 -> 跑了个测试 -> 发现 2 个失败 -> 开始修这 2 个失败。
修着修着，**它就完全忘记了最初的任务是“把所有文件改成 snake_case”**，它的注意力被后面无穷无尽的测试报错全吸走了。

当对话上下文越来越长，早期的指令（System Prompt 和最初的 User 需求）的影响力会被后面大量的代码和终端输出稀释。
一个 10 步的任务，它做完前 3 步就开始“即兴发挥”了。

**Harness 层面的解法：规划。**
强制 Agent 在动手干活之前，**先想清楚并写下待办清单（Todo List）**。每做完一步，回来打个勾，再看下一步是什么。

---

## 核心改造：todo_write 工具

在 s05 中，我们给模型新发了一个工具：`todo_write`。
**关键洞察**：`todo_write` 工具**没有提供任何执行能力**。它不能读文件，不能跑命令。它提供的仅仅是**规划能力**。

### 1. 新增的工具
我们在 `TOOLS` 列表里加了一项 `todo_write`，它接收一个包含 `content` (任务内容) 和 `status` (状态：pending, in_progress, completed) 的数组。

```python
# 接收并打印当前的 TODO 状态
def run_todo_write(todos: list) -> str:
    global CURRENT_TODOS
    CURRENT_TODOS = todos
    # 在终端打印出漂亮的 TODO 进度树...
    return f"Updated {len(CURRENT_TODOS)} tasks"
```

### 2. 引导模型使用它 (System Prompt)
我们在系统提示词中加了一句话：
> "Before starting any multi-step task, use todo_write to plan your steps. Update status as you go."
> (在开始任何多步任务前，使用 todo_write 规划你的步骤。并在进行中更新状态。)

### 3. “唠叨”机制 (Nag Reminder)
光告诉模型要用还不够，它写起代码来容易上头，一连写了几轮都忘了更新进度。
所以我们在 `agent_loop` 循环里加了一个计数器 `rounds_since_todo`。
如果模型连续 **3 轮**对话都没有调用 `todo_write`，代码会强行给它注入一条提示：
`<reminder>Update your todos.</reminder>`
这就好像有个监工在旁边提醒：“哎，看看你的计划表，进度到哪了？”

---

## 实践操作指南

我已经把 s05 的代码适配了 DeepSeek 客户端和 UTF-8 编码修复，并存为了 `code_annotated.py`。

### 第 1 步：运行 s05
在终端中运行：
```bash
cd C:\Users\18085\Desktop\claude_code\2_学习\how-to-harness
python s05_todo_write/code_annotated.py
```

### 第 2 步：下发复杂任务
你可以试着输入：
`请在当前目录下创建一个 test_pkg 文件夹，里面包含 __init__.py、utils.py 和 tests/test_utils.py 三个文件，分别写入一些基础代码。`

**观察重点：**
1. 第一次工具调用是不是 `todo_write`？（它会先在终端打印出一个黄色的任务清单）。
2. 在执行过程中，它会不会停下来再次调用 `todo_write`，把状态从 `pending` 改成 `in_progress`（▸）和 `completed`（✓）？

如果观察到了这些现象，恭喜你，你的 Agent 已经学会了“三思而后行”！