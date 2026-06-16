# Desktop AI Pet Assistant

一只住在桌面上的 AI 宠物助手：它有自己的形象、状态、记忆和关系网络，可以通过 Telegram 与主人日常互动，也可以在本机桌面上以悬浮宠物的形式陪伴主人工作。

这个项目从 ReAct Agent + RAG 教学 demo 演进而来，现在重点展示 AI Agent 应用工程能力：结构化状态、工具调用、长期记忆、Telegram 产品交互、桌面运行时、图片生成资产链路和轻量工作助手。

## 核心能力

### AI 宠物状态系统

- 支持多只宠物，每只宠物有名字、物种、性格、主人称呼、资料补充和形象配置。
- 使用 SQLite 保存宠物、主人、行为事件、行为 session、睡眠 session、状态统计、总结、记忆和助手事项。
- 支持结构化行为事件：吃饭、喝水、便便、玩耍、睡眠开始、睡眠结束。
- 对短时间重复行为做 session 聚合，避免重复刷屏，同时保留原始事件。
- 支持日、周、月统计和宠物风格化总结。
- 低置信度事件只记录，不触发消息。

### 虚拟宠物模拟器

- 虚拟宠物有饥饿、口渴、精力、心情、清洁度、亲密度和睡眠状态。
- 支持主人动作：喂饭、加水、陪玩、摸摸、清洁、哄睡。
- 本地规则推进状态，不依赖 LLM 做随机模拟。
- 主人动作和自然 tick 都可以生成结构化事件，再复用同一套事件处理和消息生成链路。

### Telegram 日常入口

- Telegram 是当前主要的日常交互入口。
- 支持按钮式操作：创建宠物、查看状态、喂饭、加水、陪玩、摸摸、清洁、哄睡、桌面陪伴、小助手等。
- 支持按宠物编辑资料，包括名字、物种、主人称呼、说话风格、性格/行为补充。
- 支持多宠物群聊：普通文本可以触发 GPT 选择 1-2 只宠物回复。
- 支持主人手动设置宠物之间的关系，关系会轻量影响群聊发言和接话。
- 支持主动 tick，宠物可以在主人不操作时自然推进状态并发消息。
- 支持多 owner 基础：通过 Telegram chat id 做 V1 访问边界。

### 形象定制与桌宠资产

- 主人可以在 Telegram 中发送参考图，描述想要的宠物风格。
- 后端生成形象预览，主人确认后才写入角色记录并绑定到指定宠物。
- 确认后的角色会生成 manifest-first 桌宠资产包。
- 资产包包含头像和 GIF 动画，支持 idle、relax、walk left/right、sleep、happy 等基础状态。
- 支持为已确认角色生成一次性 12 张聊天表情包。
- 可选接入 Wan 图生视频和 Cloudflare R2，用于生成更丰富的动作 GIF 素材。

### 本机悬浮桌宠

- 支持 macOS 原生悬浮桌宠运行时。
- 桌宠窗口无边框、置顶、可拖动。
- 支持读取宠物状态并切换动画状态。
- 支持双击摸摸和右键快捷动作。
- Telegram 的“桌面陪伴”按钮可以触发本机桌宠启动。
- 运行控制层会校验 manifest、防止重复启动，并记录启动日志。

### 长期记忆

- 支持 durable pet memories，不把所有聊天日志都默认写成长期记忆。
- 支持记忆类型：
  - `owner_shared`：主人分享给宠物的现实经历。
  - `co_experienced`：主人授权宠物当作共同经历来回忆的陪伴记忆。
  - `pet_milestone`：宠物成长或状态里程碑。
  - `work_companion`：宠物陪主人完成工作任务的记忆。
- 每条记忆可记录参与宠物、情绪、重要性、可见性、召回策略和使用方式。
- Telegram 收到普通照片后，会先追问“发生了什么”，再根据主人解释决定是否保存为共同记忆。
- 敏感记忆需要主人确认，并默认只在主人明确问起时召回。

### 宠物好友与跨 owner 分享

- 一个 owner 可以为自己的宠物生成好友邀请。
- 另一个 owner 可以用自己的宠物接受邀请，形成跨 owner 宠物好友关系。
- 支持主人确认后把消息或记忆分享给好友 owner。
- 支持低频宠物好友日常消息，受冷却时间和概率控制。

### 轻量工作助手

- 宠物可以进入工作形态，帮助主人处理轻量任务。
- 支持事项类型：记事、待办、提醒、闹钟、番茄钟。
- Telegram 支持自然短语：
  - `记一下 ...`
  - `待办 ...`
  - `提醒 10分钟后 ...`
  - `闹钟 16:30 ...`
  - `番茄钟 25 ...`
  - `我的记事`
  - `我的待办`
  - `完成 7`
- 到期提醒由 Telegram 发送给 owner。
- 桌面宠物右键菜单也可以创建同一套助手事项。

## 运行方式

安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

复制环境变量模板：

```bash
cp .env.example .env
```

至少需要配置：

```bash
PET_AGENT_API_URL=http://127.0.0.1:8000
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
OPENAI_API_KEY=...
```

启动本地产品链路：

```bash
python3 run_pet_agent.py
```

这个命令会同时启动 FastAPI 服务和 Telegram bot，日志写入：

```text
logs/fastapi.log
logs/telegram_bot.log
```

如果只想单独调试后端或 bot，也可以分别运行：

```bash
uvicorn api:app --reload
python3 telegram_bot.py
```

启动本机桌宠：

```bash
python3 launch_desktop_pet.py --pet-id 2
```

也可以省略 `--pet-id`，默认选择本地第一只虚拟宠物。

## 关键配置

### LLM 与图片生成

```bash
OPENAI_API_KEY=...
OPENAI_LLM_MODEL=gpt-5.5
OPENAI_IMAGE_MODEL=gpt-image-1.5
PET_AGENT_USE_LLM=false
```

`PET_AGENT_USE_LLM=false` 时，部分宠物消息会走本地 fallback，适合本地调试。需要真实 GPT 群聊或生成式文案时再开启。

### Telegram

```bash
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
TELEGRAM_ALLOWED_OWNER_CHAT_IDS=
TELEGRAM_DEFAULT_OWNER_CHAT_ID=
TELEGRAM_DEFAULT_OWNER_DISPLAY_NAME=Default Owner
```

`TELEGRAM_ALLOWED_OWNER_CHAT_IDS` 为空时偏本地单用户 demo；填写后启用 V1 owner-scoped 使用边界。

### 主动 tick

```bash
PET_AGENT_PROACTIVE_TICKS_ENABLED=true
PET_AGENT_PROACTIVE_TICK_INTERVAL_SECONDS=600
PET_AGENT_PROACTIVE_TICK_MINUTES=10
```

默认每 600 秒推进 10 分钟虚拟时间。若产生新的宠物事件消息，会发送给对应 owner chat。

### Wan 动作 GIF 与 R2

```bash
DESKTOP_PET_ASSET_PROVIDER=wan
DASHSCOPE_API_KEY=...
WAN_VIDEO_MODEL=wan2.2-kf2v-flash
WAN_VIDEO_RESOLUTION=720P
WAN_PROMPT_EXTEND=true
```

Wan 服务无法直接读取本机文件。可选两种方式提供公网素材：

```bash
PET_AGENT_PUBLIC_BASE_URL=https://your-public-domain
```

或配置 Cloudflare R2：

```bash
CLOUDFLARE_R2_ACCOUNT_ID=...
CLOUDFLARE_R2_ACCESS_KEY_ID=...
CLOUDFLARE_R2_SECRET_ACCESS_KEY=...
CLOUDFLARE_R2_BUCKET=...
CLOUDFLARE_R2_PUBLIC_BASE_URL=...
CLOUDFLARE_R2_KEY_PREFIX=agent-demo/wan
```

密钥只应保存在本地 `.env`，不要提交到仓库。

## 主要模块

- `api.py`：FastAPI 后端入口，暴露宠物、事件、状态、记忆、角色、助手事项等 API。
- `telegram_bot.py`：Telegram 产品入口，包含按钮交互、宠物群聊、形象定制、记忆、好友和小助手流程。
- `pet_db.py`：SQLite schema、迁移和数据访问层。
- `pet_simulator.py`：虚拟宠物状态模拟器。
- `virtual_pet_service.py`：虚拟宠物状态持久化和事件处理桥接。
- `pet_event_service.py`：结构化宠物事件处理。
- `pet_message_agent.py`：实时宠物消息生成。
- `pet_summary_agent.py`：周期总结生成。
- `pet_status_service.py`：宠物状态格式化和动作回复。
- `character_agent.py`：角色确认、事件图、表情包和桌宠资产生成。
- `desktop_pet_assets.py`：manifest-first 桌宠资产包构建。
- `desktop_pet_mac.swift`：macOS 原生悬浮桌宠运行时。
- `launch_desktop_pet.py`：桌宠启动器。
- `pet_runtime_controller.py`：本地运行控制层。
- `pet_work_assistant.py`：轻量文本总结和待办提取。
- `llm_openai.py` / `llm_anthropic.py`：LLM provider 适配。
- `agent.py`、`tools.py`、`rag.py`：早期 ReAct/RAG demo 和工具调用基础。

## 数据流概览

```text
Telegram / Desktop action
-> FastAPI API
-> SQLite fact store
-> virtual pet state or event session update
-> message / summary / memory / assistant service
-> Telegram reply or local desktop pet reaction
```

形象定制链路：

```text
Telegram reference image
-> image preview generation
-> owner confirms
-> character record
-> desktop asset manifest
-> pet profile binding
-> desktop companion runtime
```

## 测试

运行全部 Python 测试：

```bash
python3 -m pytest
```

运行重点测试示例：

```bash
python3 -m pytest tests/test_pet_memories.py
python3 -m pytest tests/test_pet_friendships.py
python3 -m pytest tests/test_telegram_pet_onboarding.py
python3 -m pytest tests/test_pet_work_items.py
python3 -m pytest tests/test_desktop_pet_assets.py
```

## 当前限制

- 当前桌面悬浮宠物主要是本机 macOS 路径；真正面向远程 owner 的跨平台桌面客户端仍是后续方向。
- 高级动作素材生成可能依赖外部图片/视频模型额度；基础桌宠形象和已生成素材仍可继续使用。
- 早期 ReAct/RAG demo 仍保留在项目中，但当前产品主线已经转向桌面 AI 宠物助手。
- 本项目是学习和作品集导向的本地产品原型，不是生产级多租户服务。

## 项目定位

这个项目展示的是一个从“会调用工具的 Agent”逐步长成“有形象、有记忆、有状态、有日常入口的 AI 应用”的过程。

它的重点不只是让 LLM 回复一句话，而是把事实状态、用户动作、长期记忆、图片生成、桌面运行时和 Telegram 交互串成一个可以持续使用的产品闭环。
