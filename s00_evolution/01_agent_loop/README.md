# 第1部分：Agent Loop (智能体主循环引擎)

## 核心比喻：大厨在后厨做菜（The Chef's Loop）

想象一下大厨在后厨做菜的过程，其实这就是一个标准的 **Agent Loop**：
1. **输入 (Input)**：服务员递过来一张点菜单：“客人要一份番茄炒蛋，少放盐”。
2. **思考 (Thought)**：大厨看了菜单，脑子里盘算：“我需要先拿番茄和鸡蛋，然后开火，少放盐”。（对应大模型处理上下文并决定下一步动作）
3. **行动 (Action)**：大厨走到冰箱拿食材，走到灶台开火。（对应 Agent 决定调用 `get_weather` 或 `read_file` 工具）
4. **观察 (Observation)**：大厨发现冰箱里没番茄了。（对应工具执行后返回的结果，被塞回给大模型）
5. **再次思考 (Thought)**：大厨重新盘算：“没有番茄了，我得告诉服务员换菜，或者去隔壁借”。
6. **循环 (Loop)**：以上 2-4 步不断循环，直到大厨把菜做出来端上桌，或者明确告诉服务员“做不了”。

## 在代码里长什么样？

在 Claude Code / OpenHarness 中，这对应着一个经典的 `while True` 死循环（或者叫 Tool-Call Cycle）：

```python
while True:
    1. 把所有对话历史发给大模型 (Thought)
    2. 大模型返回结果
    3. 如果模型要求调用工具：
        - 执行本地代码 (Action)
        - 获取工具结果 (Observation)
        - 将结果追加到对话历史中
        - continue (继续下一轮循环，让模型看着结果继续想)
    4. 如果模型直接返回了纯文本：
        - 说明任务完成了 (或者失败放弃了)
        - break (打破循环，输出给用户)
```

## 学习指南

在当前目录的 `code_annotated.py` 中，我为你实现了一个**极简且可交互的 Agent Loop**。
它虽然只有几十行代码，但完美展示了 OpenHarness 引擎最核心的“思考->行动->观察”循环机制。

**如何运行：**
在终端中执行：
```bash
conda activate harness
python 01_agent_loop/code_annotated.py
```