# Orchestrator 模块

## 概述

Orchestrator 模块实现了项目流程规划.md 中描述的完整工作流程，将 `ai_sdk`、`session_management`、`processor`、`agent`、`tool` 等模块串联起来。

## 架构设计

### 模块依赖关系

```
orchestrator (编排层)
    ├── parser (输入解析)
    ├── command_handler (命令处理)
    ├── agent_switcher (智能体切换)
    └── orchestrator (主编排器)
            ├── interpreter (高级集成层)
            │   ├── ai_sdk (LLM 抽象)
            │   ├── session_management (会话管理)
            │   └── processor (流式处理)
            ├── agent (智能体系统)
            └── tool (工具系统)
```

## 工作流程

### 1. 输入与解析阶段

**Parser** 检测用户输入前缀：
- `/` 开头 → 命令处理
- `@` 开头 → 智能体切换
- 无前缀 → 普通消息处理

### 2. 分流处理

#### 命令处理流程
```
用户输入 "/help"
  → Parser 识别为 COMMAND
  → CommandHandler 查询命令表
  → 执行对应处理函数
  → 返回结果
```

#### 智能体切换流程
```
用户输入 "@coder"
  → Parser 识别为 AGENT_SWITCH
  → AgentSwitcher 查询智能体配置
  → 切换当前智能体
  → 返回确认消息
```

#### 普通消息处理流程
```
用户输入 "你好"
  → Parser 识别为 NORMAL
  → 进入主循环
```

### 3. 主循环处理（普通消息）

```
1. 会话管理
   - 获取/创建会话
   - 存储用户消息

2. 准备阶段
   - 获取历史消息
   - 获取 Agent 配置
   - 过滤可用工具

3. AI SDK 调用
   - 通过 Interpreter 创建会话
   - 调用 Processor 处理流式响应
   - 处理工具调用

4. 结果处理
   - 存储助手消息
   - 返回最终结果
```

## 核心组件

### InputParser

```python
from orchestrator import InputParser, InputType

parser = InputParser()
input_type, content = parser.parse("/help")
# input_type: InputType.COMMAND
# content: "help"
```

### CommandHandler

```python
from orchestrator import CommandHandler

handler = CommandHandler()

async def help_cmd(args: str) -> str:
    return "帮助信息"

handler.register("help", help_cmd)
result = await handler.execute("help")
```

### AgentSwitcher

```python
from orchestrator import AgentSwitcher
from session_management import AgentInfo

switcher = AgentSwitcher()
agent = AgentInfo(name="coder", mode="code")
switcher.register("coder", agent)

agent, msg = await switcher.switch("coder")
```

### Orchestrator

```python
from orchestrator import Orchestrator
from interpreter import InterpreterConfig

config = InterpreterConfig(
    provider="ollama",
    model="llama3.2",
)

async with Orchestrator(config=config) as orch:
    # 注册命令
    orch.register_command("help", help_handler)

    # 注册智能体
    orch.register_agent("coder", coder_agent)

    # 注册工具
    orch.register_tool("read_file", read_file_tool)

    # 处理输入
    async for event in orch.process("你好"):
        print(event)
```

## 使用示例

参见 `orchestrator_demo.py` 文件。

## 与现有模块的集成

- **interpreter**: 提供高级集成接口
- **ai_sdk**: 处理 LLM 调用
- **session_management**: 管理会话状态
- **processor**: 处理流式响应和工具调用
- **agent**: 提供智能体配置
- **tool**: 提供工具执行能力
