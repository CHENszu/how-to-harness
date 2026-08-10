# s18: Worktree Isolation — 独立料理台，互不干扰

> *"各干各的目录, 互不干扰"* — 任务管目标，Worktree 管物理隔离。
>
> **Harness 层**: 物理隔离 — 并行执行的目录级安全网。

---

## 问题：拥挤的厨房

在上一节（S17）中，队友们（Agent）已经能够自觉接单干活了。但是，所有的队友都在**同一个目录**下工作！

想象一下：Alice 接了“重构认证模块”的任务，Bob 接了“修改UI”的任务。结果他们都需要修改 `config.py` 文件。
Alice 写了一半，Bob 突然也把这个文件给覆盖了。两个人互相踩脚，而且如果出了问题，你连是谁写错了都分不清，根本没法干净地撤销！

这就好比一家餐厅，所有的厨师都在**同一个案板**上切菜。菜切好了，谁也分不清哪堆是哪道菜的配料。

---

## 解决方案：分配“独立料理台”（Git Worktree）

我们要解决“在哪干活”的问题。这就需要用到 Git 的一个高级功能：**Git Worktree**。
它能让你在同一个代码仓库里，分身出多个“平行宇宙”（独立的物理目录），每个目录都自带一个独立的分支，彼此修改完全隔离。

在这个系统中，我们引入了以下机制：

1. **领班开桌** (`create_worktree`)：当老大（Lead）发布一个高风险任务时，可以顺手为这个任务创建一个独立的 Worktree 目录（例如 `.worktrees/auth-refactor/`），并和任务 ID 绑定。
2. **厨师对号入座** (`bind_task_to_worktree`)：当队友自动认领了这个任务，系统会自动将该队友执行命令（bash、读写文件）的工作目录（`cwd`）切换到这个专属的 Worktree 中。
3. **安全收尾** (`remove_worktree` / `keep_worktree`)：队友干完活后，老大可以检查（保留分支），或者在确认无误/出错放弃时，把这个独立目录直接清理掉。

---

## 工作原理：代码中的体现

### 1. 任务绑定 Worktree
我们的 `Task` 结构体新增了一个 `worktree` 字段。老大在创建任务时，可以调用 `create_worktree("auth-refactor", task_id="task_xxx")`。
这会在 `.worktrees/auth-refactor/` 创建一个真实的物理目录，并切换到 `wt/auth-refactor` 这个新分支，同时给任务打上标记。

```python
def bind_task_to_worktree(task_id: str, worktree_name: str):
    task = load_task(task_id)
    task.worktree = worktree_name
    save_task(task)  # 任务仍然是 pending 状态，等着队友来抢
```

### 2. 队友自动“进站”干活
在队友的守护线程里，系统维护了一个当前工作目录的上下文 `wt_ctx`。
当队友调用 `claim_task` 抢到任务时，如果发现这个任务绑定了料理台（Worktree），系统就会悄悄把这个队友的所有工具（bash、read_file、write_file）的 `cwd`（当前工作目录）切换过去：

```python
# 队友的内部逻辑
wt_ctx = {"path": None}

def _run_claim_task(task_id: str):
    result = claim_task(task_id, owner=name)
    if "Claimed" in result:
        task = load_task(task_id)
        if task.worktree:
            # 自动进站！
            wt_ctx["path"] = str(WORKTREES_DIR / task.worktree)
    return result

# 队友执行 bash 时，实际上是在他专属的目录里执行
def _run_bash(command: str):
    return run_bash(command, cwd=wt_ctx["path"])
```

### 3. 严格的安全收尾
Worktree 里的改动非常珍贵，系统绝不允许随便丢弃：
```python
def remove_worktree(name: str, discard_changes: bool = False):
    # 如果有没提交的代码，直接报错拒绝删除！除非你显式指定 discard_changes=True
    files, commits = _count_worktree_changes(path)
    if files > 0 or commits > 0:
        return "有未提交改动，拒绝删除！请使用 discard_changes=true 强制删除，或使用 keep_worktree 保留审查。"
```

---

## 相对 s17 的变更总结

| 组件 | 之前 (s17) | 之后 (s18) |
|------|-----------|-----------|
| 工作目录 | 所有人都挤在 `WORKDIR` 根目录 | 每个任务可绑定独立的 Git Worktree 物理目录 |
| 队友工具 | 始终在根目录执行 bash/读写 | 认领带有 worktree 的任务后，底层 `cwd` 自动切换 |
| 任务结构 | 无 | 新增 `worktree` 字段绑定 |
| 新增工具 | 无 | `create_worktree`, `remove_worktree`, `keep_worktree` |
| 安全保护 | 无 | 强制检查未提交代码，防止误删隔离区的心血 |

---

## 试一下

在终端中运行：
```sh
python s18_worktree_isolation/code_annotated.py
```

输入以下 Prompt 测试隔离效果：
> "Create two tasks, then create worktrees for each (bind with task_id). Spawn alice and bob. Watch them auto-claim and work in isolated directories."

你可以打开另外一个终端，实时观察 `.worktrees/` 目录下是否生成了对应的文件夹，并且里面的改动完全互不影响。

---

## 接下来

至此，我们的 Agent 团队不仅能自组织（S17），还能在互不干扰的“平行宇宙”里安全干活（S18）。
但这群强大的特种兵，目前只能使用我们手写的有限几个工具（读写文件、bash、任务管理）。

如果我想让它们查询我公司的 Jira 库？或者让它们去读取我本地的 MySQL 数据库？难道我每次都要给它们手写 Python 工具函数吗？

**s19 MCP Plugin** 章节，我们将接入 Model Context Protocol。给 Agent 开放一个标准化的“USB 接口”，不管外面是什么插件，插上就能用！