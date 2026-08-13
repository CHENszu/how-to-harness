# Mini Claude Code (Agent Harness)

这是基于 OpenHarness 架构演进出来的一个迷你版的 Claude Code (Agent Harness)。
它的目标是提供一个轻量、结构清晰、能在 Windows 终端无缝运行的单 Agent 核心底座。

## 🎯 核心目标
1. **极简起步**：抛弃复杂的工程化封装，回归 Agent 的本质（观察-思考-调用工具-回复）。
2. **结构清晰**：参考 OpenHarness 的分层思想，将引擎（Engine）、工具（Tools）与入口（Main）分离。
3. **Windows 兼容**：确保在 Windows 终端中运行顺畅，处理好编码、路径和子进程等问题。

## 🚀 快速体验

本目录提供了一个完整的 Mini Claude Code 体验版，你可以直接在这里启动 Agent，让它帮你执行系统指令、搜索网络或读写文件。

### 1. 环境准备

确保你已经激活了正确的 Conda 环境（例如 `harness`），并且安装了依赖：

```bash
conda activate harness
pip install -r requirements.txt
```

### 2. API 配置

Agent 支持原生的 Anthropic API，也支持兼容 OpenAI 格式的其他大模型（如 DeepSeek 等）。
在 `agent` 目录下，创建一个 `.env` 文件（或直接复制 `.env.example`，如果有的话），并根据你的情况配置以下环境变量：

**方式一：使用原生 Anthropic Claude**
```env
ANTHROPIC_API_KEY=sk-ant-api03-xxx...
```

**方式二：使用兼容格式的模型（如 DeepSeek）**
```env
ANTHROPIC_API_KEY=sk-xxxxxx...
ANTHROPIC_BASE_URL=https://api.deepseek.com/v1
```
*(注：如果配置了 `ANTHROPIC_BASE_URL`，系统会自动将请求端点路由至 `/chat/completions` 并使用 `Bearer` 认证方式进行适配。)*

### 3. 启动 Agent

配置完成后，直接在终端中运行以下命令启动 Agent：

```bash
python main.py
```
*(如果没有配置 `.env` 文件，程序启动后也会提示你手动输入 API Key)*

---

## 📂 目录结构 (当前规划)
```text
agent/
├── README.md       # 本项目说明与规划文档
├── requirements.txt# 依赖文件 (httpx, pydantic)
├── main.py         # 命令行交互入口 (CLI)，负责用户输入与输出打印
├── engine.py       # 核心引擎 (Agent Loop)，负责与大模型通信及解析工具调用
└── tools/          # 工具包目录 (模块化组织)
    ├── __init__.py # 工具注册表与导出
    ├── base.py     # 工具基类 (BaseTool)
    ├── bash_tool.py
    ├── web_search_tool.py
    ├── web_fetch_tool.py
    ├── file_read_tool.py
    ├── file_write_tool.py
    ├── glob_tool.py
    ├── grep_tool.py
    ├── todo_write_tool.py
    └── ask_user_question_tool.py
```

## 🛠️ 已分配工具 (Tools)
目前提供以下核心工具，覆盖了网络、系统、文件与交互：

**系统与网络 (System & Network)**
1. **`bash`**: 在 Windows PowerShell/CMD 中执行命令。
2. **`web_search`**: 通过搜索引擎获取实时信息 (内置防封禁降级)。
3. **`web_fetch`**: 抓取指定 URL 的网页纯文本内容。

**文件操作 (File Operations)**
4. **`file_read`**: 精确读取文件内容，支持按行号截取。
5. **`file_write`**: 写入文件，自动创建不存在的父目录。
6. **`glob`**: 通配符搜索本地文件 (如 `**/*.py`)。
7. **`grep`**: 正则表达式搜索文件内容。

**任务规划与交互 (Planning & Interaction)**
8. **`todo_write`**: 管理 Markdown 格式的待办事项清单 (TODOs.md)。
9. **`ask_user_question`**: 遇到歧义时，主动挂起并向人类提问。

## 🗺️ 演进路线 (Roadmap)
- [ ] **Phase 1: 基础底座** (当前任务)
  - 实现 `tools.py` 中的三个基础工具。
  - 实现 `engine.py` 中的 Agent Loop（包含提示词构建、API 调用、响应解析）。
  - 实现 `main.py` 的终端交互。
- [ ] **Phase 2: 记忆与状态管理** (待定)
  - 引入短时记忆压缩（解决 Prompt 太长的问题）。
- [ ] **Phase 3: 技能扩展 (Skills)** (待定)
  - 支持从外部 Markdown 加载技能指令。

> **注**：后续增加任何新任务或模块，都会优先在此 README 中更新规划。
