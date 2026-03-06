# OpenCode Python - AI 编程助手

一个基于 Python 的 AI 编程助手，支持渐进式工具披露功能。

## ✨ 核心特性

- 🤖 **AI 对话**: 使用 GLM-4-Flash 模型进行智能对话
- 📁 **文件操作**: read, write 文件读写工具
- ⚡ **命令执行**: bash 命令执行工具
- 🔍 **文件搜索**: glob, grep 文件搜索工具
- 🔐 **渐进式工具披露**: 按需加载工具描述，减少80%+初始token使用 ⭐

## 🚀 快速启动

```bash
cd /home/jk-b-047/桌面/code/open_code/python-opencode
export GLM_API_KEY=37eeed8bb86c497b9c09eac4cc807edd.IbUAlqKwOMBf6oZ7
python start.py
```

## 🔐 渐进式工具披露（核心功能）

### 什么是渐进式披露？

**传统方式**：一次性向模型发送所有工具的完整定义
```
初始发送: [tool1完整定义(~300tokens), tool2完整定义(~300tokens), ...]
总计: ~1500 tokens
```

**渐进式披露**：按需加载工具描述
```
初始发送: [tool1简要描述(~50tokens), tool2简要描述(~50tokens), ...]
总计: ~250 tokens (节省 83%)

模型决定调用 tool1 时 → 才发送 tool1 的完整参数schema
```

### 优势对比

| 指标 | 传统方式 | 渐进式披露 | 改善 |
|------|---------|------------|------|
| **初始token** | ~1500 | ~250 | ↓ 83% |
| **信息过载** | 高 | 低 | ✅ |
| **灵活性** | 低 | 高 | ✅ |

### 实现细节

**核心模块**: `src/tool/progressive_disclosure.py`

```python
class ProgressiveToolRegistry:
    def list_simple(self) -> List[Dict]:
        """返回简化工具列表（名称+简短描述）"""

    def get_full_schema(self, tool_name: str) -> Dict:
        """按需获取完整工具schema"""
```

**使用流程**:

```python
# 1. 注册工具
registry.register(
    name="read",
    short_description="读取文件内容",  # 简短描述
    full_schema={...},  # 完整schema
    execute_fn=read_file
)

# 2. 初始时只发送简要描述
simple_tools = registry.list_simple()
send_to_model(simple_tools)  # ~250 tokens

# 3. 模型决定调用工具时，获取完整schema
if model_decides_to_use("read"):
    full_schema = registry.get_full_schema("read")
    send_to_model({
        "name": "read",
        "parameters": full_schema
    })

# 4. 执行工具
tool = registry.get_tool("read")
result = await tool.execute_fn({"filePath": "test.py"})
```

## 📁 项目结构

```
python-opencode/
├── src/                              # 核心代码
│   ├── agent/                        # 智能体管理
│   ├── ai_sdk/                       # AI SDK 集成
│   ├── interpreter/                  # 解释器核心
│   ├── lsp/                          # 语言服务器协议
│   ├── orchestrator/                 # 主编排器
│   ├── processor/                    # 流式处理器
│   ├── session_management/          # 会话管理
│   ├── skill/                        # 技能管理
│   └── tool/                         # 工具框架
│       ├── progressive_disclosure.py # 渐进式披露 ⭐
│       └── description_utils.py       # 描述转换工具
├── tests/                            # 测试文件
├── start.py                          # 启动脚本 ⭐
├── demo_progressive_disclosure.py   # 功能演示 ⭐
├── .env                              # 环境变量配置
└── README.md                         # 本文件
```

## 💡 使用示例

启动后，你可以在交互式界面中输入：

```
💬 你: 帮我查看 src 目录下的文件
💬 你: 读取 .env 文件的内容
💬 你: 创建一个 hello.py 文件
💬 你: 列出所有 Python 测试文件
```

## 🧪 运行演示

```bash
# 查看渐进式披露功能演示
python demo_progressive_disclosure.py
```

**演示内容**:
- 工具注册流程
- 简化版 vs 完整版token对比
- 按需加载schema示例
- 使用示例代码

## ⚙️ 配置说明

在 `.env` 文件中配置：

```bash
# GLM 配置（推荐）
GLM_API_KEY=your_api_key_here
DEFAULT_MODEL=glm-4-flash
DEFAULT_PROVIDER=glm

# 日志配置
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## 📊 性能对比

### 传统方式（完整工具列表）

```
5个工具 × 300 tokens/tool = 1500 tokens
```

### 渐进式披露（按需加载）

```
初始: 5个工具 × 50 tokens/tool = 250 tokens
按需: 只在调用时加载完整schema
```

**节省**: 1250 tokens (83%)

## 🎯 适用场景

渐进式披露特别适合以下场景：

- ✅ **工具数量多**（>5个工具）
- ✅ **参数schema复杂**
- ✅ **需要控制上下文大小**
- ✅ **按使用次数计费的API**
- ✅ **避免信息过载**

## 🚧 开发状态

- ✅ 核心框架完成
- ✅ 渐进式工具披露完成
- ✅ 工具系统完成
- ✅ LSP 集成完成

## 📞 快速命令

```bash
# 启动项目
python start.py

# 运行演示
python demo_progressive_disclosure.py

# 运行测试
python -m pytest tests/ -v
```
