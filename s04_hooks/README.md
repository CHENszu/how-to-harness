# 第四课：Hooks —— 挂在循环上，不写进循环里

## 核心概念：为什么要用 Hook (钩子)？
在上一节（s03）中，我们把安全权限检查 `check_permission()` 硬编码写死在了 `while True` 循环里面。

但是，如果我们的 Agent 越来越复杂，比如：
- 我们想在每次执行工具前，打印一条日志。
- 我们想在工具执行后，如果文件被修改了，自动执行 `git add`。
- 我们想在每次收到用户输入时，偷偷往里面塞一点上下文信息。

如果把这些代码全塞进 `agent_loop` 函数里，这个本来只有 30 行的极简循环，很快就会膨胀成几百行、面目全非的“屎山代码”。

**Harness 工程的核心原则：循环是一个稳定的核心，不应该被侵入。所有的扩展逻辑，都应该像挂件一样“挂”在循环外面。** 这个挂件，就叫 **Hook (钩子)**。

## 核心改造：四个关键生命周期
我们在 Agent Loop 的四个关键节点抛出了“钩子”，你可以把任何想做的事情注册到这些钩子上。

1. **`UserPromptSubmit` (用户提交输入时)**：在进入大模型前触发。可以用来篡改/丰富用户的输入。
2. **`PreToolUse` (工具执行前)**：s03 的**权限检查**就搬到了这里！还可以加**日志记录**。
3. **`PostToolUse` (工具执行后)**：工具跑完出结果了。可以用来做**结果拦截**（比如发现输出超过 10万字，就发出警告）。
4. **`Stop` (循环即将停止时)**：模型说它干完了。在这里可以做收尾工作（比如统计一下这轮对话总共调了多少次工具）。

### 代码的魔法变化（直观对比）

我们可以把 **Agent Loop（核心循环）** 想象成一条 **“汽车流水线”**。
`Hook`（钩子）就是传送带旁边的一个个**“插槽”或者“工位”**。

假如我们想在“执行工具前”做两件事：1. 检查权限 2. 打印日志

#### ❌ 之前的写法 (s03)：硬编码（把逻辑直接塞进流水线里）
```python
def agent_loop(messages: list):
    while True:
        # ...
        for tool_call in response_message.tool_calls:
            # 业务逻辑 1：打印日志（硬编码在循环里）
            print(f"> 准备使用工具: {tool_call.function.name}")
            
            # 业务逻辑 2：权限检查（硬编码在循环里）
            if not check_permission(tool_call): 
                continue # 拦截
            
            # 真正执行工具...
            handler(**args)
```
**缺点**：如果加 10 个新功能，流水线代码就会无限膨胀，变成不敢碰的“屎山”。

#### ✅ 现在的写法 (s04)：Hook 机制（流水线只提供插槽）
```python
# 核心循环 agent_loop 变得极其干净：
def agent_loop(messages: list):
    while True:
        # ...
        for tool_call in response_message.tool_calls:
            
            # ！！！流水线大喊一声：触发 "PreToolUse" 插槽上的所有外挂！！！
            blocked = trigger_hooks("PreToolUse", tool_call.function.name, args)
            
            if blocked:
                continue # 外挂说不准执行，就跳过
                
            # 真正执行工具...
            handler(**args)
```

**具体的逻辑去哪了？**
它们被写成了独立的函数，放在循环外面。像插 U 盘一样插到 `PreToolUse` 这个槽位上：
```python
# 独立的模块
def log_hook(name, args):
    print(f"日志：准备使用 {name}")

def permission_hook(name, args):
    if name == "bash" and "rm -rf" in args:
        return "权限拒绝"

# 注册（插U盘）
register_hook("PreToolUse", permission_hook)
register_hook("PreToolUse", log_hook)
```

---

## 实践操作指南

我已经把 s04 的代码翻译并适配好了 DeepSeek/OpenAI 格式。

### 第 1 步：运行 s04
在终端中，确保你处于 `harness` 环境中，运行：
```bash
cd C:\Users\18085\Desktop\claude_code\2_学习\how-to-harness
python s04_hooks/code_annotated.py
```

### 第 2 步：观察 Hook 的触发
你可以试着输入：
`请读取 README.md 文件`

注意观察终端输出中带有 `[HOOK]` 字样的灰色提示：
1. 一敲回车，马上会出现 `[HOOK] UserPromptSubmit...`
2. 在真正去读文件前，会出现 `[HOOK] read_file(...)`
3. 对话结束后，会出现 `[HOOK] Stop: session used 1 tool calls`

这证明我们的扩展逻辑已经成功地通过“挂钩子”的方式运行了，而核心循环保持了完美的纯洁！