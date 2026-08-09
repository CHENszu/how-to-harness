# 第七课：Skill Loading —— 技能按需加载，别把字典全背身上

## 核心概念：为什么不能把所有规范塞进 System Prompt？

假设你的项目有一份 React 规范（2000行）、一份 SQL 规范（1500行）、一份 API 设计规范（3000行）。
为了让 Agent 写的代码符合公司标准，最简单粗暴的方法是：把这 6500 行规范全塞进 System Prompt 里。

**这会带来灾难性的后果：**
1. **Token 浪费极其严重**：Agent 哪怕只是去改一个简单的 CSS 颜色，也要把这 6500 行毫不相干的 SQL 和 API 规范读一遍，既花钱又慢。
2. **注意力稀释**：背景信息太多，大模型会抓不住重点。

**Harness 层的解法：两级按需加载（Two-level on-demand injection）**
就像你去图书馆：
- **第一级（目录）**：System Prompt 里只给模型看一个只有几行字的“技能目录”。（非常便宜）
- **第二级（正文）**：当模型觉得自己需要写 SQL 时，它主动使用 `load_skill("sql-style")` 工具，把那一本技能书借出来看。（按需花钱）

---

## 核心改造：启动时扫描与 `load_skill` 工具

### 1. 启动时扫描技能库，生成轻量级目录
在 Harness 启动时，代码会去扫描当前目录下的 `skills/` 文件夹。
它会读取里面每一个 `SKILL.md` 文件的开头（YAML frontmatter），提取出名字和一句话描述。
最终，在 System Prompt 里，模型只会看到这么一小段话：
```text
Skills available:
- **agent-builder**: Instructions for building custom specialized sub-agents
- **code-review**: Guidelines for performing code reviews
- **mcp-builder**: Instructions for building Model Context Protocol servers
Use load_skill to get full details when needed.
```
（这大约只占 100 个 token）。

### 2. 运行时按需加载 (load_skill 工具)
我们在工具箱里增加了一个 `load_skill` 工具。
如果用户要求：“帮我 review 一下这段代码。”
大模型看到任务，再对比自己的“技能目录”，发现有一个叫 `code-review` 的技能非常合适。
于是它调用 `load_skill(name="code-review")`。
Harness 就会把几千字的 `code-review/SKILL.md` 的正文，作为工具的返回值（tool_result）发给大模型。

**安全机制**：注意，`load_skill` 并不是通过读取文件路径实现的，而是通过查内存里的 `SKILL_REGISTRY` 字典。这样就彻底杜绝了模型瞎编一个路径（比如 `../../etc/passwd`）来读取敏感文件的风险。

---

## 实践操作指南

为了方便你测试，我已经把教程源码里的 `skills/` 文件夹复制到了 `2_学习/how-to-harness/skills` 目录下。

### 第 1 步：运行 s07
在终端中运行：
```bash
cd C:\Users\18085\Desktop\claude_code\2_学习\how-to-harness
python s07_skill_loading/code_annotated.py
```

### 第 2 步：体验按需加载
你可以输入这样一个 Prompt：
`你能告诉我你现在会哪些技能吗？`
（你会发现它能立刻报出技能名字，因为它在 System Prompt 的目录里看到了。）

然后你再输入：
`请加载 code-review 技能，然后告诉我，根据你的技能规范，code review 时最重要的是关注什么？`

**观察重点：**
1. 终端里是否打印出了 `[HOOK] load_skill`？这说明它真的去翻书了。
2. 它的回答是否是基于刚才加载的规范内容。

这就是 Agent 动态获取外部领域知识的核心机制！