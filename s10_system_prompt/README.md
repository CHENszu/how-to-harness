# 第十课：System Prompt —— 告别硬编码，实现运行时动态组装

## 核心概念：为什么要动态组装 System Prompt？

从 s01 到 s09，我们一直使用一行或一段写死的 `SYSTEM` 字符串来设定 Agent 的身份和规则，比如：
```python
SYSTEM = f"You are a coding agent at {WORKDIR}. Use tools to solve tasks."
```
随着我们的 Agent 越来越强大（加入了工具、子代理、任务列表、技能加载、记忆系统），如果我们把所有的说明全塞在一个硬编码的字符串里，会面临以下三个痛点：

1. **牵一发而动全身**：改一行可能导致前面的指令冲突，换个项目甚至需要重写整个 Prompt。
2. **浪费 Token**：有些功能（比如“记忆系统”）在当前会话可能根本没有数据，但你还是把长长的规则发给了 LLM。
3. **缓存命中率低**：如果你每轮都重新生成不确定的 System Prompt，就无法命中各大模型厂商（如 Anthropic 或 OpenAI）底层的 Prompt Cache 缓存，导致响应慢、花钱多。

**Harness 层的核心设计：分段 (Section) + 按真实状态按需拼接 + 本地缓存防抖。**

---

## 核心改造：模块化 Prompt 与按需加载

在 s10 中，我们将庞大、混乱的 System Prompt 拆解成了一个字典 `PROMPT_SECTIONS`，并在运行时（Runtime）根据真实环境状态将其组装起来。

### 1. 拆分 Sections（分段）
我们将 System Prompt 拆成了不同主题的小块：
- **`identity`**（始终加载）：你是谁，你应该如何行事。
- **`tools`**（始终加载）：当前注册了哪些工具，可用工具列表。
- **`workspace`**（始终加载）：当前的工作目录在哪。
- **`memory`**（按需加载）：当前是否有记忆文件，有才加载记忆索引，没有就不加载。

### 2. 按需拼接 (Assemble based on State)
拼接逻辑不再是“猜”，而是基于当前的 **真实状态 (Context)**：
- 程序去扫一眼注册表，发现有 `bash` 工具，就把 `bash` 拼进去。
- 程序去扫一眼 `.memory/MEMORY.md`，发现文件存在且有内容，才会把 `Relevant memories` 这一段拼进去。

### 3. 本地缓存与防抖 (Caching)
同一轮对话的多次工具调用中，只要环境变量（Context）没变，就不应该重新拼接字符串。
我们使用 `json.dumps(context)` 作为 Key，一旦发现状态没变，直接返回上一轮组装好的 System Prompt，节省 CPU 和内存开销（在实际的 Claude Code 中，这里还有着更复杂的 API 层缓存逻辑）。

---

## 实践操作指南

我已经为你适配并准备好了带中文注释的可运行代码，它保留了之前课程的基础工具，去掉了繁杂的压缩逻辑以突出本节核心。

### 第 1 步：运行 s10
在终端中运行：
```bash
python s10_system_prompt/code_annotated.py
```

### 第 2 步：体验动态加载
请在终端中进行以下测试：

1. **观察初始加载**：刚启动程序随便问一句 `你是谁`，注意观察终端打印出的绿色提示 `[assembled] sections: identity, tools, workspace`，以及灰色的 `[cache hit]` 提示。此时因为没有记忆文件，`memory` 没有被加载。
2. **创建记忆触发动态加载**：
   - 输入：`请在 .memory 目录下创建一个叫 MEMORY.md 的文件，内容写上 "- [test](test.md) — 这是一条测试记忆"`
   - Agent 执行完毕后，你可以再输入一句 `你看到了什么记忆？`。
   - 此时你会发现，绿色的日志变为了 `[assembled] sections: identity, tools, workspace, memory`！Agent 感知到了真实文件的存在，自动将记忆模块组装进了 System Prompt 中。

通过这套机制，我们的 Agent 变成了一个像积木一样可插拔的系统，为将来实现更复杂的多智能体、长会话奠定了坚实的基础！
