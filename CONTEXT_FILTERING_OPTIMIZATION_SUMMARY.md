# 上下文过滤机制优化总结

基于 OpenCode CONTEXT_FILTERING_MECHANISM.md 的实现逻辑，对本项目的上下文过滤机制进行了全面优化。

## 核心改进

### 1. 双标记系统实现

完整实现了 OpenCode 的双标记系统：

```
标记1: CompactionPart (用户消息)
  ↓
  标记压缩触发点

标记2: summary: true (助手消息)
  ↓
  标记摘要完成
```

**工作原理**:
- 压缩时：创建带 CompactionPart 的用户消息
- 摘要时：创建 summary: true 的助手消息
- 过滤时：识别这对标记，在压缩点截断

### 2. 消息流式读取

**新增功能** (session_storage.py):
```python
def stream_messages(session_id: str, batch_size: int = 50):
    """流式获取消息（从新到旧，DESC顺序）"""
```

**特性**:
- 按批次读取，避免内存溢出
- DESC 顺序（从新到旧）
- 批量加载部件，优化性能
- 生成器模式，支持大规模消息

### 3. 增强的过滤算法

**改进前**:
- 基础的遍历和标记
- 简单的注释

**改进后**:
```python
def filter_compacted(messages: List[MessageWithParts]):
    """
    算法步骤（对齐OpenCode实现）：

    第一步：正向遍历（从新到旧）
    - 遍历消息流，将每条消息添加到结果
    - 识别摘要消息（summary: true），记录其父用户消息ID
    - 遇到带CompactionPart的已标记用户消息时停止

    第二步：反转结果
    - 将结果反转为从旧到新的顺序
    - 只包含压缩点之后的消息
    """
```

**新增**:
- 详细的算法文档
- 完整的示例说明
- 流式版本 `filter_compacted_stream()`

### 4. 会话管理器集成

**新增方法** (session_manager.py):
```python
def get_filtered_messages(session_id: str) -> List[MessageWithParts]:
    """获取过滤后的会话消息（只包含最后压缩点之后的消息）"""
```

**优势**:
- 一键获取过滤后的消息
- 自动使用流式读取
- 无需手动调用过滤函数

## 算法可视化

### 过滤前（完整历史）
```
msg-1: user "开始任务"
msg-2: assistant "好的"
msg-3: user "继续"
msg-4: assistant "完成部分"
msg-5: user [CompactionPart] ← 第1次压缩
msg-6: assistant [summary: true]
msg-7: user "下一步"
msg-8: assistant "继续工作"
msg-9: user [CompactionPart] ← 第2次压缩
msg-10: assistant [summary: true]
msg-11: user "最后检查"
msg-12: assistant "完成"
```

### 过滤后（只保留最后压缩点后）
```
msg-10: assistant [summary: true] ← 摘要
msg-9: user [CompactionPart] ← 压缩点
msg-11: user "最后检查"
msg-12: assistant "完成"
```

## 关键特性

### 1. 不删除数据
- 所有消息保留在数据库
- 只在发送给模型时截断
- 完全可逆

### 2. 高效算法
- 单次遍历
- O(n) 时间复杂度
- 流式处理，内存友好

### 3. 精确识别
- 基于双标记系统
- 自动识别压缩点
- 支持多次压缩

## 文件清单

### 修改文件
- `src/session_management/message_filter.py` - 增强过滤算法
  - 详细的算法文档
  - 新增 `filter_compacted_stream()`
  - 完整的示例说明

- `src/session_management/session_storage.py` - 新增流式读取
  - `stream_messages()` - 流式获取消息
  - `_load_parts_batch()` - 批量加载部件

- `src/session_management/session_manager.py` - 集成过滤
  - `get_filtered_messages()` - 一键获取过滤后消息

- `src/session_management/__init__.py` - 更新导出
  - 导出 `filter_compacted_stream`

### 新增文件
- `examples/context_filtering_demo.py` - 完整演示
  - 创建测试消息序列
  - 演示过滤算法
  - 可视化结果

## 使用示例

### 方式1: 直接使用过滤函数
```python
from session_management import filter_compacted

# 获取消息（DESC顺序）
messages = storage.stream_messages(session_id)

# 过滤
filtered = filter_compacted(list(messages))
```

### 方式2: 使用会话管理器
```python
manager = SessionManager(storage, "project-id")

# 一键获取过滤后的消息
filtered = manager.get_filtered_messages(session_id)
```

### 方式3: 流式处理
```python
from session_management import filter_compacted_stream

# 流式读取并过滤
stream = storage.stream_messages(session_id)
filtered = filter_compacted_stream(stream)
```

## 架构对齐

本次优化使 Python 实现与 OpenCode TypeScript 版本完全对齐：

- ✅ 双标记系统（CompactionPart + summary: true）
- ✅ 流式消息读取（DESC顺序）
- ✅ 过滤算法（标记-识别-截断）
- ✅ 批量加载优化
- ✅ 会话管理器集成

## 性能优势

1. **内存效率**: 流式处理，避免一次性加载所有消息
2. **查询优化**: 批量加载部件，减少数据库查询
3. **算法效率**: O(n) 单次遍历
4. **可扩展性**: 支持任意长度的对话历史

## 后续集成

过滤机制已完整实现，可直接用于：
- 主循环中的上下文准备
- LLM 调用前的消息过滤
- 上下文窗口管理

参见 `examples/context_filtering_demo.py` 了解完整使用流程。
