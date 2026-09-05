# AI 网文小说网站 · 项目文档

> 版本 v1.0 ｜ 日期 2026-08-30 ｜ 状态：开发蓝图

---

## 1. 项目概述

### 1.1 目标

搭建一个 **AI 网文小说写作网站**：用户只需在配置页填入自己的 AI 模型 API（OpenAI 兼容格式），网站就能根据**已写内容的前后文**自动续写**情节连贯的长篇网络小说**（几十万字到几百万字），并保证人物一致、设定不崩、伏笔能回收。

### 1.2 核心价值

| 痛点 | 本项目的解决方案 |
|---|---|
| 直接用 ChatGPT 写小说，几轮对话后 AI 就"失忆"，前后矛盾 | 内置分层记忆系统，自动维护摘要、伏笔、角色状态 |
| 每次续写都要手动粘贴大纲和设定，费时且易漏 | 一键「生成下一章」，上下文自动组装 |
| AI 生成质量不可控 | 半自动流水线：细纲可改 → 正文可润色 → 校对报告 → 逐段重生成 |
| 需要绑定某一家 AI 服务 | 只依赖 OpenAI 兼容协议，DeepSeek / Kimi / 豆包 / 通义 / GLM 等均可接入 |

### 1.3 使用场景

- 仅自己使用：本机部署，无登录注册，API Key 存本地数据库
- 写作模式：**半自动** —— AI 自动续写，每章可人工干预（改细纲、润色、重生成）

---

## 2. 核心难点与解决方案

### 2.1 难点分析

长篇网文的本质难题：**百万字级全书上下文 vs 模型有限的上下文窗口**。

- 普通模型窗口 4K~128K tokens，长文最多容纳约 20 万字原文；
- 直接把全书塞给模型，token 成本爆炸且中后段质量下降；
- 直接什么都不给，AI 就会"忘记"前面的人物、设定和伏笔，情节断裂。

结论：**不能依赖模型记忆，必须由系统维护一套外置记忆（Memory System）**。

### 2.2 分层记忆系统（核心设计）

系统为每本小说维护以下六类记忆，这是全书唯一的事实来源（Source of Truth）：

| 记忆层 | 内容 | 更新时机 | 用途 |
|---|---|---|---|
| **故事圣经 Story Bible** | 世界观设定、力量体系、地理势力 | 建书时生成，人工可改 | 所有生成步骤的必带上下文 |
| **人物卡 Characters** | 每个角色的外貌、性格、目标、关系、**当前状态**（位置/情感/生死） | 建书时生成 + 每章总结更新 | 保证人物言行一致 |
| **层级大纲 Outlines** | 全书大纲 → 分卷大纲 → 章节细纲（三级树） | 建书时生成全书大纲；开新卷时生成卷大纲；每章前生成细纲 | 保证剧情有方向、不跑偏 |
| **递归摘要 Summaries** | 章摘要（300字）→ 卷摘要 → 全书摘要 | 每章定稿后由总结器更新 | 写新章时只带"最近 3 章摘要 + 本卷摘要"，代替原始正文 |
| **伏笔库 Foreshadowing Ledger** | 每条伏笔：标题、描述、状态（已埋/待回收/已回收/废弃）、埋设章节 | 细纲师埋设、总结器登记、回收时更新 | 保证伏笔不烂尾，到期强制回收 |
| **角色状态机 Character States** | 每个角色当前位置、当前目标、情感状态、关系变化 | 每章定稿后由总结器更新 | 跨章连贯的关键 |

**写第 N 章时，上下文 = 故事圣经精选 + 卷大纲 + 最近章摘要 + 待回收伏笔 + 细纲 + 上一章末尾原文窗口**，总长度控制在模型窗口的 30%~50%，成本与记忆两不误。

### 2.3 每章生成流水线（4 步 Agent 编排）

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ ① 细纲师  │ → │ ② 写手   │ → │ ③ 校对   │ → │ ④ 总结师  │
│ Planner  │   │ Writer   │   │ Checker  │   │ Summarizer│
└──────────┘   └──────────┘   └──────────┘   └──────────┘
 生成本章细纲    流式生成正文     一致性检查      更新记忆档案
 （用户可编辑）  （按细纲分段）  （输出问题清单）  （摘要/伏笔/状态）
```

| 步骤 | 角色 | 输入 | 输出 | 人工干预点 |
|---|---|---|---|---|
| ① | 细纲师 | 卷大纲 + 前情摘要 + 伏笔库（待回收项）+ 角色状态 | 本章细纲（JSON：场景序列、伏笔埋设/回收计划、章末钩子） | ✅ 用户可编辑细纲 |
| ② | 写手 | 故事圣经精选 + 细纲 + 前情摘要 + 上文滚动窗口 | 正文（2000~3000 字，SSE 流式输出） | ✅ 逐段重生成、手动编辑 |
| ③ | 校对 | 正文 + 圣经 + 摘要 + 伏笔库 | 问题清单（人物/设定/时间线/伏笔矛盾） | ✅ 用户选择采纳/忽略/改写 |
| ④ | 总结师 | 正文 + 细纲 + 旧记忆 | 更新：章摘要、伏笔状态、角色状态、大纲进度 | 自动执行 |

### 2.4 上下文组装模板

写第 N 章时，`memory_service` 按以下优先级拼装 prompt（总预算 ≤ 模型窗口的 50%）：

```
[系统提示] 写手角色 + 写作规则 + 文风要求
[故事圣经精选] 核心世界观 + 本章出场人物卡（从细纲的 participants 反查）
[剧情定位] 全书大纲进度 + 本卷大纲
[前情摘要] 最近 3 章摘要 + 本卷摘要
[伏笔提醒] 待回收伏笔列表（强制要求处理）
[本章细纲] 用户已确认的 JSON
[上文窗口] 上一章末尾 500~1000 字（正文分段生成时滚动更新）
```

### 2.5 成本与稳定性控制

- **Token 预算**：每步生成设定最大输入/输出 token，组装时超限自动裁剪（优先裁旧摘要）
- **重试机制**：API 失败按指数退避重试 3 次；正文生成支持断点续传（按已生成段落恢复）
- **降级策略**：可配置备用模型，主模型连续失败时自动切换
- **成本统计**：`generation_logs` 记录每步 token 与耗时，控制台可查每章/每本书成本
- **流式输出**：正文通过 SSE 逐字推送，用户可随时中断（中断点保存为草稿）

---

## 3. 技术选型

| 层 | 选型 | 理由 |
|---|---|---|
| 后端 | Python 3.12 + **FastAPI** | 原生支持 SSE 流式响应，Pydantic 约束 LLM 的 JSON 输出 |
| ORM | SQLAlchemy 2.x + **SQLite** | 单机使用零部署负担，WAL 模式支持并发读 |
| AI 接入 | `openai` Python SDK，自定义 `base_url` | 一套代码适配所有 OpenAI 兼容服务（DeepSeek/Kimi/豆包/通义/GLM） |
| 前端 | **Vue 3** + Vite + Pinia + Element Plus | 组合式 API，中文组件生态成熟 |
| 内容渲染 | markdown-it / marked | 正文以 Markdown 存储与展示 |
| 进阶可选 | 本地 embedding（sentence-transformers）+ SQLite 向量表 | 章节摘要语义检索，进一步压缩上下文（M4 引入） |

---

## 4. 系统架构

```
┌──────────────────────────── 浏览器 ────────────────────────────┐
│  Vue 3 前端：书架 / 章节工作台 / 设定面板 / API 配置 / 成本统计  │
└────────────────┬───────────────────────────────┬───────────────┘
                 │ REST (JSON)                    │ SSE（正文流式）
┌────────────────▼───────────────────────────────▼───────────────┐
│                          FastAPI 后端                          │
│  ┌─────────────┐   ┌────────────────┐   ┌───────────────────┐  │
│  │ API 路由层   │ → │ 生成编排引擎     │ → │ LLM 网关           │  │
│  │ /api/*      │   │ Pipeline 4 步   │   │ openai SDK 适配    │  │
│  └─────────────┘   └────────────────┘   │ 重试/降级/流式      │  │
│  ┌─────────────┐   ┌────────────────┐   └─────────┬─────────┘  │
│  │ 记忆服务      │   │ 任务/日志服务    │             │            │
│  │ 上下文组装    │   │ 成本统计        │             │            │
│  └──────┬──────┘   └────────────────┘             │            │
│         │                                          │            │
│   ┌─────▼──────────┐                    ┌──────────▼──────────┐  │
│   │ SQLite（WAL）   │                    │ 用户配置的 OpenAI    │  │
│   │ SQLAlchemy     │                    │ 兼容 API（外部）      │  │
│   └────────────────┘                    │ DeepSeek/Kimi/...   │  │
└─────────────────────────────────────────┴─────────────────────┘
```

模块职责：

| 模块 | 职责 |
|---|---|
| `api/` 路由层 | REST 接口 + SSE 端点；请求校验 |
| `pipeline/` 编排引擎 | 编排 4 步流水线；维护生成任务状态机 |
| `memory_service` | 分层记忆读写；写第 N 章时的上下文组装与裁剪 |
| `llm_gateway` | 封装 openai SDK；流式转发、重试、备用模型降级 |
| `models/` + `schemas/` | ORM 模型 + Pydantic 校验（含 LLM JSON 输出 Schema） |
| 前端 `stores/` | Pinia：当前小说、当前章节生成状态、SSE 缓冲区 |

---

## 5. 数据库设计（SQLite）

### 5.1 `api_config`（单行表，API 配置）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 恒为 1 |
| base_url | TEXT | 如 `https://api.deepseek.com/v1` |
| api_key | TEXT | 加密存储（Fernet） |
| model_name | TEXT | 如 `deepseek-chat` |
| backup_model_name | TEXT | 降级备用模型，可空 |
| context_window | INTEGER | 模型上下文长度（tokens） |
| temperature | REAL | 默认 0.8（写作类建议偏高） |
| updated_at | DATETIME | |

### 5.2 `novels`（小说）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | |
| title | TEXT | 书名 |
| genre | TEXT | 题材（玄幻/都市/科幻/言情...） |
| synopsis | TEXT | 一句话简介 |
| style | TEXT | 文风要求（如"轻松幽默、白描"） |
| story_bible | JSON | 故事圣经全文（世界观/力量体系/势力） |
| book_outline | JSON | 全书大纲（卷级节点树） |
| target_word_count | INTEGER | 目标总字数 |
| status | TEXT | 连载中 / 完结 |
| created_at / updated_at | DATETIME | |

### 5.3 `volumes`（卷）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | |
| novel_id | FK | |
| volume_no | INTEGER | 卷号 |
| title | TEXT | 卷名 |
| outline | TEXT | 卷大纲 |
| summary | TEXT | 卷摘要（卷完结时生成） |
| status | TEXT | 未开始 / 连载中 / 完结 |

### 5.4 `chapters`（章节）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | |
| novel_id / volume_id | FK | |
| chapter_no | INTEGER | 章号 |
| title | TEXT | 章节标题 |
| detailed_outline | JSON | 已确认的细纲（② 的输入依据） |
| content | TEXT | 正文（Markdown） |
| word_count | INTEGER | 字数 |
| status | TEXT | 草稿 / 待校对 / 已定稿 |
| created_at / updated_at | DATETIME | |

### 5.5 `chapter_summaries`（章摘要，每章一行）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | |
| chapter_id | FK | |
| summary | TEXT | 200~300 字摘要（因果链） |
| key_events | JSON | 关键事件数组 |
| character_state_updates | JSON | 角色状态变更数组 |
| outline_progress | TEXT | 本章完成了卷大纲的哪些目标 |
| tokens_used | INTEGER | 总结器消耗的 token |

### 5.6 `characters`（人物卡）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | |
| novel_id | FK | |
| name | TEXT | 角色名 |
| role | TEXT | 主角/配角/反派/龙套 |
| card | JSON | 外貌、性格、目标、关系、**当前状态**（位置/情感/生死） |
| first_appearance_chapter | INTEGER | 首次出场章号 |
| updated_at | DATETIME | |

### 5.7 `world_settings`（世界观条目）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | |
| novel_id | FK | |
| category | TEXT | 力量体系 / 地理 / 势力 / 规则 / 物品 |
| key | TEXT | 条目名 |
| value | TEXT | 条目内容 |
| updated_at | DATETIME | |

### 5.8 `foreshadowings`（伏笔库）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | |
| novel_id | FK | |
| title | TEXT | 伏笔标题 |
| description | TEXT | 伏笔内容 |
| status | TEXT | 已埋 / 待回收 / 已回收 / 废弃 |
| planted_chapter_id | FK | 埋设章节 |
| resolved_chapter_id | FK | 回收章节，可空 |
| updated_at | DATETIME | |

### 5.9 `outlines`（大纲树，三级：book / volume / chapter）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | |
| novel_id | FK | |
| level | TEXT | book / volume / chapter |
| parent_id | FK | 上级节点 |
| seq_no | INTEGER | 同级排序 |
| title | TEXT | 节点标题 |
| content | TEXT | 大纲内容 |
| status | TEXT | 未开始 / 进行中 / 已完成 |

### 5.10 `generation_logs`（生成日志，成本统计）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | |
| novel_id / chapter_id | FK | |
| agent_type | TEXT | planner / writer / checker / summarizer |
| model_name | TEXT | 实际使用的模型 |
| prompt_tokens / completion_tokens | INTEGER | |
| duration_ms | INTEGER | 耗时 |
| status | TEXT | 成功 / 失败 |
| error | TEXT | 失败原因 |
| created_at | DATETIME | |

---

## 6. 功能设计

### 6.1 新建小说向导

1. 填写：书名、题材、主角名、风格要求、目标字数
2. 可选「AI 生成初始设定」：一次调用生成故事圣经（世界观/力量体系）+ 全书大纲（分卷节点）+ 主角人物卡
3. 生成结果以表单呈现，**全部可人工修改**后保存

### 6.2 章节工作台（核心页面）

```
┌─ 第 N 章 ────────────────────────────────────────┐
│ [生成细纲] [开始写作] [校对] [定稿]                │
│                                                   │
│ ┌─ 细纲卡片（可编辑 JSON 表单）────────────────┐  │
│ │ 场景 1：地点/人物/事件/目标                    │  │
│ │ 场景 2：...    伏笔：埋设 X、回收 Y            │  │
│ │ 钩子：...                                     │  │
│ └──────────────────────────────────────────────┘  │
│ ┌─ 正文编辑区（SSE 流式渲染，可手动编辑）───────┐  │
│ │ ...                                           │  │
│ └──────────────────────────────────────────────┘  │
│ ┌─ 校对报告（问题列表，可勾选采纳）─────────────┐  │
│ │ ⚠ 高：第 3 段角色 B 的性格与人物卡矛盾          │  │
│ └──────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────┘
```

- **生成细纲**：细纲师输出场景序列，用户可在卡片上增删改
- **开始写作**：写手按细纲流式生成，可随时暂停/中断；选中某段可「重写此段」
- **校对**：输出问题清单，每条可勾选「按建议改写」
- **定稿**：触发总结器更新记忆（摘要/伏笔/角色状态/大纲进度），章节置为已定稿
- **连续生成**（M3）：可设定一次连写 N 章，每章之间自动衔接

### 6.3 设定面板

- **人物卡**：列表 + 详情编辑（外貌/性格/目标/关系/当前状态），支持 AI 补全
- **世界观**：分类条目 CRUD
- **伏笔库**：状态看板（已埋/待回收/已回收），可手动登记或废弃
- **大纲树**：三级树形编辑，拖动排序

### 6.4 API 配置页

- 填写 baseURL / API Key / 模型名 / 备用模型 / 上下文长度
- 「测试连接」按钮：发一条最小请求验证连通性
- Key 以 Fernet 加密落库，页面不回显明文

### 6.5 导出

- 导出整本书为 txt / Markdown（含卷名、章标题）
- 可选同时导出设定集（圣经+人物卡+大纲）为独立 md

---

## 7. Prompt 工程设计

### 7.1 角色分工与模型建议

| 角色 | 职责 | 输出格式 | 模型建议 |
|---|---|---|---|
| 大纲师 | 生成全书大纲、卷大纲 | JSON | 强推理模型 |
| 细纲师 | 规划本章场景序列与伏笔 | JSON | 强推理模型 |
| 写手 | 正文写作 | 纯文本（SSE） | 写作能力强的模型 |
| 校对 | 一致性检查 | JSON | 强推理模型 |
| 总结师 | 更新记忆档案 | JSON | 便宜快速的模型即可 |

> 4 步流水线中，写手占 token 大头；细纲/校对/总结可用便宜模型降成本。未来可支持按角色配置不同模型。

### 7.2 各角色系统提示（模板节选）

**写手（Writer）**：

```text
你是一位资深中文网络小说作家，擅长{genre}题材，文风要求：{style}。

写作规则：
1. 严格按照「本章细纲」推进剧情，不得偏离、不得提前剧透后续章节
2. 每章正文 2000~3000 字，分 3~5 个场景，场景间用空行分隔
3. 多用对话和动作推进剧情，减少大段说明性文字
4. 人物言行必须符合「人物卡」中的性格与目标；人物死亡后不得再出场
5. 章末必须落实细纲中的「钩子」，制造悬念
6. 不使用上下文未提供的信息；如确需新设定，用模糊写法带过
7. 输出纯正文 Markdown，不要章节标题，不要任何解释
```

**细纲师（Planner）**：

```text
你是网文细纲规划师。根据「卷大纲」「前情摘要」「伏笔库」「角色状态」规划下一章细纲。

要求：
1. 本章必须推进主线，或至少推进一个角色的弧光
2. 优先回收「待回收伏笔」中已到期的伏笔
3. 每章设置 1~2 个冲突/爽点
4. 章末设计钩子，勾住读者读下一章
5. 本章可埋设新伏笔（不超过 2 条），并在伏笔库中登记

输出 JSON（schema 见 7.3 之【细纲 Schema】）
```

**校对（Checker）**：

```text
你是网文一致性校对员。逐段检查正文与「故事圣经」「人物卡」「前情摘要」「伏笔库」的矛盾：

检查维度：
- 人物：性格、外貌、关系、生死状态
- 设定：力量体系、世界观规则
- 时间线：事件先后顺序
- 伏笔：已回收伏笔不得再当未回收使用；待回收伏笔无正当理由不得被无视

输出 JSON：{"issues": [...], "verdict": "pass|need_fix"}
无问题时 issues 为空数组。
```

**总结师（Summarizer）**：

```text
你是章节总结员，负责在章节定稿后更新记忆档案。输入正文与细纲，输出 JSON：

{
  "summary": "本章 200~300 字摘要，保留因果链",
  "key_events": ["关键事件 1", "关键事件 2"],
  "character_state_updates": [
    {"name": "角色名", "location": "当前所在地", "goal": "当前目标",
     "relationships": "关系变化（无则写'无变化'）", "emotional_state": "情感状态"}
  ],
  "foreshadowings_planted": [{"title": "", "description": ""}],
  "foreshadowings_resolved": ["已回收的伏笔标题"],
  "outline_progress": "本章完成了卷大纲中的哪些目标"
}
```

**大纲师（Outliner）**：

```text
你是资深网文架构师。根据「书名、题材、简介、风格、目标字数」设计全书结构。

要求：
1. 全书按剧情阶段分为 3~8 卷，每卷 15~30 章
2. 每卷有明确的起承转合与卷末高潮
3. 主角成长线、主线冲突、最终反派在开局就要埋设
4. 输出 JSON 大纲树，每卷含：卷名、卷目标、每章一句话梗概
```

### 7.3 JSON 输出约定

- 所有结构化输出用 Pydantic 定义 Schema，调用 LLM 时开启 `response_format={"type": "json_object"}` 并校验解析，失败自动重试一次并附错误信息
- 【细纲 Schema】：

```json
{
  "chapter_title": "第N章 标题",
  "scenes": [
    {"scene_no": 1, "location": "场景地点", "participants": ["出场角色"],
     "events": "本场景发生的事", "goal": "本场景的剧情作用"}
  ],
  "foreshadowings_planted": [{"title": "新伏笔", "description": "内容"}],
  "foreshadowings_resolved": ["待回收伏笔的标题"],
  "hook": "章末钩子",
  "word_target": 2500
}
```

### 7.4 网文写作规则（写手提示中的常量配置）

- 章字数：2000~3000 字；章节内要有起伏，禁止纯过渡章
- 钩子：每章末尾一句悬念/转折/预告
- 网感：拒绝书面腔报告体，对话口语化，节奏快，信息密度高
- 禁忌：不重复解释已交代过的设定；不出现"本章小结"式总结句

---

## 8. 生成流程时序（写第 N 章）

```
用户点击「生成下一章细纲」
  ① memory_service 组装 Planner 上下文（卷大纲+前情摘要+伏笔库+角色状态）
  ② LLM 网关调用细纲师 → 返回细纲 JSON
  ③ 前端展示可编辑细纲卡片
用户确认/修改后点击「开始写作」
  ④ memory_service 组装 Writer 上下文（圣经精选+细纲+前情摘要+上文窗口）
  ⑤ 写手按场景分段流式生成，SSE 逐字推送前端（滚动上文窗口）
     —— 用户可随时暂停/中断/逐段重生成 ——
用户点击「校对」
  ⑥ Checker 输出问题清单 → 用户勾选「按建议改写」或忽略
用户点击「定稿」
  ⑦ Summarizer 生成记忆更新 JSON
  ⑧ 后端事务落库：章节内容/状态、章摘要、伏笔状态、角色卡状态、大纲进度
  ⑨ 写入 generation_logs（token/耗时/成本）
```

---

## 9. 开发里程碑

| 里程碑 | 内容 | 验收标准 | 预估 |
|---|---|---|---|
| **M1 MVP** | API 配置页+测试连接；新建小说向导（表单+可选 AI 生成圣经/大纲）；细纲卡片；写手流式生成；SQLite 落库；书架/阅读页 | 配好 Key 后能完整写出并保存一章 | 1~2 周 |
| **M2 记忆系统** | 细纲师/校对/总结师接入；章摘要/卷摘要；伏笔库；角色状态机；上下文组装器；成本日志 | 连续写 20 章，人物设定不崩、伏笔正常回收 | 2~3 周 |
| **M3 体验完善** | 逐段重生成；按建议改写；批量连续生成 N 章；导出 txt/md；成本统计页 | 可无人值守连写 10 章，随时导出 | 1~2 周 |
| **M4 进阶（可选）** | 章节摘要 embedding 语义检索（RAG）；按角色配置不同模型；多小说管理优化 | 长上下文模型下更省 token，质量持平 | 2 周 |

---

## 10. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 上下文窗口不足 | 长文记忆丢失、前后矛盾 | 分层摘要+裁剪预算；只携带必要上下文；M4 检索增强 |
| 长文质量衰减 | 后期注水、人设漂移 | 每卷开卷时用「圣经+卷摘要」重校准；校对器拦截；细纲强制推进主线 |
| API 失败/限流 | 生成中断 | 指数退避重试 3 次；SSE 断点续传；备用模型自动降级 |
| 成本失控 | 预算超标 | token 预算上限；generation_logs 成本统计；细纲/总结用便宜模型 |
| 单机数据丢失 | 小说全失 | 定期备份 novel.db；支持一键导出 md 存档 |
| 内容安全 | 生成违规内容 | 提示词约束；仅本地使用不公开发布；用户对内容自担责任 |
| AI 输出 JSON 不合法 | 流水线中断 | Pydantic 严格校验 + 失败自动重试并回传错误 |

---

## 11. 推荐目录结构

```
test1/
├── backend/
│   ├── app/
│   │   ├── main.py                # FastAPI 入口，挂载路由与 SSE 端点
│   │   ├── config.py              # .env 配置读取
│   │   ├── database.py            # SQLAlchemy 引擎 / 会话（SQLite WAL）
│   │   ├── models/                # ORM：novel, volume, chapter, character, ...
│   │   ├── schemas/               # Pydantic：请求/响应 + LLM JSON Schema
│   │   ├── api/                   # 路由：config.py novels.py chapters.py
│   │   │                          #       settings.py export.py stats.py
│   │   ├── services/
│   │   │   ├── llm_gateway.py     # openai SDK 封装：流式/重试/降级
│   │   │   ├── memory_service.py  # 分层记忆读写 + 上下文组装/裁剪
│   │   │   └── pipeline/          # 4 步流水线
│   │   │       ├── planner.py
│   │   │       ├── writer.py
│   │   │       ├── checker.py
│   │   │       └── summarizer.py
│   │   └── prompts/               # 5 角色系统提示模板
│   ├── requirements.txt
│   └── data/novel.db
├── frontend/
│   ├── src/
│   │   ├── views/                 # Bookshelf / NovelWorkbench / SettingsPanel
│   │   │                          # ApiConfig / Stats
│   │   ├── components/            # ChapterEditor、OutlineCard、ForeshadowPanel
│   │   │                          # StreamingRenderer、CheckReport
│   │   ├── stores/                # Pinia：novel / chapterGeneration / apiConfig
│   │   ├── api/                   # axios 封装 + SSE 客户端（fetch stream）
│   │   └── router/
│   ├── package.json
│   └── vite.config.ts            # dev proxy → http://localhost:8000
└── tx.md                          # 本文档
```

---

## 附：关键 API 端点（草案）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/PUT | `/api/config` | 读写 API 配置；POST `/api/config/test` 测试连接 |
| POST | `/api/novels` | 新建小说；POST `/api/novels/{id}/generate-setup` 生成初始设定 |
| GET | `/api/novels/{id}/chapters` | 章节列表 |
| POST | `/api/novels/{id}/next-outline` | 生成下一章细纲 |
| POST | `/api/chapters/{id}/write` | **SSE** 流式生成正文 |
| POST | `/api/chapters/{id}/rewrite-segment` | 重写某段 |
| POST | `/api/chapters/{id}/check` | 一致性校对 |
| POST | `/api/chapters/{id}/finalize` | 定稿（触发总结器更新记忆） |
| GET | `/api/novels/{id}/export?format=txt|md` | 导出 |
| GET | `/api/stats` | 成本统计 |
