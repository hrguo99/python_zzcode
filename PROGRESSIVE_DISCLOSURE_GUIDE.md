# 渐进式工具披露 - 实现说明

## ✅ 已完成的工作

### 1. 删除错误实现
- ❌ 删除了基于信任管理的渐进式披露系统（src/progressive_disclosure/）
- ❌ 删除了相关的测试文件
- ✅ 恢复了 Orchestrator 到原始状态

### 2. 实现正确的渐进式披露
- ✅ 创建 `src/tool/progressive_disclosure.py` - 核心模块
- ✅ 创建 `src/tool/description_utils.py` - 转换工具
- ✅ 创建 `demo_progressive_disclosure.py` - 演示脚本
- ✅ 修正 `start.py` - 移除错误的参数引用

## 🔐 正确的渐进式披露

### 核心概念

**传统方式**（信息过载）:
```json
[
  {
    "type": "function",
    "function": {
      "name": "read",
      "description": "读取文件内容",
      "parameters": {
        "type": "object",
        "properties": {
          "filePath": {...},
          "offset": {...},
          "limit": {...}
        },
        "required": ["filePath"]
      }
    }
  },
  ... 5个工具 = ~1500 tokens
]
```

**渐进式披露**（按需加载）:
```json
[
  {
    "type": "function",
    "function": {
      "name": "read",
      "description": "读取文件内容"
      // 注意：没有 parameters 字段
    }
  },
  ... 5个工具 = ~250 tokens
]

// 当模型决定调用 read 时，才发送完整schema
{
  "type": "function",
  "function": {
    "name": "read",
    "description": "读取文件内容",
    "parameters": {...完整的schema...}
  }
}
```

## 📂 新增文件

### 核心模块
- `src/tool/progressive_disclosure.py`
  - `ToolDescription` - 工具描述包装器
  - `ProgressiveToolRegistry` - 渐进式工具注册表
  - `calculate_token_savings()` - Token节省计算

### 工具
- `src/tool/description_utils.py`
  - `convert_tool_to_description()` - 转换工具定义
  - `create_tool_summary()` - 创建工具摘要

### 演示
- `demo_progressive_disclosure.py` - 功能演示脚本

## 💡 使用示例

### 基本用法

```python
from tool.progressive_disclosure import ProgressiveToolRegistry

# 创建注册表
registry = ProgressiveToolRegistry()

# 注册工具
registry.register(
    name="read",
    short_description="读取文件内容",
    full_schema={...},  # 完整的JSON Schema
    execute_fn=read_file_func
)

# 列出所有工具的简要描述
simple_tools = registry.list_simple()
# [
#   {"type": "function", "function": {"name": "read", "description": "读取文件内容"}},
#   ...
# ]
# 总计 ~250 tokens (vs 传统方式 ~1500 tokens)

# 按需获取完整schema
full_schema = registry.get_full_schema("read")
# {
#   "type": "function",
#   "function": {
#     "name": "read",
#     "description": "读取文件内容",
#     "parameters": {...完整的JSON Schema...}
#   }
# }
```

### 集成到 AI SDK

```python
async def process_with_progressive_disclosure(user_message):
    # 1. 初始时只发送简要工具列表
    simple_tools = registry.list_simple()
    first_response = await call_llm(
        user_message,
        tools=simple_tools  # ~250 tokens
    )

    # 2. 如果模型想调用工具
    if first_response.tool_calls:
        for tool_call in first_response.tool_calls:
            tool_name = tool_call.name

            # 3. 按需获取完整schema
            full_schema = registry.get_full_schema(tool_name)

            # 4. 发送完整schema给模型确认
            confirmation = await call_llm(
                tool_call,
                tools=[full_schema]
            )

            # 5. 执行工具
            tool = registry.get_tool(tool_name)
            result = await tool.execute_fn(tool_call.input)
```

## 🎯 下一步集成点

要在当前系统中完整实现渐进式披露，需要在以下位置集成：

1. **AI SDK 层** (`src/ai_sdk/`)
   - 修改 LLM 调用逻辑
   - 第一次调用：使用 `list_simple()`
   - 确认调用：使用 `get_full_schema()`

2. **Interpreter Session 层** (`src/interpreter/session.py`)
   - 添加渐进式披露模式
   - 管理工具schema的按需加载

3. **配置选项**
   - 添加环境变量控制开关
   - `PROGRESSIVE_DISCLOSURE=true`

## 📊 性能对比

| 场景 | 传统方式 | 渐进式披露 | 节省 |
|------|---------|------------|------|
| **5个工具，初始** | ~1500 tokens | ~250 tokens | ↓ 83% |
| **10个工具，初始** | ~3000 tokens | ~500 tokens | ↓ 83% |
| **调用1个工具** | +0 tokens | +300 tokens | ↑ 300 |
| **调用3个工具** | +0 tokens | +900 tokens | ↑ 900 |
| **调用5个工具** | +0 tokens | +1500 tokens | ↑ 1500 |

**最佳使用场景**: 工具数量多，但实际调用次数少

## 🚧 当前状态

- ✅ 核心模块已实现
- ✅ 演示脚本可用
- ⚠️ 未深度集成到主系统（需要修改 AI SDK 层）
- ⚠️ `start.py` 已移除错误功能引用

## 🧪 测试功能

运行演示查看效果：
```bash
python demo_progressive_disclosure.py
```

**输出示例**:
```
============================================================
  Token 使用对比
============================================================
工具数量: 5
简化版本: ~250 tokens
完整版本: ~1500 tokens (估计)
节省 tokens: ~1250 tokens
节省比例: 83.3%
```

## 📝 总结

正确的渐进式披露 = **按需加载工具描述**
- 初始：只发送名称+简短描述
- 调用时：才提供完整参数schema
- 目标：减少token使用，避免信息过载

✅ 已实现核心模块，可以单独使用
⚠️ 需要深度集成到 AI SDK 才能在主系统中启用
