# 02. Tools 工具抽象与编排

在本模块中，我们将学习如何像 OpenHarness 那样，通过抽象层来管理 Agent 的工具（Tools）。

## 核心概念

1. **`BaseTool` (工具抽象基类)**
   每个工具都必须继承自 `BaseTool`，这相当于签署了一份契约。它强制规定了每个工具必须有：
   - `name` 和 `description`
   - `input_model`：使用 `Pydantic` 进行强类型参数校验。
   - `to_api_schema()`：负责将 Pydantic 模型自动翻译为大模型（OpenAI/Anthropic）能够识别的 JSON Schema。
   - `execute()`：工具的实际执行逻辑。

2. **`ToolRegistry` (工具注册中心)**
   大模型并不是天生知道系统里有什么工具的，而是通过注册中心统一管理的。
   - 所有的工具实例化后放入 `ToolRegistry`。
   - 引擎启动时，调用 `to_api_tools()`，把挂在墙上的工具“说明书”打包发给大模型。
   - 大模型决定调用某个工具时，引擎通过 `get_tool(name)` 取出工具实例，拦截、校验并执行。

3. **`BashTool` (终端工具实战)**
   我们实现了一个简化版的 `BashTool`，它可以让大模型像程序员一样在本地终端执行命令。
   它内置了异常捕获和 Pydantic 参数验证，保证大模型传来的命令能被安全解析。

## 运行测试

在虚拟环境（如 `harness`）中运行：
```bash
conda activate harness
python code_annotated.py
```

然后尝试向 Agent 下达终端指令，例如：
- “帮我看一下当前目录有哪些文件？” 
- “用 python 帮我算一下 2的10次方”。

你会看到 Agent 是如何思考、翻看工具说明书、调用 `bash` 工具并获得结果反馈的完整闭环。
