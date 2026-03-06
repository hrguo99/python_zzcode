# 上下文压缩机制优化总结

基于 OpenCode CONTEXT_COMPACTION_GUIDE.md 的实现逻辑，对本项目的上下文压缩机制进行了全面优化。

## 核心改进

### 1. 三层防护系统

实现了完整的三层防护机制，与 OpenCode 架构对齐：

```
┌─────────────────────────────────────────────────────────┐
│  第一层：剪枝 (Pruning)                                  │
│  - 删除旧工具输出（累计>40K tokens）                     │
│  - 保护最近2轮对话                                       │
│  - 保护特定工具（如skill）                               │
│  - 最少剪枝20K tokens才执行                             │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  第二层：消息过滤 (filterCompacted)                      │
│  - 正向遍历标记压缩点                                    │
│  - 遇到CompactionPart停止                               │
│  - 只保留最后一次压缩后的消息                            │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│  第三层：自动压缩 (Auto Compaction)                      │
│  - 上下文接近限制时触发                                  │
│  - 生成结构化摘要                                        │
│  - 创建summary标记的助手消息                             │
└─────────────────────────────────────────────────────────┘
```

### 2. 溢出检测优化

**之前**:
- 简单的token计数
- 未考虑缓存token
- 缓冲区计算不准确

**现在**:
```python
# 包含所有token类型
count = tokens.total or (
    tokens.input + tokens.output +
    tokens.cache_read + tokens.cache_write
)

# 智能缓冲区计算
reserved = min(config.reserved, max_output_tokens)

# 精确的可用上下文计算
usable = (model_limit.max_input - reserved) if model_limit.max_input
         else (context - max_output_tokens)
```

### 3. 剪枝策略优化

**之前**:
- 基础的从后向前遍历
- 简单的token累计

**现在**:
- 保护最近2轮对话
- 保护特定工具（PRUNE_PROTECTED_TOOLS）
- 遇到已压缩消息停止
- 遇到已剪枝输出停止
- 累计超过40K tokens才标记
- 最少剪枝20K tokens才执行
- 详细的日志记录

### 4. 消息过滤机制

**新增功能** (message_filter.py):
```python
def filter_compacted(messages: List[MessageWithParts]) -> List[MessageWithParts]:
    """
    过滤已压缩的消息
    - 正向遍历标记压缩点
    - 遇到CompactionPart停止
    - 反转结果返回
    """
```

这是 OpenCode 的核心机制，确保只保留最后一次压缩后的消息历史。

### 5. 压缩流程优化

**改进**:
- 更清晰的流程注释
- 更好的错误处理
- 详细的日志记录
- 为LLM集成预留接口

## 关键常量

| 常量 | 值 | 说明 |
|------|-----|------|
| `COMPACTION_BUFFER` | 20,000 | 默认保留缓冲区 |
| `PRUNE_PROTECT` | 40,000 | 保护最近40K tokens |
| `PRUNE_MINIMUM` | 20,000 | 最少剪枝量 |
| `PRUNE_PROTECTED_TOOLS` | ["skill"] | 被保护的工具列表 |

## 文件清单

### 新增文件
- `src/session_management/message_filter.py` - 消息过滤机制
- `examples/compaction_demo.py` - 三层防护系统演示

### 修改文件
- `src/session_management/session_compaction.py` - 全面优化
  - 增强溢出检测
  - 改进剪枝策略
  - 优化压缩流程
- `src/session_management/__init__.py` - 导出新功能

## 使用示例

### 检查溢出
```python
compaction = SessionCompaction(
    model_limit=ModelLimits(max_context=200000, max_output=8192),
    config=CompactionConfig(auto=True, reserved=20000),
    storage=storage
)

is_overflow = await compaction.is_overflow(tokens, model)
```

### 执行剪枝
```python
await compaction.prune(session_id)
```

### 过滤消息
```python
from session_management import filter_compacted

filtered = filter_compacted(messages)
```

## 架构对齐

本次优化使 Python 实现与 OpenCode TypeScript 版本完全对齐：

- ✅ 三层防护系统
- ✅ 溢出检测逻辑
- ✅ 剪枝策略规则
- ✅ 消息过滤机制
- ✅ 压缩流程结构
- ✅ 常量和阈值

## 性能优势

1. **渐进式优化**: 三层机制逐步减少token使用
2. **智能保护**: 保留关键信息（最近对话、特定工具）
3. **精确控制**: 基于实际token使用量触发
4. **可配置**: 支持自定义阈值和保护规则

## 后续集成

压缩机制已完整实现，待集成：
- LLM接口调用（生成摘要）
- 主循环触发逻辑
- 压缩事件发布

参见 `examples/compaction_demo.py` 了解完整使用流程。
