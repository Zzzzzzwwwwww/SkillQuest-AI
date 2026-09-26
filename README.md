# SkillQuest AI

> AI 职业成长智能体 —— 把职业规划、技能图谱、AI 导师、自适应学习与 RPG 游戏化成长融合在一起。

**默认领域**：AI 应用开发工程师
**目标用户**：在校学生 / 企业技术从业者 / 转岗学习者

当前仓库为 **项目框架版本（v0.1.0）**：前后端骨架、基础设施与示例页面均已就绪，具体业务逻辑（注册登录、技能图谱数据、AI 导师对话等）将在后续版本逐步落地。

---

## 技术栈

| 端 | 技术 |
| --- | --- |
| 前端 | Vue 3 + TypeScript + Vite + Pinia + Vue Router + Element Plus + ECharts + AntV G6 + axios |
| 后端 | FastAPI + SQLAlchemy 2.0 + Pydantic v2 + Alembic + MySQL 8 + Redis + JWT |
| AI | 华为云盘古大模型 / 华为云大模型服务（接口已预留） |
| 向量库 | PgVector（预留） |
| 部署 | Docker Compose（mysql:8 / redis:7 / frontend） |

> 注：`docker-compose.yml` 另含 PgVector（pg16）服务，供「智能答疑」模块向量检索使用（预留）。

### 多智能体架构

所有 AI 输出均结构化 JSON，前端直接渲染；后端通过统一 `LLMService` 调用华为云大模型。

| Agent | 职责 | 输出 |
| --- | --- | --- |
| Orchestrator | 调度中心：路由用户请求 | 意图 / 目标 Agent / 路由参数 |
| Career Agent | 职业测评画像、岗位推荐 | 画像标签 / 优劣势 / 推荐岗位 |
| Skill Agent | 技能树与差距分析 | 瓶颈技能 / 优先级 |
| Learning Agent | 个性化学习路径 | 阶段 / 资源 / 里程碑 |
| Tutor Agent | 答疑（RAG 带引用）、弱点诊断 | 回答 / 引用 / 弱点分析 |
| Assessment Agent | 测评复盘 | 知识域分析 / 改进计划 |
| Coach Agent | 督导、番茄钟、游戏化 | 今日计划 / 激励 |
| Reflection Agent | 学习复盘 | 亮点 / 卡点 / 下一步 |

`app/services/llm.py`：`chat_json()` 强制结构化输出 + 自动重试；
`app/agents/base.py`：`BaseAgent.run()` / `AgentRunner` 统一调度，未配置模型时返回可渲染的降级 JSON。

---

## 目录结构

```
SkillQuest-AI/
├── backend/                        # FastAPI 后端
│   ├── app/
│   │   ├── main.py                 # 应用入口（CORS / 异常处理 / 路由挂载）
│   │   ├── core/
│   │   │   ├── config.py           # 配置中心（pydantic-settings）
│   │   │   ├── security.py         # 密码哈希 + JWT 工具类 + 预留鉴权依赖
│   │   │   └── response.py         # 统一响应 { code, message, data }
│   │   ├── db/
│   │   │   ├── session.py          # SQLAlchemy 2.0 Engine / Session / Redis
│   │   │   └── base.py             # ORM 声明基类
│   │   ├── models/user.py          # 用户模型 users
│   │   ├── schemas/user.py         # 注册/登录/用户/令牌 Schema
│   │   ├── api/v1/
│   │   │   ├── router.py           # v1 路由汇总
│   │   │   └── endpoints/
│   │   │       ├── health.py       # GET /api/v1/health
│   │   │       └── auth.py         # 注册/登录（路由+签名留空）
│   │   └── utils/ai_client.py      # 华为云大模型客户端（预留）
│   ├── alembic/                    # 数据库迁移（含 users 表初始迁移）
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── frontend/                       # Vue3 前端
│   ├── src/
│   │   ├── main.ts                 # 入口（Element Plus / Pinia / Router）
│   │   ├── App.vue
│   │   ├── router/index.ts         # 路由配置（懒加载）
│   │   ├── store/user.ts           # Pinia 用户状态（预留）
│   │   ├── api/request.ts          # axios 统一封装
│   │   ├── layouts/BasicLayout.vue # 侧边栏 + 顶栏 + 内容区（移动端适配）
│   │   ├── views/                  # 6 个业务页面（占位内容）
│   │   │   ├── Home.vue            #   成长首页
│   │   │   ├── Career.vue          #   职业探索
│   │   │   ├── SkillTree.vue       #   技能树（G6 示例）
│   │   │   ├── LearningPath.vue    #   冒险地图（ECharts 示例）
│   │   │   ├── Tutor.vue           #   AI 导师（对话面板占位）
│   │   │   └── Profile.vue         #   成长档案
│   │   └── components/             # 共用组件
│   ├── package.json
│   ├── vite.config.ts              # 别名 / 代理 / 分包
│   ├── tsconfig.json
│   └── Dockerfile                  # 多阶段构建 + Nginx
├── docker-compose.yml              # 一键编排
├── .env.example
└── README.md
```

---

## 快速启动

### 一、Docker Compose 一键启动（推荐）

```bash
# 1. 准备环境变量
cp .env.example .env

# 2. 构建并启动全部服务
docker compose up -d --build

# 3. 查看状态（mysql/redis 健康后才执行后端迁移，已内置 alembic upgrade）
docker compose ps

# 4. 查看日志
docker compose logs -f backend
```

| 服务 | 地址 |
| --- | --- |
| 前端应用 | http://localhost/ |
| 后端 Swagger 文档 | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/api/v1/health |

停止：`docker compose down`（加 `-v` 会同时删除数据卷）。

### 二、本地开发模式

#### 1. 后端（Python 3.12）

```bash
cd backend

# 创建虚拟环境并安装依赖
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 准备环境变量（数据库/Redis 需先就绪）
cp .env.example .env

# 执行数据库迁移（创建 users 表）
alembic upgrade head

# 启动开发服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端地址：
- Swagger 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/v1/health

#### 2. 前端（Node 18+）

```bash
cd frontend

npm install
npm run dev
```

前端地址：http://127.0.0.1:5175/（开发服务器已配置 `/api` 代理到 `http://127.0.0.1:8000`）

```bash
# 生产构建 + 预览
npm run build
npm run preview
```

---

## 已实现 / 预留能力

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| 统一响应格式 | ✅ 已实现 | `{ code: 0, message: "success", data: {} }` + 全局异常兜底 |
| 健康检查 | ✅ 已实现 | MySQL / Redis 实时连通性探测 |
| 数据库迁移 | ✅ 已实现 | Alembic 初始迁移创建 users 表 |
| JWT 工具类 | ✅ 已实现 | 签发 / 解析 / 预留鉴权依赖 |
| 注册登录接口 | 🚧 路由签名就绪 | `POST /api/v1/auth/register`、`POST /api/v1/auth/login`（返回 501） |
| 华为云盘古大模型 | 🚧 客户端骨架就绪 | `app/utils/ai_client.py`，待填 API Key 与端点 |
| PgVector 向量库 | 🚧 配置预留 | `.env` 中含连接配置占位 |
| 技能图谱 / 雷达图 | 🚧 渲染骨架就绪 | AntV G6 / ECharts 示例可交互 | 
| 各业务页面 | 🚧 占位 | 首页任务栏 / 导师对话 UI 等已搭好 UI 骨架 |

---

## 环境变量说明

所有配置项均从环境变量 / `.env` 读取（后端 `app/core/config.py`），关键项：

- `MYSQL_*`：MySQL 连接配置（Compose 下 host 为 `mysql`）
- `REDIS_*`：Redis 连接配置（Compose 下 host 为 `redis`）
- `JWT_SECRET_KEY`：JWT 签名密钥，**生产环境务必替换为随机强密钥**
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(64))"
  ```
- `HUAWEI_LLM_*`：华为云大模型（盘古）接入占位，参考
  [华为云 ModelArts 文档](https://support.huaweicloud.com/modelarts/)

---

## 常见问题

**Q：健康检查显示 mysql / redis 未连接？**
本地开发时请先启动 MySQL 与 Redis，或直接用 `docker compose up -d mysql redis` 拉起基础设施。

**Q：如何进行后续数据库表结构的迭代？**
```bash
cd backend && source .venv/bin/activate
alembic revision --autogenerate -m "add some table"
alembic upgrade head
```

---

## 路线图（Roadmap）

- [x] v0.1.0 项目框架：前后端骨架、基础设施、示例页面
- [ ] v0.2.0 用户体系：注册 / 登录 / JWT 鉴权闭环
- [ ] v0.3.0 职业规划：AI 应用开发工程师技能图谱与差距分析
- [ ] v0.4.0 AI 导师：接入华为云盘古大模型对话与学习记忆
- [ ] v0.5.0 自适应学习：个性化学习路径 + RPG 关卡机制

---

## License

内部预览使用（暂未指定开源协议）。