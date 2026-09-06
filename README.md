# AI 网文写作台

一个面向长篇网络小说创作的本地化 AI 写作工具。它通过“故事圣经、人物卡、章节摘要、卷大纲和伏笔库”等外置记忆，帮助 AI 在连续创作时保持人物、世界观和剧情的连贯性。

> 本项目适合个人创作者在本机使用。项目不会自带 AI 模型，使用前需要配置一个兼容 OpenAI Chat Completions 接口的模型服务。

## 项目状态

当前项目处于持续开发阶段：

- 后端 API、SQLite 数据持久化、API Key 加密存储和 AI 流式写作接口已经实现；
- 章节细纲、校对、定稿总结、人物/伏笔记忆管理等核心后端能力已经具备；
- 前端采用 Vue 3 + Vite 方案，具体页面会随着开发继续完善；
- 部分设计文档中的高级能力（例如 RAG 向量检索、批量连续生成、按角色配置不同模型）属于后续规划，不代表当前版本全部可用。

## 功能概览

### 1. AI 章节创作流水线

每一章可以按照以下流程完成：

1. **生成细纲**：根据当前卷大纲、前情摘要、人物状态和待回收伏笔生成章节细纲；
2. **开始写作**：按照细纲生成章节正文，支持 SSE 流式输出；
3. **一致性校对**：检查人物、设定、时间线、伏笔和文风问题；
4. **修订正文**：根据选中的校对问题生成修订稿；
5. **定稿并总结**：生成章节摘要，更新人物状态、伏笔状态和生成日志。

### 2. 长篇小说外置记忆

系统不把整本小说全部发送给模型，而是按需组装上下文，主要包含：

- 故事圣经：世界观、力量体系、势力和写作设定；
- 人物卡：外貌、性格、目标、关系和当前状态；
- 全书/分卷大纲：控制剧情发展方向；
- 最近章节摘要：减少长篇正文带来的上下文压力；
- 伏笔库：记录已埋设、待回收、已回收和废弃的伏笔；
- 上一章结尾窗口：帮助新章节自然衔接。

### 3. 小说和章节管理

- 创建、编辑和删除小说；
- 自动创建第一卷并管理多卷结构；
- 创建、编辑和删除章节；
- 统计章节字数；
- 导出选定章节为 TXT；
- 可导入故事圣经、全书大纲、人物卡和 AI 写作限制词文档。

### 4. API 配置

支持配置任意兼容 OpenAI API 格式的服务，例如：

- DeepSeek
- Kimi/Moonshot
- 豆包/火山引擎
- 通义千问
- 智谱 GLM
- 其他兼容 `chat.completions.create` 的服务

API Key 不会以明文写入数据库，而是使用 Fernet 对称加密后保存到本地。

## 技术栈

### 后端

| 技术 | 用途 |
| --- | --- |
| Python 3.10+（推荐 3.12） | 后端开发语言 |
| FastAPI | REST API、请求处理和接口文档 |
| Uvicorn | ASGI 应用服务器 |
| SQLAlchemy 2.x | ORM 和数据库访问 |
| SQLite | 本地单机数据库 |
| Pydantic 2 | 请求参数和 AI JSON 输出校验 |
| OpenAI Python SDK | 调用 OpenAI 兼容模型服务 |
| Cryptography / Fernet | 本地加密保存 API Key |
| SSE | 将 AI 正文以流式方式推送到前端 |

### 前端

| 技术 | 用途 |
| --- | --- |
| Vue 3 | 前端界面和交互 |
| Vite | 前端开发服务器和构建工具 |
| Vue Router | 页面路由 |
| JavaScript ES Modules | 前端模块化开发 |

> 当前 `frontend/package.json` 中已配置 Vue 3、Vue Router、Vite 和 Vue 插件。Pinia、Element Plus、Markdown 渲染库等属于设计方案中的可选技术，只有在代码实际引入后才会成为运行时依赖。

## 运行环境

### 必需环境

- Windows 10/11、macOS 或 Linux；
- Python 3.10 或更高版本（推荐 Python 3.12）；
- Node.js 18 或更高版本，推荐 Node.js 20 LTS；
- npm；
- 一个可访问的 OpenAI 兼容 API 服务及 API Key。

### 推荐配置

- 内存：4 GB 以上；
- 磁盘：至少 1 GB 可用空间，具体取决于小说数量；
- 网络：能够访问所配置的模型服务；
- 不需要单独安装 MySQL、Redis 或向量数据库，当前版本默认使用 SQLite。

## 快速开始

下面以 Windows PowerShell 为例。Linux/macOS 只需要将激活虚拟环境的命令替换为对应写法即可。

### 1. 获取项目

```bash
git clone <你的 GitHub 仓库地址>
cd test1
```

### 2. 创建并激活 Python 虚拟环境

```bash
cd backend
python -m venv .venv
.venv\\Scripts\\activate
```

Linux/macOS：

```bash
source .venv/bin/activate
```

### 3. 安装后端依赖

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. 启动 FastAPI 后端

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

启动成功后可以访问：

- 健康检查：<http://127.0.0.1:8000/api/health>
- Swagger API 文档：<http://127.0.0.1:8000/docs>
- ReDoc 文档：<http://127.0.0.1:8000/redoc>

### 5. 安装并启动前端

打开新的终端窗口：

```bash
cd frontend
npm install
npm run dev
```

默认前端地址：<http://127.0.0.1:5173>

Vite 开发服务器会把 `/api` 请求代理到 `http://127.0.0.1:8000`。如果前端目录当前只有工程配置而没有完整页面源码，请先完成前端页面开发，或直接使用 Swagger 文档测试后端接口。

### 6. 云端部署

当前项目适合采用“Cloudflare Pages 前端 + Python Web Service 后端”的部署方式。Cloudflare Pages 负责托管 Vue 静态页面，FastAPI 后端需要部署到支持 Python Web Service 的平台（例如 Render、Railway 或其他同类服务）。

#### 部署 FastAPI 后端

在 Python Web Service 中连接项目仓库，并填写：

```text
根目录：backend
运行时：Python 3.12
构建命令：pip install -r requirements.txt
启动命令：uvicorn app.main:app --host 0.0.0.0 --port $PORT
健康检查：/api/health
```

部署完成后，访问 `https://你的后端域名/api/health`，应返回：

```json
{"status":"ok"}
```

#### 部署 Cloudflare Pages 前端

在 Cloudflare Pages 中填写：

```text
根目录：frontend
框架预设：Vue
构建命令：npm run build
构建输出目录：dist
Node.js：20
```

在 Pages 的生产环境变量中添加：

```text
VITE_API_BASE_URL=https://你的后端域名/api
```

该变量必须以 `VITE_` 开头，值的末尾必须包含 `/api`。修改环境变量后需要重新触发一次构建，因为 Vite 会在构建时将变量写入前端资源。前端 API 地址默认仍为 `/api`，因此不配置该变量不会影响本地开发。

#### 配置后端跨域

后端默认允许跨域，便于本地开发和首次联调。正式部署时，可在后端 Web Service 中设置：

```text
CORS_ORIGINS=https://你的项目.pages.dev
```

如果有多个前端来源，用英文逗号分隔：

```text
CORS_ORIGINS=https://你的项目.pages.dev,https://novel.example.com
```

不要在来源末尾添加 `/`。后端代码会读取该变量并限制允许的前端域名。

#### 部署后的检查顺序

1. 访问后端 `/api/health`，确认返回 `{"status":"ok"}`；
2. 打开前端，在浏览器开发者工具的 Network 面板中保存 API 配置；
3. 确认请求地址是 `https://你的后端域名/api/config`，而不是前端 Pages 域名下的 `/api/config`；
4. 创建一本新小说，确认请求 `POST /api/novels` 成功。

当前后端使用 SQLite。本地文件部署到临时磁盘时，服务重启或重新部署可能导致小说和配置丢失；正式使用应为 Web Service 配置持久化磁盘，或将数据库迁移到 PostgreSQL。无论采用哪种方式，都必须同时持久化 `backend/data/novel.db` 和 `backend/data/.secret_key`。

### 7. 配置模型 API

在应用的 API 配置页面中填写：

- **Base URL**：模型服务的兼容接口地址，例如 `https://api.deepseek.com/v1`；
- **API Key**：对应服务的密钥；
- **模型名称**：服务商提供的模型 ID，例如 `deepseek-chat`；
- **上下文长度**：模型支持的上下文 token 数；
- **Temperature**：写作随机性，默认值为 `0.8`。

保存后执行“测试连接”。也可以在 Swagger 中调用：

```text
POST /api/config/test
```

> 不同服务商的 Base URL 和模型名称不同，请以服务商官方文档为准。不要把真实 API Key 提交到 GitHub。

## 推荐使用流程

### 第一次使用

1. 启动后端和前端；
2. 配置并测试模型 API；
3. 创建一本小说，填写书名、题材、主角、简介和文风；
4. 导入或手动补充故事圣经、全书大纲和人物卡；
5. 检查第一卷大纲和人物设定；
6. 进入章节工作台，生成下一章细纲；
7. 人工修改细纲后开始生成正文；
8. 仔细阅读正文并进行人工编辑；
9. 执行校对，根据报告选择性修订；
10. 确认无误后定稿，让系统更新记忆。

### 连续写作时的建议

- 每章生成的细纲先人工确认，不要完全依赖模型；
- 重要世界观规则写入故事圣经，不要只放在章节正文里；
- 角色发生位置、目标、关系或情绪变化时，及时检查人物卡；
- 伏笔应使用明确标题登记，回收后检查状态是否正确；
- 定稿前先校对，避免错误被总结进后续记忆；
- 定期导出 TXT，并备份 `backend/data/` 目录。

## 目录结构

```text
test1/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 应用入口和路由挂载
│   │   ├── database.py          # SQLAlchemy 引擎和 SQLite 配置
│   │   ├── models.py            # 数据库模型
│   │   ├── schemas.py           # Pydantic 请求/响应模型
│   │   ├── crypto.py            # API Key 加密和解密
│   │   ├── llm_gateway.py       # OpenAI 兼容 API 网关
│   │   ├── memory_service.py    # 长篇记忆和上下文组装
│   │   ├── prompts.py            # 各类 AI 角色提示词
│   │   ├── importers.py          # 设定文档导入解析
│   │   └── api/
│   │       ├── config_routes.py # API 配置接口
│   │       ├── novels.py         # 小说和导出接口
│   │       ├── chapters.py       # 章节 CRUD 接口
│   │       ├── memory_routes.py  # 细纲、校对、总结和记忆接口
│   │       ├── imports.py        # 故事设定导入接口
│   │       └── write_routes.py   # SSE 流式写作接口
│   ├── data/                     # 运行时生成，存放数据库和加密密钥
│   ├── requirements.txt
│   └── .venv/                    # 本地虚拟环境，不应提交
├── frontend/
│   ├── src/
│   │   └── api.js                # API 基地址和请求封装
│   ├── .env.example              # 线上 API 地址配置示例
│   ├── package.json
│   ├── vite.config.js
│   └── index.html
├── all.txt                       # 项目设计/需求资料
├── tx.md                         # 详细设计蓝图
└── README.md
```

## 核心接口

### 系统

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 服务健康检查 |
| GET | `/docs` | Swagger 交互式 API 文档 |

### API 配置

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/config` | 获取当前配置（不会返回完整 Key） |
| PUT | `/api/config` | 保存 API 配置 |
| POST | `/api/config/test` | 测试模型服务连通性 |

### 小说和章节

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `/api/novels` | 获取小说列表 / 创建小说 |
| GET/PUT/DELETE | `/api/novels/{novel_id}` | 获取、修改、删除小说 |
| POST | `/api/chapters` | 创建章节 |
| PUT/DELETE | `/api/chapters/{chapter_id}` | 修改、删除章节 |
| POST | `/api/novels/{novel_id}/export` | 导出选定章节为 TXT |

### AI 写作和记忆

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/novels/{novel_id}/next-outline` | 生成下一章细纲 |
| POST | `/api/write/stream` | SSE 流式生成正文 |
| POST | `/api/chapters/{chapter_id}/check` | 一致性校对 |
| POST | `/api/chapters/{chapter_id}/revise` | 根据问题生成修订稿 |
| POST | `/api/chapters/{chapter_id}/finalize` | 定稿并更新记忆 |
| GET | `/api/novels/{novel_id}/memory` | 查看人物、伏笔、摘要和卷信息 |

完整的请求参数和响应格式请以运行中的 Swagger 文档为准。

## 数据和安全说明

### 本地数据位置

首次启动后端时会自动创建：

```text
backend/data/novel.db
backend/data/.secret_key
```

- `novel.db`：小说、章节、人物、伏笔和生成日志；
- `.secret_key`：用于解密 API Key 的本地 Fernet 密钥。

请同时备份这两个文件。只备份数据库而不备份 `.secret_key`，将无法恢复已保存的 API Key。

### 提交 GitHub 前必须注意

不要提交以下内容：

- `backend/.venv/`；
- `backend/data/novel.db`；
- `backend/data/.secret_key`；
- 任何包含真实 API Key 的文件；
- 个人小说原稿、未公开设定或生成日志（除非确定允许公开）。

建议在项目根目录创建 `.gitignore`，至少加入：

```gitignore
backend/.venv/
backend/data/*.db
backend/data/.secret_key
__pycache__/
*.py[cod]
node_modules/
dist/
.env
```

当前应用主要面向本机单用户场景，尚未提供用户登录、权限管理、HTTPS、远程数据库和多用户隔离能力。不要在未增加认证和安全配置的情况下直接部署到公网。

## 常见问题

### 启动时提示 `ModuleNotFoundError: No module named 'app'`

请确认当前终端所在目录是 `backend`，并且已经激活虚拟环境：

```bash
cd backend
.venv\\Scripts\\activate
uvicorn app.main:app --reload
```

### API 测试失败

请依次检查：

1. Base URL 是否为服务商的 OpenAI 兼容接口地址；
2. API Key 是否有效、是否有余额或调用权限；
3. 模型名称是否正确；
4. 本机网络能否访问该服务；
5. 是否在 `/api/config` 中保存了配置。

### 前端请求跨域或连接失败

本地开发时确认后端运行在 `127.0.0.1:8000`，前端运行在 `127.0.0.1:5173`。Vite 会自动代理 `/api` 请求；如果修改了后端端口，需要同步修改 `frontend/vite.config.js`。

云端部署时确认 Cloudflare Pages 的构建环境变量 `VITE_API_BASE_URL` 已设置为完整后端地址，例如 `https://novel-api.example.com/api`，并在修改变量后重新部署前端。浏览器 Network 面板中的请求应直接指向后端域名。如果仍然出现 CORS 错误，请检查后端的 `CORS_ORIGINS` 是否包含完整前端来源（不带末尾 `/`）。

### 为什么 AI 会出现设定错误

外置记忆只能降低错误，不能替代人工审核。建议把关键规则写入故事圣经，定稿前执行校对，并检查总结后的角色状态和伏笔状态。

## 后续规划

- 完善 Vue 前端页面和章节工作台；
- 支持 Markdown 正文渲染和更细粒度的段落重写；
- 增加批量连续生成和中断恢复；
- 增加成本统计页面和更准确的 token 统计；
- 支持本地 embedding 与章节摘要语义检索（RAG）；
- 支持不同流水线角色使用不同模型；
- 增加自动备份、导出 Markdown 和设定集导出；
- 为公开部署增加登录、权限、限流和更完善的密钥管理。

## 免责声明

本项目是 AI 辅助写作工具，模型输出可能存在事实错误、逻辑矛盾、重复、模板化表达或不适宜内容。使用者应自行审核并对最终发布内容负责，同时遵守所使用模型服务商的条款、当地法律法规以及相关平台的内容规范。

## License

如果准备将项目公开到 GitHub，请根据自己的发布计划补充许可证，例如 MIT License。当前仓库尚未在代码中声明具体许可证，发布前请明确项目授权方式。
