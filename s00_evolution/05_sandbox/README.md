# 05. Sandbox 沙箱与隔离机制

在 Agent 架构中，如果放任大模型在用户的真实电脑里随意执行 `bash` 命令或修改文件，将会是一场灾难。
OpenHarness 实现了一套非常优雅的**三层隔离机制**，本模块将为你解析其底层原理。

## OpenHarness 的三层沙箱

通过对源码的分析，OpenHarness 并没有自己去用 C/C++ 写底层的系统拦截代码，而是巧妙地**作为“包工头”，去调用现成的专业沙箱工具**。

### 1. Docker 沙箱 (重量级系统隔离)
- **原理**：Agent 决定执行命令时，OpenHarness 在后台调用本机的 Docker。
- **实现方式**：通过 `subprocess.run(["docker", "run", ...])` 启动一个隔离的容器。
- **特点**：提供最彻底的网络、文件系统和 CPU/内存隔离，但启动较慢，且要求用户的电脑装有 Docker。

### 2. SRT (Sandbox Runtime - 轻量级进程隔离)
这是 OpenHarness 的默认方案，依赖于 Anthropic 提供的 `@anthropic-ai/sandbox-runtime`。
- **Linux 平台**：底层调用 `bwrap` (Bubblewrap)。
- **macOS 平台**：底层调用苹果自带的 `sandbox-exec`。
- **原理**：它通过生成一份 JSON 配置文件，规定当前命令“只能读 A 文件夹”、“只能写 B 文件夹”、“禁止访问外网”。然后用 `srt` 包裹着真实的命令执行（例如：`srt --config rule.json -- bash -c "ls"`）。

### 3. Git Worktree (工作区/多智能体隔离)
在 S15 的长工与包工头模式中，如果多个 Agent 同时在主目录下修改代码，一定会发生文件冲突。
- **原理**：OpenHarness 会调用 `git worktree add`。
- **效果**：它会在电脑的临时目录里，为每个 Agent 瞬间克隆出一份**完全独立但共享同一个 Git 仓库**的代码副本。
- **优化**：为了省空间，它还会把 `node_modules` 或 `.venv` 这样的超大目录通过**软链接 (Symlink)** 共享过去。

## 运行演示

在本次的代码演示中，我们将重点模拟第 3 种隔离（Git Worktree）的核心逻辑，以及一个轻量级的基于 Python 的目录隔离机制。

在虚拟环境中运行：
```bash
conda activate harness
python code_annotated.py
```
