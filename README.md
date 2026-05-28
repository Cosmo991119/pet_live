# Agent Demo

这是一个中文教学向的 ReAct Agent + RAG demo。它演示了一个最小可运行的智能体闭环：

用户提问 -> LLM 判断是否调用工具 -> 工具返回结果 -> LLM 汇总回答。

项目还包含多轮历史、简单长期记忆、本地知识库检索、OpenAI GPT LLM 适配，以及一个未默认启用的 Anthropic 适配层。

## 主要入口

- `chat.py`：命令行聊天入口，适合手动体验 agent。
- `main.py`：批量测试入口，包含计算、天气、多轮记忆示例。
- `api.py`：FastAPI 网页/API 入口，包含虚拟宠物控制台和图片风格转换接口。

运行聊天：

```bash
python3 chat.py
```

运行演示：

```bash
python3 main.py
```

运行网页控制台：

```bash
uvicorn api:app --reload
```

打开 `http://127.0.0.1:8000`。如果要使用真实 LLM 或 Image Style 功能，需要在 `.env` 中配置 OpenAI API：

运行桌面宠物 + Telegram 产品链路：

```bash
python3 run_pet_agent.py
```

这个入口会同时启动 FastAPI 和 Telegram bot，日志分别写到
`logs/fastapi.log` 和 `logs/telegram_bot.log`。单独运行 `uvicorn ...` 或
`python3 telegram_bot.py` 更适合调试。

```bash
OPENAI_API_KEY=...
OPENAI_LLM_MODEL=gpt-5.5
OPENAI_IMAGE_MODEL=gpt-image-1.5
```

`OPENAI_LLM_MODEL` 可省略，默认使用 `gpt-5.5`。`OPENAI_IMAGE_MODEL` 可省略，默认使用 `gpt-image-1.5`。页面和 Telegram 会把上传的参考图和额外要求提交到 `/image-style`，后端会保留原图服装、配色、主体结构、姿势和主要装饰，并固定转换成复古 16/32-bit 像素 Q 版桌宠头像/精灵风。生成结果优先透明底，强调清晰像素块和干净色块，避免明显反光、脏光晕和复杂背景，保存到 `static/generated/`。

## 核心模块

- `agent.py`：核心 ReAct 循环。维护对话历史，调用 LLM，让 LLM 选择工具，再把工具结果写回消息流。
- `tools.py`：工具注册和执行分发。包含知识库搜索、天气、mock web search、计算、时间、保存 note、读取 note。
- `rag.py`：本地 RAG。读取 `knowledge_base/*.txt`，切 chunk，用 `sentence-transformers` 向量化，存入 ChromaDB。
- `prompts.py`：系统提示词。规定中文回答、数学必须用工具、公司政策类问题先查知识库等。
- `llm_openai.py`：OpenAI GPT API 适配层，把 OpenAI tool call 格式转成项目内部使用的 Anthropic-like 格式。
- `llm_anthropic.py`：Anthropic API 适配层，目前不是默认路径。
- `image_style_agent.py`：图片风格转换服务。读取上传图片，调用 OpenAI GPT Image 模型，保存生成图。
- `image_styles/`：图片风格注册表。每个风格独立维护 prompt，前端通过 `/image-styles` 动态加载风格列表。
- `notes.json`：简单持久化记忆文件。
- `knowledge_base/`：本地知识库原始资料。
- `chroma_db/`：ChromaDB 持久化数据目录。

## 当前默认行为

`agent.py` 中 `USE_REAL_LLM = True`，所以默认走 `llm_openai.py`。

需要在 `.env` 中配置：

```bash
OPENAI_API_KEY=...
```

如果要切换到 mock LLM，可在 `agent.py` 中把 `USE_REAL_LLM` 改为 `False`。

如果要切换 Anthropic，需要把 `agent.py` 中的 LLM 调用改为 `llm_anthropic.anthropic_llm_call`，并配置：

```bash
ANTHROPIC_API_KEY=...
```

## 数据流

1. `chat.py` 或 `main.py` 调用 `run_agent(...)`。
2. `run_agent` 把用户问题加入 `messages`。
3. 每轮调用前注入 `ASSISTANT_PROMPT`。
4. LLM 返回 `end_turn` 或 `tool_use`。
5. 如果是 `tool_use`，`agent.py` 通过 `execute_tool(...)` 调用对应工具。
6. 工具结果以 `tool_result` 形式写回历史。
7. LLM 读取工具结果并输出最终回答。

## 工具扩展方式

添加新工具通常需要三步：

1. 在 `tools.py` 的 `TOOLS` 列表中添加工具 schema。
2. 在 `tools.py` 中实现工具函数。
3. 在 `execute_tool(...)` 中添加 dispatch 分支。

工具定义格式大致如下：

```python
{
    "name": "tool_name",
    "description": "给 LLM 看的工具说明",
    "input_schema": {
        "type": "object",
        "properties": {
            "param": {"type": "string", "description": "参数说明"}
        },
        "required": ["param"]
    }
}
```

## RAG 知识库

`rag.py` 当前只读取 `knowledge_base` 目录下的 `.txt` 文件。

重建知识库：

```bash
python3 rag.py
```

当前知识库包含公司政策、技术 FAQ、RAG 学习资料等文本。目录中的 PDF 文件暂时不会被 `build_knowledge_base()` 读取。

## 已知风险和改进点

- `tools.py` 的 `calculate()` 使用 `eval()`，只适合教学演示，生产环境应替换为安全表达式解析器。
- 项目没有 `requirements.txt` 或 `pyproject.toml`，新环境复现依赖需要从 import 反推。
- `chat.py` 只检查 `chroma_db` 目录是否存在，不检查 Chroma collection 是否有效。
- `rag.py` 不处理 PDF，虽然 `knowledge_base` 中已有 PDF 文件。
- `.github/copilot-instructions.md` 仍偏向描述 mock LLM，而当前代码默认使用真实 POE LLM，文档和实现有轻微漂移。

## 主要依赖

从源码 import 反推，项目至少需要：

- `openai`
- `python-dotenv`
- `requests`
- `chromadb`
- `sentence-transformers`
- `anthropic`，仅当使用 `llm_anthropic.py` 时需要

## 项目定位

这个项目更像一个学习和实验用的 agent 骨架，而不是生产级框架。它的价值在于结构清楚、概念完整，适合继续围绕工具调用、RAG、记忆、LLM provider 切换和安全性逐步加固。
