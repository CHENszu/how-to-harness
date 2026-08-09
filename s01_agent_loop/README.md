# 第一课：Agent Loop —— 一个循环就够了

## 核心概念：什么是 Agent Loop？
当我们跟大模型（比如 Claude）对话时，如果问：“帮我看看当前目录下有什么文件”，通常它只会给你回复一段类似 `ls` 的 bash 命令文本。然后你需要自己复制到终端里去运行，再把终端的输出结果粘贴回对话框里告诉它。

在这个过程中，**你**就是那个手动跑命令的“工具人”。

如果要把这个过程自动化，让模型自己跑命令、自己看结果，我们需要写一段极简的代码。这段代码的本质就是一个 `while True` 的无限循环。这就是所谓的 **Agent Loop（代理循环）**。

### 工作流程
1. 把你的问题和**工具箱**（比如包含一个 `bash` 工具）一起发给大模型。
2. 模型思考后，如果它说：“我要使用 `bash` 工具执行 `ls` 命令”（这个状态叫 `stop_reason == "tool_use"`）。
3. 我们的代码（Harness）就会拦截到这个请求，在本地替它执行 `ls`。
4. 我们把 `ls` 的输出结果，再追加到聊天记录里，发送给大模型。
5. **循环继续**，直到模型说：“我搞定了，这是最终答案”（`stop_reason != "tool_use"`），此时循环结束，输出结果。

一句话总结：
> **“一个工具 + 一个循环 = 一个 Agent”**
> 模型负责“思考”和“发号施令”，循环代码（Harness）负责“执行”和“反馈”。

---

## 代码拆解（见同目录下的 s01_code_annotated.py）
你可以查看我为你添加了中文注释的代码文件。整个核心循环不到 30 行：

```python
def agent_loop(messages: list):
    while True:
        # 1. 带着聊天记录和工具箱，去问大模型
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )

        # 2. 把模型的回复追加到聊天记录里
        messages.append({"role": "assistant", "content": response.content})

        # 3. 检查模型是不是想用工具。如果不想用（说明回答完毕），就退出循环
        if response.stop_reason != "tool_use":
            return

        # 4. 如果模型想用工具，我们就在本地执行工具（比如跑 bash 命令）
        results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"\033[33m$ {block.input['command']}\033[0m")
                output = run_bash(block.input["command"]) # 本地跑命令
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                })

        # 5. 把跑完的结果追加到聊天记录，进入下一次循环
        messages.append({"role": "user", "content": results})
```

---

## 实践操作指南

我已经为你配置好了环境依赖。接下来你可以亲自跑一下这第一段代码。

### 第 1 步：配置你的 API Key
你只需要在 `C:\Users\18085\Desktop\claude_code\2_学习\how-to-harness\.env` 文件中配置一次即可。我已经帮你填好了 DeepSeek 的配置信息。

### 第 2 步：在终端里运行
在终端中激活 `harness` 环境并运行：
```bash
conda activate harness
cd C:\Users\18085\Desktop\claude_code\2_学习\how-to-harness
python s01_agent_loop/code_annotated.py
```

### 第 3 步：向 Agent 下达指令
当看到 `s01 >>` 提示符时，你可以试着输入以下指令，观察终端里它是如何自己调用 bash 命令并拿到结果的：
- `请帮我在当前目录下创建一个名为 hello.py 的文件，里面打印 "Hello, World!"`
- `当前目录下有哪些 python 文件？`
- `查看一下系统当前的 Python 版本`

观察重点：当它调用工具时，循环会继续；当它直接回答你时，循环结束，等待你的下一个指令。
