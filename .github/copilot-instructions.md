# AI 智能体开发指南

## 架构概述
本项目展示了一个使用 ReAct（推理+行动）模式的 AI 智能体系统。分为三个核心层：

- `main.py`：入口点，用于测试智能体处理示例问题
- `agent.py`：核心 ReAct 循环，包含 Mock LLM 决策逻辑
- `tools.py`：工具定义及执行逻辑

数据流：用户查询 → 智能体循环 → LLM 决定是否调用工具 → 获取工具结果 → 整合到对话历史 → 最终回答

## 关键模式

### 工具接口规范
所有工具遵循 `tools.py` 中 `TOOLS` 列表定义的标准结构：
```python
{
    "name": "tool_name",
    "description": "LLM 能理解的工具描述",
    "input_schema": {
        "type": "object",
        "properties": {"param": {"type": "string", "description": "参数说明"}},
        "required": ["param"]
    }
}
```
执行通过 `execute_tool(tool_name, tool_input)` 分派器统一处理。

### Mock 实现
- **搜索**：`MOCK_SEARCH_DB` 字典关键词匹配
- **计算**：使用 `eval()`（演示用，生产环境需安全解析器）
- **LLM 决策**：`mock_llm_call()` 基于消息历史分析模拟 LLM 行为

### 消息格式
遵循 Claude API 的标准格式：
- 用户消息：`{"role": "user", "content": "查询内容"}`
- 助手响应：`{"role": "assistant", "content": [{"type": "tool_use", "name": "工具名", "input": {...}}]}`
- 工具结果：`{"role": "user", "content": [{"type": "tool_result", "content": "结果"}]}`

## 开发工作流

### 测试与调试
- 运行 `python main.py` 进行详细执行跟踪（自动启用 verbose 模式）
- 传递 `verbose=True` 给 `run_agent()` 查看每一步决策过程

### 扩展工具
1. 在 `tools.py` 的 `TOOLS` 列表中添加工具定义
2. 实现对应的处理函数（如 `search_web()`, `calculate()`）
3. 在 `execute_tool()` 的 dispatch 分支中添加执行逻辑

### 集成真实 LLM
在 `agent.py` 中用真实 API 调用替换 `mock_llm_call()`：
```python
# 替换为实际的 Claude API 调用
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    tools=tools,
    messages=messages
)
```

## 项目约定
- 中文注释和字符串用于可读性
- ReAct 循环包含 `max_steps=10` 防止无限循环
- 工具结果通过对话历史传递给 LLM，供后续推理使用
- Mock 实现优先考虑演示效果而非生产级稳定性

## 核心集成点
- **LLM 提供商**：替换 mock 为 Anthropic/Claude API
- **网络搜索**：用真实搜索 API 替换 `MOCK_SEARCH_DB`
- **计算引擎**：用安全表达式解析器替换 `eval()`
- **工具扩展**：按现有模式添加新工具（定义 → 实现 → dispatch）</content>
<parameter name="filePath">/Users/cosmos/agent-demo/.github/copilot-instructions.md