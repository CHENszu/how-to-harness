# 第三课：Permission —— 工具执行前加一道门

## 核心概念：为什么需要权限判断？
在上一节中，我们给模型配备了多个强大的工具，甚至还有万能的 `bash`。这就像把一把上膛的枪交给了大模型。如果模型发神经，决定执行 `rm -rf /` 把电脑根目录清空怎么办？

**安全不能靠“信任模型”，必须靠“代码规则”约束！**

在真正的企业级或生产级 Agent 中，在工具被实际调用执行（`output = handler()`）之前，必须加一道**权限判断（Permission Pipeline）**。

## 核心改造：三道安全闸门
在 `while True` 循环里，我们在真正调用 `TOOL_HANDLERS` 之前插入了一个 `check_permission()` 函数。这个函数会依次经过三道闸门：

### 闸门 1：硬拒绝列表 (Hard Deny)
- **作用**：永远禁止执行的危险操作。
- **示例**：如果命令中包含 `rm -rf /`，`sudo`，直接报错拦截，**模型连求情的机会都没有**。

### 闸门 2：规则匹配 (Rule Matching)
- **作用**：判断这个操作是否需要谨慎对待。
- **示例**：
  - 如果调用 `write_file`，但路径指向了当前工作区之外的地方（比如 `C:\Windows\System32`）。
  - 如果调用 `bash`，命令里包含删除文件的关键字 `rm `。
- **结果**：如果触发了这些规则，不会直接拒绝，而是进入闸门 3。

### 闸门 3：用户审批 (User Approval)
- **作用**：把决策权交给人类。
- **逻辑**：在终端暂停，提示用户：“模型想执行 XXX 命令，是否允许？(y/N)”。如果用户输入 y，放行；否则拦截。

> **如果前两道闸门都没有命中（比如只是普通的 `read_file` 读文件），就会直接放行执行，不会打扰用户。**

---

## 代码的魔法变化
**s02 的核心逻辑：**
```python
output = TOOL_HANDLERS[block.name](**block.input)
```

**s03 的核心逻辑：**
```python
# 每次执行工具前，先做检查
if not check_permission(block): 
    # 如果没通过检查，直接告诉模型“权限被拒绝”
    results.append({"content": "Permission denied."})
    continue # 跳过，不执行真正的工具

# 如果通过了检查，才真正执行
output = TOOL_HANDLERS[block.name](**block.input)
```

---

## 实践操作指南

### 第 1 步：运行 s03
在终端中，确保你处于 `harness` 环境中，运行：
```bash
cd C:\Users\18085\Desktop\claude_code\2_学习\how-to-harness
python s03_permission/code_annotated.py
```

### 第 2 步：向 Agent 施加“危险”指令
你可以试试这几条指令，观察不同的闸门是如何生效的：
1. **测试直接放行**：`帮我看看当前目录下有什么文件` (调用只读工具，应该直接出结果)
2. **测试用户审批**：`帮我删掉当前目录下的 test.txt 文件` (调用 `bash rm`，应该会暂停问你是否同意，你可以输入 `n` 拒绝)
3. **测试硬拒绝**：`请执行 sudo rm -rf /` (命中危险词，直接拒绝，不问用户)
