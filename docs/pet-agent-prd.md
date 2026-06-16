# Pet Agent PRD

## 1. 项目目标

本项目的目标是把当前 ReAct Agent + RAG demo 升级为一个应用型 AI Agent 作品：桌面 AI 宠物助手。

它的长期产品形态不是一个普通聊天机器人，也不只是宠物行为播报系统，而是一只在主人桌面上活动、陪伴、记得共同经历，并能帮主人工作的形象化 AI 工具助手。

工作辅助不是另一个被塞进产品里的通用助理人格，而是主人的宠物化身进入工作形态。当前产品语言里，这个宠物化身可以被明确理解为“自己的宠物化身龙虾”：平时是陪伴主人的龙虾，工作时仍然是同一只龙虾，只是切换成能使用总结、待办、提醒、检索和项目工具的工作姿态。

系统底层接收宠物的实时结构化行为事件，记录事实数据，结合近期行为上下文生成讨喜的宠物口吻消息，并基于日、周、月统计生成状态总结。这个行为与状态系统是“宠物活着”的基础。后续产品层会扩展到桌面宠物运动、陪伴回忆、主人工作上下文、工具调用和主动提醒，让宠物从“会表达状态”升级为“陪主人工作和生活的小助手”。

这个项目服务于学习和求职目标：训练 AI Agent 应用工程能力，包括 tool calling、结构化数据、RAG、LLM 输出约束、统计分析、通知抽象、Prompt 版本管理和工程化边界。

## 1.1 产品北极星

一句话定位：

```text
一只住在桌面上的 AI 宠物化身龙虾：它会活动、会陪伴、记得和主人的共同经历，也能以同一个宠物身份进入工作形态，帮主人完成轻量工作任务。
```

产品体验分三层：

- 形象层：宠物有可视化形象，能在桌面上运动、停留、互动，而不只存在于聊天窗口或 Telegram 消息里。
- 定制层：主人可以定制宠物形象，包括上传参考图、选择风格、生成角色形象，并让这个形象成为后续桌面陪伴和工作助手的统一外观。
- 成长定制层：宠物上线后，主人可以继续定制表情、动作和情绪包，让宠物从“生成出来的形象”逐步变成“被主人养出来的伙伴”。
- 记忆层：宠物能沉淀主人陪伴它的回忆，包括日常互动、照顾记录、共同完成的事情和阶段性变化。
- 助手层：宠物可以作为形象化 AI 工具入口，帮助主人做工作中的轻量任务，例如提醒、总结、检索、草拟、整理待办和调用工具。这个助手层不是第二个角色，而是同一只宠物化身龙虾的工作形态。
- 日常沟通层：Telegram 是主人离开桌面后的日常交流窗口，用于查看状态、照顾宠物、接收宠物主动消息、继续轻量陪伴，而不是只作为调试通知渠道。

底层原则：

- 程序和数据库负责事实、状态、时间线和工具执行。
- LLM 负责表达、解释、陪伴感和自然语言协作。
- 宠物形象不是皮肤，也不是一次性生成图片，而是用户和 AI 工具之间长期存在的情感界面。
- 工作辅助必须保持同一个宠物身份、同一套关系和同一条记忆线。切换到工作形态时可以改变姿态、表情、工具栏和语气密度，但不能变成另一个无关的生产力机器人。
- 定制形象确认后，应优先开放基础桌面陪伴。初始只需要安静态和桌面闲逛，完整动作和表情可以在后台逐步生成、逐步解锁。
- 桌面端负责强存在感和工作陪伴，Telegram 负责跨设备、低摩擦、随时可达的日常交流。

## 2. 第一版范围

第一版聚焦核心闭环：

```text
HTTP API 接收结构化行为事件
-> 校验事件
-> 写入 SQLite
-> 聚合行为 session 或睡眠 session
-> 查询当前上下文和历史基线
-> LLM 生成结构化俏皮话
-> ConsoleNotifier 打印调试消息
-> API 返回结果
```

第一版要做：

- 底层支持多只宠物。Telegram 对话应按“主人和所有宠物的群聊”来设计，宠物状态消息都进入同一个陪伴上下文；具体设置资料、生成形象和主动照顾按钮再指定某一只互动对象。
- 使用 SQLite 保存结构化行为数据。
- 保留当前 ChromaDB RAG，后续扩充为宠物护理知识库。
- 使用 FastAPI 暴露事件输入和统计总结接口。
- 用命令行输出作为第一版通知渠道。
- 支持日、周、月统计 API。
- 支持用户主动请求日、周、月总结。
- 支持宠物性格和主人称呼影响文案风格。

第一版暂不做：

- Telegram 接入。
- 完整前端图表页面。
- 多用户账号系统。
- 原始坐标到行为的识别算法。
- 完整事件纠错流程。
- 医疗诊断、用药建议或治疗方案。

## 3. 用户体验

核心体验是让主人感觉宠物在用自己的性格说话，而不是系统在冷冰冰播报数据。

实时消息应该：

- 像宠物在对主人说话。
- 讨喜、亲近、有性格。
- 数据在后台驱动判断，默认不直接报数字。
- 只有轻微提醒或总结场景才适量展示数据。
- 禁止医疗诊断。

示例：

```text
妈，我刚刚去喝水啦，水碗边今天有点像我的快乐小基地。
```

周期总结应该：

- 比实时消息更清楚、更有信息密度。
- 轻度保留宠物性格。
- 可以适量引用统计结果。
- 给温和观察提醒，但不做诊断。

## 4. 输入事件模型

第一版输入是结构化行为事件，不处理原始坐标。

示例：

```json
{
  "pet_id": 1,
  "behavior": "drink",
  "location_name": "水碗",
  "timestamp": "2026-04-29T20:30:00+08:00",
  "confidence": 0.92
}
```

第一版行为枚举：

```text
eat
drink
poop
sleep_start
sleep_end
```

其中：

- `eat`、`drink`、`poop` 是可聚合的瞬时行为。
- `sleep_start`、`sleep_end` 是持续状态边界事件。

## 5. 事件处理规则

事件处理顺序：

```text
接收事件
-> 字段校验
-> 行为枚举校验
-> 置信度判断
-> 写入 events
-> 聚合 session
-> 决定是否生成消息
-> 通知输出
```

置信度规则：

- `confidence >= 0.7`：允许生成俏皮话和通知。
- `confidence < 0.7`：只记录事件，不生成俏皮话，不通知，事件状态标记为 `low_confidence`。

事件状态预留：

```text
confirmed
low_confidence
duplicate
ignored
corrected
```

第一版默认使用 `confirmed`，不做完整纠错功能。

## 6. 行为 Session 聚合

短时间内的重复行为不能粗暴去重。系统应保留所有原始事件，同时聚合为行为 session。

原则：

- `events` 保存所有原始事件。
- `behavior_sessions` 聚合 eat、drink、poop。
- 通知节流，同一 session 不重复刷屏。
- 统计按 session 计数。
- LLM 可以使用 `raw_event_count` 和持续时间作为后台信号。

推荐窗口：

```python
SESSION_WINDOWS = {
    "eat": 10 * 60,
    "drink": 5 * 60,
    "poop": 15 * 60,
}
```

第一版通知时机：

- 新 session 创建时触发一次实时消息。
- 同一 session 内后续事件只更新 session，不重复通知。

实时消息内容仍要结合数据库上下文，不是固定模板。

## 7. 睡眠 Session

睡眠使用持续状态建模：

```text
sleep_start
sleep_end
```

规则层负责睡眠状态一致性，不交给 LLM 判断。

规则：

- 收到 `sleep_start`，如果没有未结束睡眠段，则创建 sleep session。
- 收到 `sleep_start`，如果已有未结束睡眠段，则记录 anomaly。
- 收到 `sleep_end`，如果存在未结束 sleep session，则关闭并计算时长。
- 收到 `sleep_end`，如果不存在未结束 sleep session，则记录 orphan anomaly。

## 8. 数据模型

第一版使用 SQLite。ChromaDB 继续保留给知识库检索，不用于行为统计。

### pets

```text
id
name
species
personality
owner_call_name
profile_json
created_at
```

说明：

- `species`：`cat`、`dog`、`other`。
- `personality`：预设性格。
- `owner_call_name`：宠物对主人的称呼，如“妈”“爸爸”“姐姐”。
- `profile_json`：扩展资料，如品种、生日、体重、风格偏好。

### events

```text
id
pet_id
behavior
location_name
occurred_at
confidence
status
raw_payload
created_at
```

### behavior_sessions

```text
id
pet_id
behavior
location_name
start_time
end_time
raw_event_count
status
created_at
updated_at
```

### sleep_sessions

```text
id
pet_id
start_event_id
end_event_id
start_time
end_time
duration_minutes
status
created_at
updated_at
```

### anomalies

```text
id
pet_id
event_id
anomaly_type
description
created_at
```

### event_messages

```text
id
event_id
session_id
pet_id
message
severity
facts_used_json
internal_signal
model_name
prompt_version
created_at
```

### summaries

```text
id
pet_id
range_type
start_date
end_date
stats_json
summary_json
model_name
prompt_version
created_at
```

## 9. 宠物性格

第一版使用预设性格，不做完全自由输入。

预设：

```text
sweet      甜甜撒娇型
cool       傲娇高冷型
energetic  活泼话痨型
gentle     温柔乖巧型
```

实时消息强烈受性格影响。

周期总结轻度受性格影响，优先保持清晰和可读性。

`profile_json` 预留风格偏好：

```json
{
  "style_preferences": {
    "avoid_words": ["铲屎官"],
    "verbosity": "short",
    "emoji": false
  }
}
```

第一版默认：

- 不用 emoji。
- 不使用夸张网络梗。
- 不直接报太多数字。
- 不做医疗诊断。

## 10. LLM 使用方式

实时俏皮话由 LLM 生成，不使用固定模板作为主路径。

但 LLM 必须基于数据库上下文，不能凭空发挥。

实时消息上下文：

```text
current_session
current_event
today_stats
last_same_behavior_or_session
historical_baseline
pet personality
owner_call_name
```

输出要求：

- 数据在后台判断，前台用宠物口吻表达。
- 默认不直接输出数字。
- 可以表达轻微趋势，如“今天好像格外爱喝水”。
- 禁止说没有依据的全局比较，如“超过 99% 的猫咪”。
- 禁止医疗诊断。

结构化输出：

```json
{
  "message": "妈，我刚刚去喝水啦，水碗边今天有点像我的快乐小基地。",
  "severity": "normal",
  "facts_used": ["current_session", "today_stats", "historical_baseline"],
  "internal_signal": "frequent_today"
}
```

`internal_signal` 是系统调试字段，不一定展示给用户。

LLM 失败时，应使用降级模板返回同样结构。

## 11. Prompt 版本管理

第一版就记录 prompt 版本，但不做复杂管理系统。

建议常量：

```python
PET_EVENT_MESSAGE_PROMPT_VERSION = "pet_event_message_v1"
PET_SUMMARY_PROMPT_VERSION = "pet_summary_v1"
```

写入：

- `event_messages.prompt_version`
- `summaries.prompt_version`

同时记录 `model_name`，方便后续排查和对比。

## 12. 统计和图表

第一版先做统计 API，再做极简图表页面。

核心指标：

```text
eat
- 每日吃饭 session 次数
- 吃饭时间分布

drink
- 每日喝水 session 次数
- 两次喝水间隔

poop
- 每日排便 session 次数
- 距离上次排便多久

sleep
- 每日睡眠总时长
- 睡眠开始/结束时间趋势
```

推荐 API：

```text
GET /pets/{pet_id}/stats?range=day|week|month
```

第一版统计从 `behavior_sessions` 和 `sleep_sessions` 即时聚合，不新增 `daily_stats` 预聚合表。等主链路完成、数据量变大或查询变慢后，再把 `daily_stats` 作为性能优化引入。

示例返回：

```json
{
  "pet_id": 1,
  "range": "week",
  "days": [
    {
      "date": "2026-04-23",
      "eat_count": 2,
      "drink_count": 5,
      "poop_count": 1,
      "sleep_minutes": 480
    }
  ]
}
```

## 13. 周期总结

第一版支持用户主动请求总结，自动日报/周报后置。

推荐 API：

```text
GET /pets/{pet_id}/summary?range=day|week|month
```

总结输入：

- 后端聚合好的 stats JSON。
- 不把原始事件列表直接丢给 LLM。

原因：

- 事实计算交给程序。
- LLM 负责解释、表达、温和提醒。
- 避免 LLM 自己算错。

总结输出为结构化 JSON：

```json
{
  "summary": "糯米这周整体很乖，吃饭和睡觉都比较稳定。",
  "alerts": [
    {
      "level": "info",
      "message": "有两天喝水稍微少一点，可以继续留意水碗。"
    }
  ],
  "suggestions": [
    "保持水碗清洁，晚点观察它是否继续主动喝水。"
  ]
}
```

安全边界：

- 可以描述趋势。
- 可以给温和观察提醒。
- 可以建议异常持续时咨询兽医。
- 不可以诊断疾病。
- 不可以给药物或治疗建议。

## 14. 通知层

第一版暂不接 Telegram。

通知设计采用接口抽象：

```python
class Notifier:
    def send(self, pet_id: int, message: str):
        ...
```

第一版实现：

```python
class ConsoleNotifier:
    def send(self, pet_id: int, message: str):
        print(f"[Pet {pet_id}] {message}")
```

后续实现：

```python
class TelegramNotifier:
    def send(self, pet_id: int, message: str):
        ...
```

这样可以先在命令行调试实时事件，后续无痛替换为 Telegram Bot API。

## 15. API 草案

第一版推荐新增 `api.py`，保留 `chat.py` 学习入口。

推荐接口：

```text
POST /pets
GET /pets
POST /events
GET /pets/{pet_id}/stats?range=day|week|month
GET /pets/{pet_id}/summary?range=day|week|month
```

`POST /events` 示例返回：

```json
{
  "event_id": 42,
  "session_id": 8,
  "message": {
    "message": "妈，我刚刚去喝水啦，水碗边今天有点像我的快乐小基地。",
    "severity": "normal",
    "facts_used": ["current_session", "today_stats", "historical_baseline"],
    "internal_signal": "frequent_today"
  }
}
```

如果低置信度不通知：

```json
{
  "event_id": 43,
  "message": null,
  "reason": "low_confidence"
}
```

## 16. 后续扩展

后续阶段：

1. 极简前端图表页面。
2. Telegram Bot 通知。
3. 自动日报、周报推送。
4. 事件纠错接口和统计重算。
5. 宠物护理知识库扩充。
6. PDF 文档进入 RAG。
7. 多宠物展示切换。
8. Prompt 评估集和输出质量测试。
9. 数据增长优化：原始事件保留窗口、归档策略、`daily_stats` 预聚合表、上线后从 SQLite 迁移到 PostgreSQL。

## 17. 面试表达重点

这个项目可以在面试中强调：

- 我没有把所有问题都交给 LLM，而是让规则层负责事实一致性和状态机。
- 我用 SQLite 存结构化行为数据，用 ChromaDB 保留知识库检索，两类数据职责分离。
- 我把实时事件聚合成 behavior session，避免刷屏，同时保留行为强度。
- 我把 LLM 输出设计为结构化 JSON，方便前端、通知和调试。
- 我记录 model_name 和 prompt_version，让 LLM 输出可追踪。
- 我把通知层抽象出来，先 Console 调试，后续替换 Telegram。
- 我明确限制健康表达边界，只做观察提醒，不做医疗诊断。

## 18. 电子宠物长期路线图

后续产品方向可以从“宠物行为助手”升级为“电子宠物 Agent”。核心原则是：规则和状态机负责世界运行，LLM 负责表达、总结和柔性规划，多模态模型负责形象与照片生成。

### 18.0.1 最终呈现形态

HTML dashboard 只是开发调试面板，不是最终用户主体验。最终产品呈现应分成两条主线：

```text
1. Telegram Bot 消息交互
2. 桌面上的定制宠物形象
```

Telegram Bot 负责：

```text
实时宠物消息
主人动作指令，例如 /feed、/play、/pet、/status
日报、周报、提醒
宠物行为照片
在消息界面展示定制宠物形象、头像、表情图和行为图片
```

桌面宠物负责：

```text
展示主人定制的固定风格宠物形象
先提供安静态和桌面闲逛，确保确认形象后可以快速开始陪伴
根据状态逐步切换更丰富的表情和动作
在桌面上出现、移动、冒气泡
响应 Telegram 或本地操作触发的事件
```

宠物形象定制 Agent 是长期核心能力之一，应支持：

```text
文本生成宠物形象
参考图生成固定风格宠物形象
确认一个角色设定后，后续行为图像保持一致风格
根据行为生成照片，例如喝水、睡觉、玩耍、学习技能
允许主人后续自定义表情、情绪和动作包
```

桌面陪伴不应被完整动作资产生成阻塞。形象确认后的产品体验应分阶段开放：

```text
1. avatar_ready：角色形象已确认。
2. desktop_basic_ready：基础桌宠包已可用，包含安静态和简单桌面闲逛。
3. actions_generating：后台生成睡觉、开心、工作、提醒、互动等动作。
4. actions_partial_ready：部分动作生成完成并可替换到桌面宠物。
5. actions_full_ready：完整动作/表情包生成完成。
6. generation_failed：高级动作生成失败，但基础桌面陪伴仍可继续使用。
```

推荐产品话术：

```text
小宠物先来桌面陪你啦，动作细节正在慢慢长出来。
```

这样可以把等待从“功能不可用”转化成“宠物逐步成长”。只有高阶动作、精修表情和高级动态效果需要等待；基础桌面存在感必须尽快可用。

产品架构上，Telegram 和桌面宠物都只是交互层，不应重写宠物状态机。它们都应复用后端的同一套能力：

```text
virtual_pet_service
pet_event_service
pet_message_agent
pet_summary_agent
image/character agent
notifier
```

### 18.0.2 Telegram 与桌面宠物能力分配

Telegram 和桌面宠物都应支持定制形象，但适合承载的功能不同。

两端都应该具备的共同能力：

```text
展示同一个宠物角色设定
使用同一个宠物名字、性格、主人称呼
展示实时行为消息
触发主人动作，例如 feed、play、pet、clean、lullaby
查看状态摘要
展示行为照片或表情图
```

更适合 Telegram 的能力：

```text
聊天式互动和指令
异步通知和提醒
日报、周报、月报
行为照片推送
宠物主动发消息
主人不在电脑前也能互动
图片生成结果确认，例如“这张作为豆包的固定形象”
轻量设置，例如切换性格、称呼、通知频率
```

更适合桌面宠物的能力：

```text
常驻陪伴感
可移动、可悬浮的小宠物形象
状态驱动的表情和动作，例如困了趴下、开心跳动、饿了冒气泡
低打扰的环境反馈
与本机工作流联动，例如番茄钟、休息提醒、待办提醒
从 Telegram 消息触发桌面事件，例如“豆包跳出来找你玩”
```

不建议只放在桌面的能力：

```text
重要提醒
日报/周报
历史消息
图片确认流程
跨设备交互
```

不建议只放在 Telegram 的能力：

```text
持续陪伴展示
实时姿态变化
桌面小动作
本机工作流辅助
```

推荐设计原则：

```text
Telegram 是消息和远程互动中心。
桌面宠物是陪伴和本地环境表现层。
两者共享同一个后端状态、同一个角色设定、同一套事件和技能系统。
```

### 18.0 产品模式和订阅能力

后续应区分两种产品模式：

```text
real     真实宠物行为助手
virtual  电子宠物 Agent
```

两者可以共用底层能力，例如宠物资料、事件记录、消息生成、总结、通知和 RAG，但事件来源和产品表现不同。

真实宠物模式：

```text
事件来源：真实设备、位置数据、传感器或用户导入
核心价值：记录真实宠物行为，做统计、总结和温和观察提醒
重点行为：eat / drink / poop / sleep
```

电子宠物模式：

```text
事件来源：内部状态模拟器和主人主动操作
核心价值：陪伴、成长、互动、形象创作、技能解锁
重点行为：eat / drink / poop / sleep / play / learn
```

第一版代码层先使用 `pets.pet_mode` 区分：

```text
real
virtual
```

后续再引入订阅计划或功能开关：

```json
{
  "real_tracking": true,
  "virtual_companion": true,
  "image_generation": false,
  "desktop_pet": false,
  "skill_training": true
}
```

订阅能力建议：

```text
基础真实宠物助手：真实事件、统计、总结
电子宠物陪伴：状态模拟、主人动作、互动消息
高级创作包：文生图、图生图、行为照片、固定风格资产
技能成长包：上学、XP、技能解锁、帮主人执行受控任务
桌面陪伴包：桌面宠物、Telegram 联动、气泡和动作展示
```

### 18.1 模拟行为和主人互动

第一阶段新增电子宠物内部状态：

```text
hunger        饥饿
thirst        口渴
energy        精力
mood          心情
cleanliness   清洁度
affection     亲密度
```

行为模拟不主要交给 LLM，而使用状态机、概率模型、性格参数和日常节律。

新增主人动作：

```text
feed       喂食
refill     换水
play       陪玩
clean      清理
pet        摸摸
lullaby    哄睡
```

新增行为：

```text
play       玩耍
```

主人动作改变内部状态，内部状态再驱动结构化事件。LLM 基于状态和事件生成宠物口吻回应。

### 18.2 宠物形象系统

后续支持主人自定义宠物外观：

```text
文本描述 -> 生成固定风格宠物图像
参考图像 -> 图生图生成固定风格宠物图像
```

实现建议：

- 保存宠物视觉设定，例如 species、颜色、花纹、配饰、画风、参考图路径。
- 先生成最小桌宠资产：头像、安静态、简单桌面闲逛。
- 完整姿态资产异步生成，例如 sleep、happy、work、alert、feed、refill、play、pet、clean、lullaby。
- 允许用户后续追加自定义表情、情绪和动作包，并在确认后加入同一个桌宠 manifest。
- 每次生成图片时使用同一个视觉设定和参考图，保持角色一致性。
- 图片生成结果进入 `pet_assets` 表，记录 prompt、model、seed、asset_type、file_path。

第一版不追求完整动作库，先保证基础桌面陪伴即时可用。行为照片、完整动作和用户自定义表情可以作为后续渐进式能力。

### 18.3 行为照片

后续可以在特定事件后给主人发送“宠物行为照片”：

```text
drink session -> 生成在水碗边喝水的照片
sleep session -> 生成窝里睡觉的照片
play action -> 生成玩耍照片
school action -> 生成学习技能照片
```

照片生成应异步处理，不阻塞事件入库和文字通知。文字通知先发，图片生成完成后再补发。

### 18.4 Telegram 形态

Telegram 第一阶段作为通知和交互渠道：

```text
实时行为消息
日报/周报
主人主动动作，例如 /feed、/play、/status
发送宠物照片
```

当用户拥有多只宠物时，Telegram 不应变成冷冰冰的“选择宠物管理器”。它默认是一个宠物群聊：多只宠物都可以在这里发状态语言给主人。需要对某只宠物做资料设置、形象更新、喂饭/陪玩等定向操作时，再通过群聊中的宠物卡片指定“互动对象”。桌面陪伴则允许选择一只或多只宠物同时出现在桌面。

Telegram 不应该直接承载核心业务逻辑，而是调用后端 API 或 service 层。这样后续桌面端、网页端可以复用同一套宠物状态和 Agent 能力。

### 18.5 桌面宠物形态

远期可以支持“宠物从 Telegram 信息跳跃到桌面上”。建议拆成两步实现：

1. 桌面 companion 应用读取后端状态，展示一个可移动的桌面宠物窗口。
2. Telegram 某些消息触发桌面事件，例如宠物出现、跳动、播放动作、展示气泡。

技术上可以选择：

```text
Electron / Tauri / Python GUI
WebSocket 或轮询后端状态
本地透明窗口或置顶小窗
```

桌面端是展示层，不应重新实现宠物状态机。

桌面宠物启动体验应遵循“即时陪伴优先”：

```text
形象确认
-> 生成基础 manifest：avatar + quiet/idle + wandering
-> 立即开放桌面陪伴
-> 后台生成高级动作和表情
-> 已完成的动作逐步热更新或下次启动替换
```

基础桌面陪伴可用前，不要求 sleep、happy、feed、play 等完整动作全部完成。完整动作库是增强体验，不是启动门槛。

### 18.4.1 Telegram `/set` 指令

`/set` 是 Telegram 中的配置入口，负责设置宠物资料、性格、主人称呼、通知偏好和形象。

第一版建议同时支持快捷命令和分步向导：

```text
/set
打开设置菜单

/set name 豆包
设置宠物名字

/set personality sweet|cool|energetic|gentle
设置宠物性格

/set owner_call 妈|姐姐|爸爸
设置宠物对主人的称呼

/set mode real|virtual
设置宠物模式

/set avatar
进入形象设置流程
```

`/set avatar` 流程：

```text
1. 用户发送文字描述或参考图
2. Bot 调用宠物形象定制 Agent
3. Bot 返回候选形象图片
4. 用户确认，例如 /confirm_avatar
5. 后端保存为当前宠物 active avatar
```

后端能力应先于 Telegram Bot 实现：

```text
PATCH /pets/{pet_id}
更新宠物资料

POST /pets/{pet_id}/avatar
生成宠物形象

POST /pets/{pet_id}/avatar/confirm
确认当前形象
```

### 18.6 培养和技能系统

远期可以加入“上学学习技能，帮助主人干活”的成长系统。

建议模型：

```text
skills
- id
- name
- level
- xp
- unlocked_at
- tool_permissions
```

技能例子：

```text
提醒主人喝水
整理今日待办
总结聊天记录
查询宠物护理知识
生成日报
陪伴式番茄钟
```

实现原则：

- 技能本质上是受控工具能力，不是让 LLM 任意行动。
- 宠物上学和训练增加 xp，达到条件解锁工具。
- 每个技能都有明确输入、输出、安全边界和权限。
- 宠物用自己的性格包装执行结果，让工具型 Agent 更有陪伴感。

### 18.7 推荐实现顺序

长期路线建议：

1. 电子宠物状态模拟器：状态、tick、概率行为、主人动作。
2. `play` 行为进入事件流、统计和消息。
3. Telegram 通知和主人动作指令。
4. 宠物视觉设定和静态头像生成。
5. 行为照片异步生成。
6. 极简网页或桌面 companion 展示宠物状态。
7. 技能系统和成长 XP。
8. 桌面宠物联动 Telegram 事件。
