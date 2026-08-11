<!-- 头部横幅 -->
<div align="center">
  
![Header](https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,11,20&height=200&section=header&text=how-to-harness&fontSize=80&fontAlignY=35&animation=twinkling&fontColor=fff)

### 👋 欢迎来到 how-to-harness

💼 **Learn Harness and Hermes** | 🎓 **慢就是快：从零手写 Agent 底层框架**

<br>

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python&logoColor=white)
![Conda](https://img.shields.io/badge/conda-harness-44A833?style=flat-square&logo=anaconda&logoColor=white)
![Agent](https://img.shields.io/badge/Framework-OpenHarness-orange?style=flat-square&logo=dependabot&logoColor=white)

</div>

---

## 项目简介
本项目记录了关于大模型 Agent 运行框架的学习与探索过程。整个项目包含两条学习主线（**持续更新ing...**）：

1. **外层探索 (1-20等目录)**：初步参照 [shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) 进行学习，但由于该部分内容较为庞杂，直接上手容易感到“懵”。
2. **内层拆解 (`s00_evolution` 目录)**：为了真正搞透 Agent 的底层逻辑，决定回归“慢就是快”的原则，基于 [HKUDS/OpenHarness](https://github.com/HKUDS/OpenHarness) 的源码，将其核心能力自主拆分为约 10 个循序渐进的模块来进行“造轮子”式的复刻学习。带你深度理解大模型应用开发是如何从“提示词工程”一步步演进到为大模型“造整车”的“Harness 工程”阶段的。

## 目录结构与内容

### `s00_evolution` - Harness 核心组件演进历程 (OpenHarness 拆解)
该目录采用循序渐进的方式，拆解并复刻了 Agent 框架的核心零部件。它将大模型比作“发动机”，并逐步为其配备“方向盘”、“底盘”和“仪表盘”：

* **01_agent_loop** (变速箱)：基础的 Agent 反应式循环。实现了基于 `while True` 循环和 LLM `tool_calls` 的自主决策与多轮次执行架构。
* **02_tools** (方向盘和四肢)：工具调用机制的基础实现。构建了工具抽象类 `BaseTool`，赋予模型执行外部动作（如 Bash 终端命令执行）的能力。
* **03_web_search**：联网搜索工具。集成了外部搜索引擎（如 DuckDuckGo），让模型突破数据截止日期限制。
* **04_web_fetch**：网页内容抓取。为 Agent 提供读取和解析具体网页内容的能力。
* **05_sandbox** (安全防线)：代码执行沙箱。通过 Docker 隔离环境，安全地执行由 AI 生成的未知代码，防止宿主机受损。
* **06_short_term_memory** (短期记忆)：上下文压缩机制。针对长对话，实现了“四步走”压缩策略（微压缩、文本折叠、会话快照、全量总结），在保证上下文不丢失的前提下大幅节省 Token，并将记忆状态安全地外置持久化。
* **07_long_term_memory** (长期记忆)：跨会话的记忆持久化系统。使 Agent 能够沉淀项目经验、代码规范和用户偏好。
* **08_permission_control** (权限管控)：敏感操作拦截机制。实现了 `PermissionChecker` 进行敏感路径过滤，并引入三种运行模式：`DEFAULT`（变更类操作需终端交互审批）、`PLAN`（只读模式）、`FULL_AUTO`（全自动无人值守模式）。

> **真诚希望**：本项目能帮你深入理解大模型 Agent 底层运行的真正原理。

---

<div align="center">

![Footer](https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,11,20&height=100&section=footer)

</div>