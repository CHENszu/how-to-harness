# 第二课：Tool Use —— 多加一个工具，只需加一行映射

## 核心概念：为什么需要专门的工具？
在 s01 中，我们的 Agent 只有 `bash` 一个工具。如果它想读一个文件，它必须把意图翻译成命令，比如 `cat README.md`；想写文件，它得用 `echo "..." > file.py`。
这种做法有两个大问题：
1. **容易出错**：复杂的写入或修改，用 bash 拼接非常容易引发引号转义、格式错乱等问题。
2. **浪费 Token**：模型把简单的意图转化成复杂的命令字符串，不仅消耗更多的 Token，还拖慢了执行速度。

因此，我们需要为 Agent 提供**原生的专用工具**（比如专门的 `read_file`、`write_file` 等）。

## 核心改造：分发映射表 (Dispatch Map)
如果你想要给 Agent 加 100 个工具，难道要在 `while True` 循环里写 100 个 `if-else` 吗？
不需要！**Agent 的核心循环（s01 的 30 行代码）一行都不用改！**

我们只需要做两件事：
1. **定义工具箱 (`TOOLS` 数组)**：向大模型宣告“我新增了这几个工具，以及它们的参数格式”。
2. **编写执行逻辑并注册 (`TOOL_HANDLERS` 字典)**：把工具名和对应的 Python 执行函数绑定起来。

### 新增的工具清单：
- `read_file`: 读取文件内容（支持 limit 行数限制）。
- `write_file`: 覆盖写入文件内容。
- `edit_file`: 在文件中查找 `old_text` 并精准替换为 `new_text`。
- `glob`: 找文件，支持通配符（比如 `*.py`）。

### 代码的魔法变化
**s01 的执行方式（硬编码）：**
```python
output = run_bash(block.input["command"])
```
**s02 的执行方式（查表分发）：**
```python
handler = TOOL_HANDLERS[block.name] # 从字典中找到对应的函数
output = handler(**block.input)     # 把参数解包传给函数执行
```

## 高级知识点：并发执行 (Concurrency)
当模型一次性返回多个工具调用时（比如：“帮我读取 a.py，并且同时读取 b.py”）：
- 在我们这个简单的教学版代码里，是**顺序执行**的（排队一个个来）。
- 但在 Claude Code 真正的源码中，它会对这些操作进行分组：**只要是“只读”的操作（如 `read_file`），它会开多线程同时并行执行**，极大地提升了速度。

---

## 实践操作指南

我已经为你准备好了 s02 的代码。

### 第 1 步：运行 s02
在终端中，确保你处于 `harness` 环境中，然后运行我们带有中文注释的代码：
```bash
cd C:\Users\18085\Desktop\claude_code\2_学习\how-to-harness
python s02_tool_use/code_annotated.py
```

### 第 2 步：向 Agent 下达测试指令
你可以试试输入这些问题，观察终端里它调用了什么工具：
- `帮我读一下当前目录的 README.md，总结一下这个项目在讲什么？`
  *(观察它是不是直接调用了 `read_file` 而不是 `bash cat`)*
- `创建一个 test.py，里面打印 hello，然后帮我读一下它。`
  *(观察它如何一次性调用 `write_file`，然后再调用 `read_file`)*
- `帮我找出当前目录下所有的 .md 文件。`
  *(观察它调用 `glob` 工具)*