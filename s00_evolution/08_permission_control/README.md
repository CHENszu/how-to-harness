# 第8课：权限管控与运行模式 (Permission Control & Modes)

在前面的章节中，我们赋予了 Agent 使用工具（搜索、执行Bash、写文件等）和记忆的能力。
但是，这也带来了巨大的安全风险。如果 Agent 不小心或者被恶意引导执行了 `rm -rf /`，或者随意修改了核心代码，将会造成灾难性的后果。

为了解决这个问题，OpenHarness 实现了一套**权限管控体系 (Permission Control)**。

## 💡 核心机制：模式与拦截

本节我们引入了三种递进的自动化运行模式：

*   **DEFAULT（默认模式）**：所有“变更类”工具（如写入文件、执行 Bash）在执行前都必须经过用户手动确认审批。只读工具（如联网搜索）则自动放行。
*   **PLAN（规划模式）**：严格禁止所有变更类工具执行，仅允许读取操作。通常用于让 Agent 先给出方案，而不允许它直接动手。
*   **FULL_AUTO（全自动模式）**：允许所有已注册的工具直接运行，无需用户干预（仅限受信任环境或沙箱）。

## 🛠️ 本节重点代码结构

我们在 07 节的基础上，引入 `permissions.py` 并修改了工具和引擎逻辑：

1. **`permissions.py`**:
   - 定义了 `PermissionMode` (三种模式)。
   - 实现了 `PermissionChecker` 权限检查器，负责评估某次工具调用是否被允许。
2. **`tools.py`**:
   - 在 `BaseTool` 抽象类中增加了 `is_read_only` 属性。
   - 将 `WebSearchTool` 标记为 `is_read_only = True`，其他如 bash、写文件标记为 False。
3. **`engine.py`**:
   - 在 Agent Loop 中，工具执行 `execute()` 之前，先调用 `PermissionChecker.evaluate()` 进行拦截和评估。
   - 根据评估结果（`allowed`, `requires_confirmation`）决定是直接执行、拦截询问用户，还是直接拒绝。

## 🚀 运行与测试

```bash
python main.py
```

**测试流程**：
1. 问它：*“帮我搜索一下今天的天气”* （搜索工具是只读的，应该直接自动执行，不需确认）。
2. 问它：*“帮我新建一个 test_perm.txt 并写入 hello”* （写文件工具是变更类，系统会挂起并弹窗询问你是否允许）。
3. 输入 `n` 拒绝执行，观察 Agent 的应对反应（它会知道你拒绝了，并向你道歉或询问原因）。
4. 再次让它执行并输入 `y` 允许，观察其成功写入。