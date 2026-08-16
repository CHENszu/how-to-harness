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
├── requirements.txt# 依赖文件
├── tests/          # 单元测试与验证脚本
├── .coco/          # (运行时生成) 统一存储配置文件、短时会话快照与长时记忆
├── skills/         # 第三方技能库 (按需加载)
└── src/            # 源代码目录
    ├── main.py     # 命令行交互入口 (CLI)
    ├── engine.py   # 核心引擎 (Agent Loop)
    ├── config_manager.py # 配置管理
    ├── memory/     # 记忆管理模块
    └── tools/      # 工具包目录 (模块化组织)
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

**子代理委派 (Sub-Agent)**
10. **`search_agent`**: 启动专职检索与代码分析的子代理，执行宽泛的调研任务。

**技能加载 (Skills & Progressive Disclosure)**
11. **`skills_list`**: 扫描 `skills/` 目录，读取 YAML 元数据返回可用技能列表 (Tier 1 按需加载)。
12. **`skill_view`**: 读取指定技能的完整 `SKILL.md` 文档内容 (Tier 2 深入加载)。

## 🗺️ 演进路线 (Roadmap)
- [x] **Phase 1: 基础底座** 
  - 实现基础工具、Agent Loop 与终端交互。
- [x] **Phase 2: 记忆与状态管理** 
  - 引入短时记忆自动压缩机制。
  - 实现双层长时记忆（用户偏好与项目上下文）的提取与融合 Hook。
  - 统一运行时数据存储路径至 `.coco/` 目录。
- [x] **Phase 3: 技能扩展 (Skills)** 
  - 引入外部第三方技能库 (`skills/`)。
  - 实现基于渐进式披露的技能按需加载机制 (Tier 1 发现 + Tier 2 深入)。
- [ ] **Phase 4: 插件与生态 (Plugins & MCP)** (待定)
  - 接入 MCP (Model Context Protocol) 协议支持。

> **注**：后续增加任何新任务或模块，都会优先在此 README 中更新规划。
