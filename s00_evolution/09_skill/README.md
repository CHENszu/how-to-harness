# 09. 技能按需加载 (Skills System)

## 模块目标
本模块引入了 **Skill（按需加载的扩展能力）** 机制。这是 OpenHarness 等高级 Agent 框架中一种非常优雅的架构设计，它解决了“系统提示词过长导致 Token 消耗巨大”和“功能难以扩展”的痛点。

在之前的模块中，如果我们想让 Agent 拥有画图、分析财报、写特定框架代码等专业能力，往往需要把大量的 Prompt 硬编码在 `engine.py` 中。而通过 Skill 机制，我们将这些知识**外置为 Markdown 文件**，并采用“渐进式披露”的模型让 Agent 在需要时自行读取。

## 核心机制：渐进式披露 (Progressive Disclosure)

为了优化 Token 并在多轮对话中保持性能，Skill 的加载分为两步（Tier 1 & Tier 2）：

1. **扫描与发现 (Tier 1)**：
   系统启动时，`skills_loader.py` 会扫描 `skills/` 目录。它解析每个 `SKILL.md` 的 YAML 头部（Frontmatter），仅提取 `name` 和 `description` 等元数据。
   Agent 此时可以通过 `skills_list` 工具获取到所有可用技能的清单。这就像是一本“技能目录”，非常轻量。

2. **按需加载 (Tier 2)**：
   当用户下达指令（例如“使用 algorithmic-art 技能画图”），Agent 发现任务匹配目录中的某个技能，就会主动调用 `skill_view(name)` 工具。
   此时，系统才会将该技能对应的 `SKILL.md` 完整内容（长达几千字的操作指南和代码模板）注入到当前的上下文中。

## 关键代码结构

- **`skills/` 目录**：沙箱目录。每个子目录代表一个独立的 Skill，包含 `SKILL.md`（说明书）和可选的辅助文件（如模板、脚本）。
- **`skills_loader.py`**：核心解析器。负责读取本地文件系统，解析 Markdown 中的 YAML 前置数据，并将结果注册到内存中的 `SkillRegistry`。
- **`tools.py` (新增工具)**：
  - `SkillsListTool`: 向 Agent 返回简短的元数据列表。
  - `SkillViewTool`: 根据技能名称，返回完整的 Markdown 内容。
  - *注：这两个工具均标记为 `is_read_only = True`，在默认权限模式下无需用户审批即可自动执行。*
- **`main.py`**：在初始化 `ToolRegistry` 时，额外加载本地的 Skills，并注册上述两个查询工具。

## 测试指南

确保你已经激活了虚拟环境：
```bash
conda activate harness
```

运行入口程序：
```bash
python main.py
```

**测试场景 1：查询技能**
- 输入：`列出你当前拥有的所有可用技能`
- 预期：Agent 调用 `skills_list` 工具，返回诸如 `algorithmic-art`, `canvas-design` 等技能的名称和简短描述。

**测试场景 2：按需触发**
- 输入：`使用 algorithmic-art 技能，帮我构思一个“量子波动”主题的算法艺术理念`
- 预期：
  1. Agent 判断需要该技能，自动调用 `skill_view("algorithmic-art")`。
  2. 终端打印 `[SkillView] 正在加载技能详情: algorithmic-art`。
  3. Agent 阅读长达数千字的指令后，根据说明书的要求，为你生成严谨的、包含 4-6 段阐述的算法艺术理念（Philosophy）。

## 演进意义
通过这一步，我们的 Agent 已经从一个单纯的“API 调用机”，进化成了一个可以**通过挂载文本文件来无限扩展领域知识**的智能体。这种基于纯文本的插件系统，极大降低了用户自定义 Agent 行为的门槛。