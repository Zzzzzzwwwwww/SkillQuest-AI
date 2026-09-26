# SkillQuest AI —— 码道使用记录（Coding Log）

> 按华为云码道使用要求，完整保留每一模块的 Prompt、对话要点、代码生成、排错与重构过程。
> 每个模块完成时追加一节；格式统一，便于评审与追溯。

---

## 记录模板

```
### [模块 N] 模块名
- 日期：
- 用户 Prompt 摘要：
- 码道执行动作：
- 生成/修改文件：
- 验证结果：
- 排错/重构记录：
- 结束状态：
```

---

## 模块 1：项目框架（前后端 + Docker + 数据库连接 + 多智能体骨架）

- **日期**：2026-09-26
- **用户 Prompt 摘要**：确认 SkillQuest AI 完整实现思路（规则优先/结构化 JSON/多智能体/数据闭环），按开发顺序从项目框架开始，每模块完成后等待确认。
- **码道执行动作**：
  1. 复用上一轮已生成的基础框架（FastAPI 后端 + Vue3 前端 + Docker Compose + Alembic 初始迁移 users 表）。
  2. 补齐框架级基础设施：
     - 新增 LLMService（`app/services/llm.py`）：统一调用华为云大模型，提供 `chat()` 与结构化 `chat_json()`（含代码围栏剥离、JSON 解析失败自动重试、盘古/OpenAI 返回结构兼容）。
     - 新增 8 个 Agent 定义（`app/agents/prompts.py`）：Orchestrator / Career / Skill / Learning / Tutor / Assessment / Coach / Reflection，每个含中文系统提示词与固定 JSON Schema。
     - 新增 Agent 基类与调度执行器（`app/agents/base.py`）：`BaseAgent.run()` + `AgentRunner`，未配置大模型时返回可渲染的降级结构。
     - docker-compose 增加 PgVector（pg16）服务 + 数据卷 + backend 注入 `PGVECTOR_HOST`。
  3. 验证后端可启动、健康检查/统一响应格式正常。
- **生成/修改文件**：
  - 新增：`backend/app/services/llm.py`、`backend/app/agents/prompts.py`、`backend/app/agents/base.py`、`CODING_LOG.md`
  - 修改：`docker-compose.yml`（+pgvector）
- **验证结果**：后端 uvicorn 启动成功；`GET /api/v1/health`、统一 404、`/docs` 均正常；`python -c "import app.main"` 通过；Agent 模块 import 无语法错误。
- **排错/重构记录**：
  - 上一轮排错：passlib/bcrypt 版本兼容、health 接口不应依赖 DB 会话（改为探测式）、前端 TS18048 类型错误（`status >= 500` 需判类型）——均已修复。
  - DevBridge 公网分享链路：隧道创建成功但网关 WebSocket 握手持续 401（服务端令牌校验问题），已在上一轮说明，预留隧道 `lp47dr35` 待服务恢复后重试。
- **结束状态**：模块 1 完成。数据库迁移仍为初始 `20260101_0001`（users 表）；待用户确认后进入模块 2（用户管理）。

---

## 模块 2：用户管理（注册/登录/个人中心/学习档案/学习记录/测评报告）

- **日期**：2026-09-26
- **用户 Prompt 摘要**：按上一轮确认的模块划分，实现用户管理模块：5 张表（users 扩展 + user_profiles / learning_archives / learning_records / assessment_reports）、7 个接口（POST auth/register、POST auth/login、GET users/me、PUT users/profile、GET users/learning-archive、GET users/learning-records、GET users/assessment-reports）、JWT 鉴权 + 刷新保持登录、密码 bcrypt、统一错误处理、前端路由守卫。
- **码道执行动作**：
  1. **后端数据层**：新增 4 张业务表模型（profile/learning/assessment），扩展 users 表（phone/avatar/status），`models/__init__.py` 统一导出；新增 Alembic 迁移 `20260102_0002_user_module_tables`。
  2. **后端 API 层**：定义泛型 `ApiResponse[T]` / `PageParams` / `PageResult` 统一响应与分页模板；升级 `core/security.py`（bcrypt 哈希 + JWT；`get_current_user` 从 DB 加载完整实体并校验 status）；实现 auth（注册自动初始化学习档案+画像、登录）与 users 五个接口（等级规则引擎：`cumulative_xp=50*level*(level-1)`，`level_from_xp` 反推）。
  3. **端到端测试**：`tests/test_user_module_e2e.py`（TestClient + SQLite 内存替身），24 条断言全过，覆盖注册/登录/鉴权失败/画像更新/档案统计/记录与报告分页/禁用用户拦截。
  4. **前端**：新增 `types/user.ts`（全部类型）、`api/auth.ts`、`api/user.ts`、pinia `store/user.ts`（token+user 持久化、restoreSession、401 清理）；重写 `router/index.ts`（登录守卫 + `redirect` 回跳）；页面：Login / Register / Profile（入口四宫格）/ ProfileCenter / Archive / Records / Reports；`BasicLayout.vue` 菜单拆出「成长档案」子菜单（桌面+移动端双模板）。
  5. **前端构建验证**：修复 6 个 vue-tsc 错误（未使用导入 ×4、`fetchMe` 返回类型改为 `UserWithProfile`），`npm run build` 通过。
- **生成/修改文件**：
  - 新增（后端）：`app/models/{profile,learning,assessment}.py`、`app/schemas/{common,user}.py`、`app/api/v1/endpoints/{auth,users}.py`、`alembic/versions/20260102_0002_user_module_tables.py`、`tests/test_user_module_e2e.py`
  - 修改（后端）：`app/models/{__init__,user}.py`、`app/models/base.py`、`app/core/security.py`、`app/api/v1/router.py`、`app/api/v1/endpoints/__init__.py`
  - 新增（前端）：`src/types/user.ts`、`src/api/{auth,user}.ts`、`src/views/auth/{Login,Register}.vue`、`src/views/{Profile,ProfileCenter,Archive,Records,Reports}.vue`
  - 修改（前端）：`src/store/user.ts`、`src/router/index.ts`、`src/api/request.ts`、`src/layouts/BasicLayout.vue`
- **验证结果**：
  - 后端 E2E：`pytest tests/test_user_module_e2e.py -q` → **24 passed**。
  - 前端：`npm run build`（vue-tsc + vite）→ 构建成功（22.8s），无类型错误。
  - 沙箱进程：后端 uvicorn（:3000）与前端 vite dev（:3002）均运行中。
- **排错/重构记录**：
  - SQLite 替身下 `BigInteger` 主键不自增 → 注册 `@compiles(BigInteger, "sqlite")` 返回 INTEGER。
  - `Base` 基类上声明 `id/created_at/updated_at` Mapped 注解会令子类继承成无默认值裸列（NOT NULL 报错）→ 从基类移除，改由各模型显式声明。
  - 前端 `response_model` 直接返回模型会绕过统一包装 → 全部改用 `response_model=ApiResponse[T]` + `success()`。
  - 等级规则断言易错（500 XP 应为 3 级、升级需 600 XP）→ 测试用独立 `XP_FOR_LEVEL_3` 常量断言。
  - vue-tsc 报 6 错：4 个未使用图标/请求方法导入、`fetchMe` 返回类型应为 `UserWithProfile` → 已修复。
- **结束状态**：模块 2 完成。线上后端进程仍为旧代码（连不上 MySQL），新接口以 E2E 测试结果为验证依据；用户本地 `alembic upgrade head` + 重启后端 + 前端 dev 即可完整体验。待用户确认后进入模块 3（职业测评与画像）。

---

## 模块 3：职业测评与画像（测评试卷/答题/结果/推荐岗位 + 用户画像）

- **日期**：2026-09-26
- **用户 Prompt 摘要**：按上一轮确认的模块划分，实现职业测评与画像：5 张表（assessment_papers / assessment_questions / assessment_answers / assessment_results / user_personas）、题型单选/多选/量表/简答、10 个测评维度（逻辑/编程/数据/空间/语言/动手/兴趣/职业价值观/学习目标/职业意向）、5 个接口（GET papers、GET questions、POST submit、GET result/{id}、GET persona/current、POST persona/generate——用户清单 5 个，补充 papers 列表接口共 6 个）、规则评分 + Career Agent 推荐 Top3 职业 + 匹配理由与技能差距、前端 4 页（测评中心/答题页/结果页/画像页）。
- **码道执行动作**：
  1. **数据层**：`models/assessment.py` 扩展 4 个新模型（Paper/Question/Answer/Result），新建 `models/persona.py`（UserPersona，一对一）；Alembic 迁移 `20260103_0003` 建 5 表含索引与级联删除。
  2. **评分规则引擎** `services/assessment_scoring.py`：四种题型独立评分子规则（单选分值映射、多选求和封顶、量表线性映射、简答长度+关键词启发式，全部归一 0-100）；维度聚合=维内题目均值；总分=维度均值；雷达图=ECharts 数据；兴趣/价值观从作答解析。
  3. **职业推荐规则引擎** `services/career_recommender.py`：8 个职业库（权重向量 + 必备技能门槛 + 概述）；匹配度=维度加权归一；匹配理由=规则模板；技能差距=threshold-current；LLM 不参与算分。
  4. **画像构建** `services/persona_builder.py`：规则标签（阈值 70/55）+ 组合数据；Career Agent（LLM 可选）增强综述/优势/短板/建议，未配置自动降级规则模板；目标岗位解析（意向文本命中职业库名优先）。
  5. **接口**：`endpoints/assessment.py`（4 个，试卷列表含题数、取题不泄露 score_rule、提交评分落库并同步写 career 测评报告 + 学习轨迹、结果详情返回雷达/推荐/差距）；`endpoints/persona.py`（current 未生成返回 data=null、generate 基于最近测评 upsert）。
  6. **种子**：`app/db/seed_assessment.py` + `scripts/seed_assessment.py`（12 题覆盖 10 维，幂等写入）。
  7. **端到端测试** `tests/test_assessment_persona_e2e.py`：56 条断言全过（题型评分单测、完整答题闭环、维度分/雷达/推荐排序/差距字段、缺题拦截、无 token 拦截、报告与轨迹联动、画像生成与 upsert 幂等）。
  8. **前端**：`types/assessment.ts`、`api/assessment.ts`、`api/persona.ts`；组件 `AbilityRadarChart.vue`（ECharts 雷达，可复用）；4 页：AssessmentCenter（试卷卡片）、Answering（进度条/上一题下一题/四种题型渲染/未答拦截/提交确认）、ResultView（雷达+维度条+Top3 岗位卡+技能差距+生成画像入口）、Persona（空态引导/标签/雷达/优势短板/学习目标/兴趣价值观）；路由 4 条 + 菜单「职业测评」子菜单（测评中心/个人画像）。
  9. **沙箱演示**：因无 MySQL，新增 `scripts/run_demo_sqlite.py`（SQLite 文件库替代 + create_all + 种子 + 演示账号 hunter/skillquest123）；演示后端 3900 + `vite preview` 3901（`.env.production` 代理到 3900），全链路冒烟通过。
- **生成/修改文件**：
  - 新增（后端）：`app/models/persona.py`、`app/services/{assessment_scoring,career_recommender,persona_builder}.py`、`app/api/v1/endpoints/{assessment,persona}.py`、`app/schemas/{assessment,persona}.py`、`app/db/seed_assessment.py`、`alembic/versions/20260103_0003_assessment_persona_tables.py`、`scripts/{seed_assessment,run_demo_sqlite}.py`、`tests/test_assessment_persona_e2e.py`
  - 修改（后端）：`app/models/assessment.py`（+4 模型）、`app/models/__init__.py`、`app/db/base.py`、`app/api/v1/router.py`
  - 新增（前端）：`src/types/assessment.ts`、`src/api/{assessment,persona}.ts`、`src/components/AbilityRadarChart.vue`、`src/views/assessment/{AssessmentCenter,Answering,ResultView}.vue`、`src/views/persona/Persona.vue`、`.env.production`
  - 修改（前端）：`src/router/index.ts`、`src/layouts/BasicLayout.vue`
- **验证结果**：
  - 后端 E2E：`tests/test_assessment_persona_e2e.py` → **PASS=56 FAIL=0**。
  - 前端：`npm run build`（vue-tsc + vite）→ 构建成功（23.1s），无类型错误。
  - 沙箱演示全链路：登录 → papers → questions（无评分规则）→ submit（74 分，Top1=AI/算法工程师）→ result（Top3 雷达 6 维）→ persona generate（目标岗位+规则标签）冒烟全部通过。
- **排错/重构记录**：
  - `get_result` 中列表推导式 `jobs = [... for j in jobs]` 触发 UnboundLocalError（迭代器遮蔽赋值变量）→ 改为 `raw_jobs`。
  - `persona/current` 未生成时 `success(None)` 会把 None 转成 `{}`，导致 `Optional[PersonaOut]` 校验失败 → 直接返回 `{"code":0,"data":None}`。
  - 简答关键词测试断言过严（输入过短）→ 调整测试文本后与规则一致。
  - 能力雷达图数据统一由 `build_radar_data` 规则构建（不再依赖报告快照），保证 GET /result 可独立重建。
- **结束状态**：模块 3 完成。沙箱演示地址（登录 hunter/skillquest123 可体验完整测评与画像流程）。配置华为云大模型 API Key 后，画像综述将由 Career Agent 自动增强（ai_enriched=true）。待用户确认后进入模块 4（技能图谱）。
## 模块 4：岗位技能图谱（技能库/岗位关联/掌握状态 + 前端图谱）

- **日期**：2026-09-26
- **用户 Prompt 摘要**：按上一轮确认的模块划分，实现岗位技能图谱：4 张表（jobs / skill_nodes / job_skill_relations / user_skill_status）、层级结构（岗位族→岗位→能力域→技能→知识点）、掌握状态（已掌握/学习中/未掌握）、5 个接口（GET /jobs、GET /jobs/{id}/skill-tree、GET /users/{id}/skill-status、PUT /users/skill-status、GET /skills/{id}/detail——实现为 6 个，含 jobs 列表分页前补充）、前端 4 项（岗位选择页、技能图谱页 AntV G6/ECharts 树图、节点颜色绿/黄/灰、点击节点侧边栏详情）。
- **码道执行动作**：
  1. **数据层**：`models/skill.py` 新增 4 模型（Job/SkillNode/JobSkillRelation/UserSkillStatus，SK 树父子自引用、relation 唯一约束、级联删除）；Alembic 迁移 `20260104_0004` 建 4 表含索引与状态约束。
  2. **技能树服务** `services/skill_tree.py`：`SkillTreeBuilder`（job→能力域→技能→知识点组装，能力域由技能祖先聚合、未从属于任何能力域的技能挂"其他"；required_level/importance 标注在技能粒度、能力域 importance=子技能均值）；`infer_status`/`normalize_status` 规则（≥80 mastered、1~79 learning、0 not_started）；`compute_skill_gaps`（掌握度加权平均 + 匹配率 fit_rate + 差距项按 importance 降序）；`build_skill_detail`（前置知识按名称匹配并附掌握状态、未入库名称占位、3 条规则化推荐资源、关联岗位按 importance 降序）。
  3. **接口**：`endpoints/skills.py`（jobs 列表含技能数、skill-tree 叠加当前用户状态+gap 汇总、skills/{id}/detail）；`endpoints/users.py` 追加 GET /users/{id}/skill-status（本人或超管，否则 403）与 PUT /users/skill-status（批量 upsert、节点存在性校验、缺省状态按掌握度推导）。
  4. **种子**：`app/db/seed_skill.py` + `scripts/seed_skill.py`（6 能力域/15 技能/43 知识点/6 岗位/岗位技能关联，数据幂等写入）。
  5. **端到端测试** `tests/test_skill_tree_e2e.py`：51 条断言全过（种子统计/岗位列表与筛选/技能树结构三层/状态读写与推导/状态叠加与 Gap/技能详情/状态规则单测、无 token/越权/不存在节点拦截）。
  6. **前端**：`types/skill.ts`、`api/skill.ts`；岗位选择页 `views/skill/JobSelect.vue`（按岗位族分组卡片、技能数、点击进图谱）；技能图谱页重写 `views/SkillTree.vue`（ECharts 树图、节点颜色绿/黄/灰随掌握状态、点击节点侧边栏详情抽屉（掌握进度/快速标记/前置知识/推荐资源/关联岗位）、Skill Gap 分析区（综合掌握度/匹配度双仪表 + 差距表格）、状态筛选（全部/已掌握/学习中/未掌握）、一键展开/折叠、岗位切换、统计概览）；路由 2 条 + 菜单「技能图谱」子菜单（岗位选择/技能图谱）。
  7. **沙箱演示**：`scripts/run_demo_sqlite.py` 追加 `seed_skill`，删除旧 `sq_demo.db` 重建，演示后端 3900 + `vite preview` 3901 重启，全链路冒烟通过（登录→岗位列表 6→技能树含 gap 汇总）。
- **生成/修改文件**：
  - 新增（后端）：`app/models/skill.py`、`app/services/skill_tree.py`、`app/schemas/skill.py`、`app/api/v1/endpoints/skills.py`、`app/db/seed_skill.py`、`alembic/versions/20260104_0004_skill_graph_tables.py`、`scripts/seed_skill.py`、`tests/test_skill_tree_e2e.py`
  - 修改（后端）：`app/models/__init__.py`、`app/db/base.py`、`app/api/v1/router.py`、`app/api/v1/endpoints/users.py`（+技能状态 GET/PUT）、`scripts/run_demo_sqlite.py`（+seed_skill）
  - 新增（前端）：`src/types/skill.ts`、`src/api/skill.ts`、`src/views/skill/JobSelect.vue`
  - 修改（前端）：`src/views/SkillTree.vue`（占位→完整图谱页）、`src/router/index.ts`、`src/layouts/BasicLayout.vue`
- **验证结果**：
  - 后端 E2E：`tests/test_skill_tree_e2e.py` → **PASS=51 FAIL=0**。
  - 前端：`npm run build`（vue-tsc + vite）→ 构建成功（15.5s），无类型错误。
  - 沙箱演示全链路：登录 → /jobs（6 岗位含技能数）→ /jobs/3/skill-tree（数据分析师：5 能力域/6 技能 gap 汇总）冒烟全部通过；演示库已重建（含模块4 4 张新表）。
- **排错/重构记录**：
  - `SkillTreeBuilder.build()` 中 `caps` 为 dict，原 `for cap in caps` 遍历到整数键 → `AttributeError: 'int' object has no attribute 'id'` → 改 `for cap in caps.values()`。
  - `_subtree` 从 `_node_cache` 取节点，但知识点未入缓存 → 返回空 dict 导致 Pydantic `Field required` → 改为直接接收节点对象，知识子树递归不受缓存限制。
  - PUT skill-status 的 `status` 设为必填 → 测试期望缺省推导（learning/not_started）→ 改为 `Optional[str]`，服务层 `normalize_status` 缺省按掌握度推导。
  - 前端预览卡片与抽屉功能重复 → 移除侧栏预览块，统一用抽屉承载详情；展开/折叠由 `expandedSet` 重构为 `initialTreeDepth`（100/2）随按钮切换。
- **结束状态**：模块 4 完成。沙箱演示地址：前端 3901 / 后端 3900（登录 hunter/skillquest123 可体验岗位选择与技能图谱、点击节点查看详情并快速标记掌握状态、查看 Skill Gap 分析）。待用户确认后进入模块 5（个性化导学）。

## 模块 5：个性化导学（学习路径生成/分段地图/进度断点/资源推荐）

- **日期**：2026-09-26
- **用户 Prompt 摘要**：按确认的模块划分实现个性化导学：数据库 5 张表（learning_paths 含 current_node_id 断点指针、learning_path_nodes 含 stage/order_no/status/estimated_hours/prerequisites_json、learning_resources、learning_progress 含 progress_percent/last_position、resource_recommendations）；生成逻辑=用户画像+目标岗位+技能短板+岗位重要度+前置知识，调用 Learning Agent 生成路径，分段 青铜→白银→黄金→铂金→钻石→王者；后端 6 接口（POST /learning-path/generate、GET /learning-path/current、PUT /learning-progress、GET /learning-resources/recommend、POST /learning-progress/resume、GET /learning-path/{id}/map）；前端 5 项（冒险地图页-节点/路线/段位、学习路径详情页-阶段/技能/时长/资源、资源推荐卡片、学习进度条、断点续学按钮）。
- **码道执行动作**：
  1. **数据层**：`models/learning_path.py` 新增 5 模型（LearningPath/LearningPathNode/LearningProgress/LearningResource/ResourceRecommendation，含 STAGES 六段位常量、节点状态约束、current_node_id 断点指针）；Alembic 迁移 `20260105_0005`（先建节点表再建路径表保证外键顺序）。
  2. **路径规划规则引擎** `services/learning_path_service.py`：`plan_path`（岗位技能+能力域展开成技能池、缺口 gap=required-mastery 加权、拓扑排序前置优先+重要度降序、6 段位均分、时长按重要度/层级规则估算）；`_topo_sort_skills`（DFS 后序+环保护）；段位目标规则模板 `STAGE_OBJECTIVES`。
  3. **Learning Agent 增强**：`enhance_with_learning_agent` 仅增强路径名称与各段位目标说明（LEARNING prompt），LLM 未配置自动降级规则模板，前端不中断（第1/3条设计原则）。
  4. **路径状态规则**：`compute_progress_map`（按 skill_node 聚合进度）、`_derive_status`/`build_path_map`（≥80 completed、>0 learning、前置全掌握 unlocked、否则 locked）、`should_complete_path`（全部≥80 即完成）；`set_user_status_map` 接口层注入用户掌握状态便于解锁判定。
  5. **接口**：`endpoints/learning.py` 挂 6 路由：generate（幂等复用/force 重建/越权 404）、current（无路径 data=null）、map、PUT progress（更新进度+掌握状态同步+`_refresh_path_status` 推进 current 指针并置 completed）、resume（断点续学带出 last_position，current 无断点时回退最近有位置记录）、recommend（规则评分排序+持久化推荐记录）。
  6. **资源推荐规则** `recommend_resources`：关联节点展开（技能→自身+知识点；能力域→其下全部）、基础分60+难度适中+时长适中+直接关联+类型性价比，理由模板化，按分降序取 topN。
  7. **种子**：`app/db/seed_learning.py` + `scripts/seed_learning.py`（技能+45 知识点各 4 类资源，幂等按标题去重）。
  8. **端到端测试** `tests/test_learning_path_e2e.py`：61 条断言全过（注册→种子→生成→6段位→幂等→force 切岗→地图→进度更新/指针推进→断点续学→越权404→全员完成 completed→技能状态落库→服务规则单测）。
  9. **前端**：`types/learning_path.ts`（含 STAGE_META 六段位展示元数据）、`api/learning_path.ts`（6 接口封装）；冒险地图页重写 `views/LearningPath.vue`（路径总览卡片+渐变总进度条+断点续学按钮+6 段位路线图节点按状态着色+节点点击抽屉详情/更新进度/推荐资源卡片）；新增 `views/LearningPathDetail.vue`（返回按钮+头部统计+分阶段节点卡片列表+详情抽屉）；路由新增 `/adventure/:pathId`。
  10. **沙箱演示**：`scripts/run_demo_sqlite.py` 追加 `seed_learning_resources`，删除旧 `sq_demo.db` 重建，演示后端 3900 + `vite preview` 3901 重启，全链路冒烟通过（登录→generate 11 节点 6 段位→recommend→resume）。
- **生成/修改文件**：
  - 新增（后端）：`app/models/learning_path.py`、`app/services/learning_path_service.py`、`app/schemas/learning_path.py`、`app/api/v1/endpoints/learning.py`、`app/db/seed_learning.py`、`alembic/versions/20260105_0005_learning_path_tables.py`、`scripts/seed_learning.py`、`tests/test_learning_path_e2e.py`
  - 修改（后端）：`app/models/__init__.py`、`app/db/base.py`、`app/api/v1/router.py`（+learning-router）、`scripts/run_demo_sqlite.py`（+seed_learning_resources）
  - 新增（前端）：`src/types/learning_path.ts`、`src/api/learning_path.ts`、`src/views/LearningPathDetail.vue`
  - 修改（前端）：`src/views/LearningPath.vue`（占位→冒险地图页）、`src/router/index.ts`（+/adventure/:pathId）
- **验证结果**：
  - 后端 E2E：`tests/test_learning_path_e2e.py` → **PASS=61 FAIL=0**。
  - 前端：`npm run build`（vue-tsc + vite）→ 构建成功（16.8s），无类型错误，LearningPath/LearningPathDetail 分包正常。
  - 沙箱演示全链路：登录 hunter → generate（AI 应用开发工程师，11 节点 6 段位，active）→ recommend（8 条资源含理由/评分）→ resume（带断点位置）；演示库已重建（含模块5 5 张新表）。
- **排错/重构记录**：
  - 测试配置 `SessionLocal(autoflush=False)`（全项目基础设施）导致 PUT progress 新写 LearningProgress 行在 `_refresh_path_status` 内 `compute_progress_map` 查询读不到 → 指针不推进、completed 不触发 → 统一在 `_refresh_path_status` 开头 `db.flush()` 解决。
  - 种子资源断言期望 `(15+43)*4=232` 实际 `240`（KNOWLEDGE 知识点实际 45）→ 测试期望修正为 240。
  - 后端岗位技能数断言期望 6 实际 7：`plan_path` 会把前置技能（如 JS/TS 之于后端）也纳入技能池，属合理生成逻辑 → 测试期望修正为 7（含前置）。
  - 断点续学 resume 在 current 指针已推进到无 last_position 的下一节点时位置丢失 → 回退查询该路径最近带 last_position 的进度记录补全。
  - agent_note 原用 `stage_options != meta["stages"]` 推断（两者结构不同永远不等，误报"增强已启用"）→ 改为直接判断 `llm_service.is_configured`。
- **结束状态**：模块 5 完成。沙箱演示地址：前端 3901 / 后端 3900（登录 hunter/skillquest123 可体验：冒险地图 6 段位路线图、点击节点更新进度与断点、断点续学、资源推荐卡片）。配置华为云大模型 API Key 后，路径名称与段位目标将由 Learning Agent 自动增强（agent_note 显示）；未配置时规则模板自动降级。待用户确认后进入模块 6。

## 模块 6：智能答疑（RAG）（文档上传/向量检索/重排/华为云大模型问答/引用+推荐练习）

- **日期**：2026-09-26
- **用户 Prompt 摘要**：按确认的模块划分实现智能答疑（RAG）模块：数据库 5 张表（chat_sessions、chat_messages、knowledge_documents、knowledge_chunks、qa_logs）；RAG 流程=上传文档→文本切分→Embedding→PgVector→检索→重排→组装 Prompt→华为云大模型→答案+引用+推荐练习；后端 5 接口（POST /chat/session、POST /chat/message、GET /chat/history、POST /knowledge/upload、GET /knowledge/search）；前端=AI 导师聊天页 + SSE 流式输出 + 显示引用来源 + 关联知识点 + 推荐相关练习 + 历史会话；硬性要求=答案必须带引用、检索不到必须明确说明、结合用户当前学习进度回答。
- **码道执行动作**：
  1. **数据层**：`models/chat.py` 新增 5 模型（ChatSession/ChatMessage/KnowledgeDocument/KnowledgeChunk/QaLog，knowledge_session 建立会话-文档关系、状态约束 uploaded/processing/ready/failed、所有模型显式声明 id/created_at 列）；`models/__init__.py` 与 `db/base.py` 导出；Alembic 迁移 `20260106_0006` 建 5 表（chunks 预置索引、外键级联删除）。
  2. **RAG 服务** `services/rag.py`：
     - `split_text`：段落级切块 + 超长段落按句拆分 + overlap 拼接，中文标点兜底；`build_embedding_text` 标题+内容。
     - `EmbeddingService.embed`：配置 `HUAWEI_EMBEDDING_*` 走华为云 Embedding 接口；未配置自动降级 `rule_embed`（字符 n-gram 哈希稀疏向量 258 维，纯规则不依赖模型），`embedding_mode` 落库标记 rule/model；`index_document` 切分→向量→批量落库（embedding 以 string 存 JSON 数组）。
     - `retrieve_chunks`：EVENT_STORE 会话事件档案缓存（同会话合并加分）+ keyword match（0.3）+ cosine 相似度（0.7）加权求和，`_MIN_SCORE=0.25` 以下丢弃；`apply_rerank` 重排（MMR 多样性 + LLM 可选）；`format_references` 引用来源=检索命中结构化生成（标题+文档名+分数），LLM 不参与引用决定（写死原则：能检索的不靠大模型编）。
     - `build_learning_context`：结合用户 skill 掌握度/learning_path 当前节点，基于用户覆盖全部技能 → 回答进个性化的 not_started 技能；`recommend_practices` 按技能高分 + 状态推导推荐练习（来自可选用例 `PRACTICE_BANK` 字典）；`map_related_skills` 关键词关联技能节点。
     - `build_tutor_prompt`：系统提示=中国程序员 IT 职业助教、结合档案/学习路径/阶段；邮件=引用+回答源；未命中时明确告知知识库暂无相关内容并给出引导。
  3. **LLM 流式** `services/llm.py` 新增 `chat_stream()`：无需调用方管理全局上下文，后端基于 `AsyncClient`（POST 自动新建、`ChatOpenAI` 重试），`async for` 按行解析 `data:` JSON，`choices[0].delta.content`；错误记录 one_line。`is_configured` 增加 `stream` 判断；`llm.chat` 传 `use_stream=False`。
  4. **接口** `api/v1/endpoints/chat.py`（chat_router + knowledge_router）：POST `/chat/session`（新建/复用会话）、POST `/chat/message`（SSE 流：`_answer_flow` 内部用 `SessionLocal()` 自建 Session；事件 `delta`/`answer`/`references`/`knowledge`/`practice`/`done` 六个独立事件；首轮语言 `first_delta` 判断仍用 `delta`）、GET `/chat/history`、POST `/knowledge/upload`（文件读入+入 chunk+状态）、GET `/knowledge/search`（检索=返回及时结果）；qa_logs 记录落库。
  5. **种子** `app/db/seed_knowledge.py` 5 篇示例文档（Python 异常/虚拟环境/HTTP缓存/Express 中间件/TS 类型注解各 2-3 段落，幂等按标题跳过）；`scripts/run_demo_sqlite.py` 追加 `seed_knowledge`。
  6. **端到端测试** `tests/test_chat_rag_e2e.py`：46 条断言全过（多轮会话、引用带分数、`sufficient=True`、未命中 `sufficient=False` 无引用并明确「知识库暂无相关内容」、长期读不到 session（>30min）提示重新开始、知识域名 recommends/计算建议/知识节点、上传后台日志无异常、search 命中 3 篇、上传依赖 `content`+`file_type`+`description` 返回 id）。
  7. **前端**：`types/tutor.ts`、`api/tutor.ts`（`sendChatMessageStream` fetch SSE 流式解析 `data:` 行、逐条 emit delta/answer/references/knowledge/practice/done，支持 VITE_API_BASE）；重写 `views/Tutor.vue`（左侧历史会话列表+新建会话；中部 SSE 聊天窗口渲染 Markdown 答案+引用卡片+关联知识点+推荐练习；右侧可在知识文档输入框处理、上传后列表显示文档状态）。
  8. **前端构建验证**：清理 Delete/ElMessageBox 未使用导入，`npm run build` 通过。
  9. **沙箱演示**：`scripts/run_demo_sqlite.py` 追加 `seed_knowledge`，删除旧 `sq_demo.db` 重建，演示后端 3900 + `vite preview` 3901 重启，全链路冒烟通过（登录→search 命中 3 篇→SSE 问答 sufficient=True 带引用/知识/练习→历史 2 条）。
- **生成/修改文件**：
  - 新增（后端）：`app/models/chat.py`、`app/services/rag.py`、`app/schemas/chat.py`、`app/api/v1/endpoints/chat.py`、`app/db/seed_knowledge.py`、`alembic/versions/20260106_0006_chat_rag_tables.py`、`tests/test_chat_rag_e2e.py`
  - 修改（后端）：`app/models/__init__.py`、`app/db/base.py`、`app/api/v1/router.py`（+chat/knowledge 路由）、`app/services/llm.py`（+chat_stream）、`app/core/config.py`（+HUAWEI_EMBEDDING_*）、`scripts/run_demo_sqlite.py`（+seed_knowledge）
  - 新增（前端）：`src/types/tutor.ts`、`src/api/tutor.ts`
  - 修改（前端）：`src/views/Tutor.vue`（占位→完整 AI 导师聊天页）
- **验证结果**：
  - 后端 E2E：`tests/test_chat_rag_e2e.py` → **PASS=46 FAIL=0**；回归 learning=61 FAIL=0、skill=51 FAIL=0 全绿。
  - 前端：`npm run build`（vue-tsc + vite）→ 构建成功（16-17s），无类型错误。
  - 沙箱演示全链路：登录 → search（命中 3 篇含文档标题/内容摘要）→ SSE 问答（sufficient=True、引用带文档标题与分数、关联知识点、推荐练习）→ 未命中分支（sufficient=False 无引用并明确说明）→ 历史会话 2 条；演示库已重建（含模块6 5 张新表 + 知识种子）。
- **排错/重构记录**：
  - **SSE DetachedInstanceError**：FastAPI 依赖 `get_db` 会在生成器被迭代前关闭，SSE 过程中访问 SQLAlchemy 对象报 DetachedInstanceError → `_answer_flow` 改为内部 `SessionLocal()` 自建 Session，`send_message` 提前捕获 uid/sid 传参，不再依赖注入 session。
  - **检索阈值**：`_MIN_SCORE` 从 0.05 调至 0.25，修复 0.168 分无关问题「量子引力」被误判命中 → 改为返回空并明确说明。
  - **SSE 事件设计**：原方案用 `meta` 单事件包装失败 → 改为 `delta`/`answer`/`references`/`knowledge`/`practice`/`done` 六个独立事件；前端解析与 E2E 断言随之适配。
  - 前端 vue-tsc 报错：`Delete`、`ElMessageBox` 未使用导入 ×2 → 移除。
- **结束状态**：模块 6 完成。沙箱演示地址：前端 3901 / 后端 3900（登录 hunter/skillquest123 可体验：AI 导师聊天页 SSE 流式输出、引用来源卡片、关联知识点、推荐练习、历史会话、文档上传与检索）。配置华为云大模型 API Key 后自动走华为云 Embedding + 流式问答（embedding_mode=model）；未配置时规则向量与规则回答自动降级（embedding_mode=rule），检索/引用/练习全部规则可用。待用户确认后进入模块 7。

---

## 模块 7：学习评估复盘（阶段测评 / 知识点掌握度 / 学习报告 / PDF 导出）

- **日期**：2026-09-26
- **用户 Prompt 摘要**：要求生成模块 7 学习评估复盘模块：6 张表（stage_exams / exam_questions / exam_records / exam_answers / knowledge_mastery / learning_reports）、7 个接口（POST exam/start、POST exam/submit、GET exam/result/{id}、GET mastery、GET report/{id}、GET report/export/pdf、POST report/generate）；规则算总分 → 各知识点掌握度 → 调用 Assessment Agent 识别薄弱知识点 → 生成能力雷达图 → 学习趋势 → 推荐下一步任务；前端含阶段测评页、测评结果页（分数/雷达图/知识点掌握）、掌握度热力图、学习报告页、PDF 导出按钮；报告内容含总体评价、优势、薄弱点、建议、下一步；支持历史报告查看。
- **码道执行动作**：
  1. **数据层**：`models/assessment_review.py` 新增 6 模型（StageExam/ExamQuestion/ExamRecord/ExamAnswer/KnowledgeMastery/LearningReport），题目支持单选/多选/判断并以 knowledge_point_id 关联技能图谱知识点，knowledge_mastery 建立 user×kp 唯一约束；`models/__init__.py` 与 `db/base.py` 导出；Alembic 迁移 `20260108_0008` 建 6 表（级联删除 + 索引）。
  2. **规则服务** `services/exam_service.py`（写死原则：能规则算的不用大模型）：`is_answer_correct` 单选比 key/多选比集合/判断比布尔；`submit_exam` 逐题评分汇总 → `_upsert_masteries` 按知识点聚合得分率滚动更新（加权平均 + review_count）；`build_exam_result` 聚合题目对错/掌握度/能力域雷达（C=能力域·技能 链路，无父级归入其他）/学习趋势/薄弱点（<60 分优先本卷覆盖）/next_steps（关联 learning_resources 的视频/课程/练习优先推荐，无资源则建议专项练习）；`get_mastery` 掌握度总览 + 热力图矩阵结构。
  3. **报告服务** `services/report_service.py`：`build_rule_report` 规则生成总体评价（≥90 优异 / ≥60 良好 / <60 需补强）、优势（≥70）、薄弱、建议（间隔重复 1/3/7 天 + AI 导师追问）、下一步；`generate_report` 可选 Assessment Agent 增强（LLM 未配置自动降级规则文案，前端 `ai_enriched=false` 标记）；`pdf_url` 暂无落库，导出用 reportlab + `UnicodeCIDFont(STSong-Light)` 零字体文件生成中文 PDF。
  4. **接口** `api/v1/endpoints/exam_review.py` 三个 router（exam/mastery/report）共 8 个端点（新增 GET /exam/list 供前端试卷列表）；路由顺序 `export/pdf`、`list` 置于 `/{report_id}` 之前避免被动态段吞掉；`app/api/v1/router.py` 挂载 trio，`app/main.py` 额外挂载 `/api` 别名（/api/exam、/api/mastery、/api/report）。
  5. **种子** `app/db/seed_exam.py` 2 套试卷（青铜：数据结构与算法/机器学习入门 5 题；白银：Prompt 设计/RAG/特征工程 5 题，每套满分 100，题目关联真实知识点 id），幂等按标题判重；`scripts/run_demo_sqlite.py` 追加 `seed_exams`（demo 模式先 seed_skill 再 seed_exams）。
  6. **端到端测试** `tests/test_exam_review_e2e.py`：46 条断言全过（双用户注册 → 青铜/白银试卷 start 不下发答案 → 提交规则评分（错 1 题=80 分/4 对/及格）→ 重复提交 400 → 结果含掌握度/雷达 3 域/趋势 1 条/薄弱排序与查找=0 带建议/下一步非空 → mastery 热力图 → generate/缺省 record_id/list/detail → PDF 导出 content-type=application/pdf 且 %PDF 头 → 越权 404 / 不存在 400 / 未登录 401）。
  7. **前端**：`types/assessment_review.ts`（全量类型 + EXAM_STAGE_META 段位元信息）、`api/assessment_review.ts`（8 个 API + `downloadReportPdf` blob 下载）、`views/exam/ExamCenter.vue`（试卷卡片列表 + 答题弹窗：单选/多选/判断自动映射，缺题提示，提交跳结果页）、`ExamResult.vue`（成绩横幅/3 统计卡/能力雷达复用 AbilityRadarChart/学习趋势进度条/知识点掌握度/薄弱告警/下一步行动/答题明细折叠）、`MasteryView.vue`（ECharts 热力图 能力域×知识点 绿红着色 + 明细列表）、`ReportCenter.vue`（报告列表 + 生成最新报告 + 详情对话框含 AI 增强标记 + PDF 导出）；路由 `/exam` `/exam/result/:id` `/mastery` `/report`，侧边栏新增「学习评估」子菜单。
- **生成/修改文件**：
  - 新增（后端）：`app/models/assessment_review.py`、`app/schemas/assessment_review.py`、`app/services/exam_service.py`、`app/services/report_service.py`、`app/api/v1/endpoints/exam_review.py`、`app/db/seed_exam.py`、`alembic/versions/20260108_0008_assessment_review_tables.py`、`scripts/seed_exam.py`、`tests/test_exam_review_e2e.py`
  - 修改（后端）：`app/models/__init__.py`、`app/db/base.py`、`app/api/v1/router.py`（+exam/mastery/report 路由）、`app/main.py`（+/api 别名）、`scripts/run_demo_sqlite.py`（+seed_exams）
  - 新增（前端）：`src/types/assessment_review.ts`、`src/api/assessment_review.ts`、`src/views/exam/ExamCenter.vue`、`src/views/exam/ExamResult.vue`、`src/views/exam/MasteryView.vue`、`src/views/exam/ReportCenter.vue`
  - 修改（前端）：`src/router/index.ts`（+4 路由）、`src/layouts/BasicLayout.vue`（+「学习评估」子菜单）
- **验证结果**：
  - 后端 E2E：`tests/test_exam_review_e2e.py` → **PASS=46 FAIL=0**；全量回归 user=24、assess=56、skill=51、learning=66、chat=49 → 全绿（合计 292 条断言）。
  - 前端：`npm run build`（vue-tsc + vite）→ 构建成功，无类型错误。
  - 沙箱演示（新库 /tmp/sq_demo_m7.db，端口 3922/3923）：登录 hunter → 试卷列表 2 套 → start 5 题 → submit 80 分 → result radar=3/薄弱=排序与查找/趋势=1/下一步=1 → mastery 4 条+热力图 4 点 → report 生成（ai_enriched=false 规则降级）→ list 1 条 → PDF 200 application/pdf %PDF 头 3464B。
- **排错/重构记录**：
  - E2E 首轮 FAIL=7：测试把第 4 题（二分查找）错选 B，而 B 恰是该题正确答案 → 改错选 C（正确答案为 B 的干扰项），规则评分 80 分断言全绿。
  - 前端 vue-tsc 报 4 个 TS 错误：`qKey` 未使用删除；三处 `v-for :key` 使用可空 `knowledge_point_id`（number|null 不可作为路由 key）→ 改索引 key。
  - `ExamStartOut.questions` 不下发答案：start 端点 `_question_out` 仅吐 id/题型/题干/选项/分值/kp，避免作弊。
- **结束状态**：模块 7 完成。沙箱演示：后端 3922、前端 3923（hunter/skillquest123，菜单「学习评估：阶段测评 / 掌握度分析 / 学习报告」可体验完整闭环）。配置华为云大模型 API Key 后报告走 Assessment Agent 增强解读（ai_enriched=true）；未配置时全部规则计算自动降级，PDF 中文渲染零字体文件依赖。

---

## 模块 8：六大业务闭环（注册建档 / 测评画像 / 选岗路径 / 测评联动弱点 / 导师推送 / Boss 奖励）

- **日期**：2026-09-26
- **用户 Prompt 摘要**：要求实现六大业务闭环，确保数据在模块间自动流转：①注册后自动创建学习档案；②完成职业测评后自动生成画像并推荐岗位；③选定岗位后自动生成技能图谱与学习路径；④完成阶段测评后自动更新知识点掌握度并触发弱点诊断；⑤弱点诊断自动推送到 AI 导师页面；⑥完成 Boss 挑战后自动更新技能等级和 XP。
- **码道执行动作**：
  1. **数据层**：`models/business_loop.py` 新增 2 模型（WeaknessDiagnostic 弱点诊断：user×record×kp 唯一约束 + user×status 索引；BossChallenge Boss 挑战记录），状态常量 DIAG_NEW/NOTIFIED/TREATED、BOSS_STARTED/PASSED/FAILED、奖励常量 BOSS_PASS_BASE_XP=30 / BOSS_FAIL_BASE_XP=5；`models/__init__.py` 与 `db/base.py` 导出；Alembic 迁移 `20260109_0009_business_loop_tables.py`。
  2. **闭环2 自动画像** `services/persona_auto.py`：`auto_build_persona(db,user_id)` 复用 `persona_builder.build_persona_payload` 规则构建画像（无 Agent 增强，upsert 仅 1 行），`sync_target_job_to_archive` 回写 LearningArchive.target_job + UserProfile.job_intention；接入 `endpoints/assessment.py` submit 末尾（同事务）。
  3. **闭环3 选定岗位** `services/business_flow.py`：`select_target_job`（upsert persona + 回写档案）+ `auto_generate_learning_path`（复用 plan_path 规则生成 + LLM Agent 增强 + 落库 + 刷新节点状态）；接口 `POST /jobs/select`（JobSelectIn/Out 已加 `schemas/skill.py`）挂载 `skills.py`。
  4. **闭环4 阶段测评联动**（`services/exam_service.py`）：`submit_exam` 新增 `_sync_user_skill_status`（知识节点掌握度=本卷得分率，技能节点=知识节点均值，阈值 80 mastered / >0 learning）+ `_upsert_weakness_diagnostics`（掌握度 < MASTERY_WEAK(60) 落 WeaknessDiagnostic，同一 record 先 delete 再重建）；`endpoints/exam_review.py` submit 末尾补 LearningRecord(module=assessment) 打点。
  5. **闭环5 导师推送**：`services/rag.py build_learning_context` 注入待攻克弱点（status != treated 前 3 条，「待攻克弱点」段落）；`endpoints/chat.py` 新增 `GET /chat/weaknesses` 返回待处理诊断列表。
  6. **闭环6 Boss**：`schemas/boss.py`（BossStartIn/Out、BossFinishIn/Out、BossQuestionOut）、`services/boss_service.py`（`start_boss_challenge` 从技能下属知识点题库抽题并落 started 会话行返回 challenge_id；`finish_boss_challenge` 规则评分 → 分数/奖励/等级/技能状态全规则计算，通过≥60 分 → XP=30+重要性/3、失败参与奖 5，写 LearningArchive.total_xp/current_level + UserSkillStatus + BossChallenge + LearningRecord(boss) 打点，提交前清理该用户 started 会话行）、`endpoints/boss.py`（POST /boss/start、POST /boss/finish）；路由挂 `/api/v1` 与 `/api` 双前缀。
  7. **端到端测试** `tests/test_business_loop_e2e.py`：36 条断言全过（闭环1 注册即档案 Lv1/XP0；闭环2 测评→画像自动生成含雷达/目标岗位回写档案；闭环3 选定岗位→自动路径 6 段位/画像切岗；闭环4 阶段测评 80 分→技能状态写入→弱点「排序与查找」落库带建议→学习记录 assessment 打点；闭环5 导师上下文含「待攻克弱点」+SSE 会话 200；闭环6 Boss start 不下发答案→全对 pass/reward_xp>0/总 XP 累计/等级同步/技能 mastered/学习记录 boss 打点→失败路径不通过）。
  8. **演示冒烟**：`scripts/run_demo_sqlite.py` 新库端口 3930 起真实服务，HTTP 全链路注册→测评→画像→选岗→路径→阶段测评→弱点→导师 SSE→Boss 全对 SMOKE-OK（弱点「排序与查找」、Boss score=100 pass、total_xp=62 档案同步、轨迹含 boss/assessment）。
- **生成/修改文件**：
  - 新增（后端）：`app/models/business_loop.py`、`app/schemas/boss.py`、`app/services/persona_auto.py`、`app/services/business_flow.py`、`app/services/boss_service.py`、`app/api/v1/endpoints/boss.py`、`alembic/versions/20260109_0009_business_loop_tables.py`、`tests/test_business_loop_e2e.py`
  - 修改（后端）：`app/models/__init__.py`、`app/db/base.py`、`app/api/v1/router.py`（+boss 路由）、`app/main.py`（+/api 别名）、`app/api/v1/endpoints/assessment.py`（submit 后自动画像+回写）、`app/api/v1/endpoints/skills.py`（+POST /jobs/select）、`app/api/v1/endpoints/exam_review.py`（submit 后 LearningRecord）、`app/services/exam_service.py`（+技能状态联动+弱点诊断）、`app/services/rag.py`（上下文注入弱点）、`app/api/v1/endpoints/chat.py`（+GET /chat/weaknesses）、`app/schemas/skill.py`（+JobSelectIn/Out）
  - 修改（测试）：`tests/test_assessment_persona_e2e.py`（「未生成画像 data=null」→「测评后画像已自动生成」，适配闭环2 新行为）
- **验证结果**：
  - 后端 E2E：业务闭环 36 条全绿；全量回归（user=24、assess=56、skill=51、learning=66、exam=46、chat=49、business=36）→ **合计 328 条断言 FAIL=0**。
  - 前端：`npm run build`（vue-tsc + vite）→ 构建成功，无类型错误。
  - 沙箱演示 HTTP 冒烟：闭环 1→6 全链路 SMOKE-OK（见上）。
- **排错/重构记录**：
  - **弱点诊断不落库**：应用 Session 为 `autoflush=False`（`db/session.py`），`_upsert_masteries` 的 `db.add` 新增掌握度在 `_upsert_weakness_diagnostics` 的 `select(KnowledgeMastery)` 前未 flush → m_map 为空跳过错分支 → `_upsert_weakness_diagnostics` 查询前置 `db.flush()` 修复。
  - **BossStartOut 缺 challenge_id**：初版 start 不落库导致响应序列化 422 → 改为 start 时落 BOSS_STARTED 会话行返回 challenge_id；finish 提交前 `delete(...status=started)` 清理悬挂会话行。
  - **回归适配**：模块2 原断言「未生成画像 data=null」与闭环2 自动画像冲突 → 更新为断言自动画像已生成（新行为正确）。
- **结束状态**：模块 8 完成。六大闭环全部后端数据自动流转（画像/路径/评分/奖励/等级/技能状态全规则计算，LLM 仅文本增强可降级）；演示脚本 `scripts/run_demo_sqlite.py` 即可起服务全链路体验；前端页面未改（闭环均可用 curl/现有页面 API 验证）。待用户反馈是否需要前端配套（选岗落库按钮、导师弱点卡片、Boss 挑战入口）。
- **前端配套（追加，同日）**：用户确认做完整前端配套：
  1. **类型与 API**：`src/types/business.ts`（JobSelectPayload/Result、WeaknessItem、BossQuestion/StartResult/AnswerItem/FinishResult）+ `src/api/business.ts`（selectTargetJob、getWeaknesses、startBossChallenge、finishBossChallenge）。
  2. **闭环3 选岗落库**：`views/skill/JobSelect.vue` 点击岗位卡片/「快速进入」先调 `POST /jobs/select`（auto_generate_path=true）→ 成功提示「已选定并自动生成学习路径」再进技能图谱；失败降级仍可进入图谱。
  3. **闭环5 弱点推送**：`views/Tutor.vue` 左侧新增「待攻克弱点」区块（getWeaknesses），展示 kp_name/能力域/掌握度/规则诊断，点击卡片自动填入提问「如何攻克…结合学习进度给建议」并发送（无会话先新建）。
  4. **闭环6 Boss 挑战**：新增 `views/skill/BossChallenge.vue`（el-dialog 答题：单选/多选/判断，start 抽题不下发答案，finish 规则评分，结果卡展示得分/通过/奖励 XP/等级/距下一级/技能状态，支持再战，`defineExpose({open})`）；`views/SkillTree.vue` 技能节点详情侧边栏新增「Boss 挑战」面板触发，@finished 自动刷新图谱掌握度。
- **验证结果（前端配套）**：
  - `npm run build`（vue-tsc + vite）→ 构建成功（首轮报 SkillTree 访问未暴露 open 方法，补 defineExpose 后通过）。
  - 演示冒烟：后端 3930 SQLite 新库 + `vite preview` 3931 → 前端页 200；登录 hunter → 选岗落库 auto_path=True 6 段位 → Boss start challenge_id=1 5 题 → 全对 finish pass reward_xp=62 → 档案 total_xp=62 同步 → FE-SMOKE-OK。
- **统一 AgentService（追加，同日）**：用户要求统一大模型调用服务与 8 个 Agent 提示词配置：
  1. **提示词配置** `app/agents/prompts.py`（增强）：`AgentSpec` 新增 `description` / `default_temperature` / `default_max_tokens`（带默认值，frozen dataclass 向后兼容，现有 persona_builder/learning_path_service/report_service 引用不变）；8 个 Agent（orchestrator/career/skill/learning/tutor/assessment/coach/reflection）补充元信息并新增 `AGENT_TASKS`（每个 Agent 的任务指令表），`__all__` 导出 AGENT_TASKS。
  2. **统一服务** `app/services/agent_service.py`：`AgentInput`（agent_type/user_context/retrieved_docs/history/fallback/temperature/max_tokens/max_retries）→ `AgentResult`（agent_type/ok/data/error/note/degraded）；`build_user_prompt` 结构化拼装【任务/用户上下文/检索资料/对话历史】并对 history（≤6条·300字/条）与 docs（≤8条·500字/条）裁剪控 token；按 `AGENT_REGISTRY` 选系统提示词 + JSON Schema，调用 `LLMService.chat_json` 强制 JSON 解析；未配置模型/调用异常统一降级（有 fallback → ok=True+degraded=True 返回规则结果；无 fallback → ok=False）；`available_agents()` 暴露 Agent 清单；全局单例 `agent_service`。
  3. **验证** `tests/test_agent_service.py`：38 条断言全过（注册表 8 Agent 配置齐全、AGENT_TASKS 全覆盖、user_prompt 拼接与裁剪、未配置降级行为、未知 agent、成功解析与温度/maxtokens 透传、模型失败 fallback 降级）。
  4. **回归**：全量 E2E（user24/assess56/skill51/learning66/exam46/chat49/business36 + agent_service38 = **366 断言 FAIL=0**），`app.main` 导入正常（71 路由）。
- **多智能体接入（业务层 + API 端点，追加，同日）**：用户确认继续「业务层接入」，将既有 4 处直接调用大模型的业务切换到统一 AgentService，并为其余 Agent 新增接入端点：
   1. **Career Agent 接入** `app/services/persona_builder.py`：`enhance_persona_with_career_agent` 改用 `agent_service.run(AgentInput(agent_type="career", user_context=..., fallback=fallback, max_tokens=1024))`；`result.degraded/not ok` 时回退规则画像，成功才写 `ai_enriched=True`；删除 `llm_service`/`CAREER` 直接导入（LLM 未配置自动降级，行为不变）。
   2. **Learning Agent 接入** `app/services/learning_path_service.py`：`enhance_with_learning_agent` 改用 `agent_service.run(AgentInput(agent_type="learning", user_context={job_name, plan_summary, planned_stages}, max_tokens=1024))`；失败/未配置返回规则路径名与段位目标；删除 `llm_service` 与残留的 `LEARNING` 提示词导入。
   3. **Assessment Agent 接入** `app/services/report_service.py`：`_assess_with_agent` 改用 `asyncio.run(agent_service.run(AgentInput(agent_type="assessment", user_context=payload, max_tokens=1024)))`（沿用既有 asyncio.run 桥接，E2E 环境无事件循环可行）；`degraded/not ok` 返回 None 走规则文案、`ai_enriched=False`；删除 `ASSESSMENT`/`llm_service` 导入。
   4. **Tutor Agent 接入（流式）** `app/api/v1/endpoints/chat.py`：`_answer_flow` 的 LLM 分支改用 `agent_service.stream(AgentInput(agent_type="tutor", user_context={question, learning_context}, retrieved_docs=hits[:8], history=history, temperature=0.3, max_tokens=1024))` 逐块产出 SSE delta（新 `stream()` 复用统一提示词/上下文拼装，未配置/未知 Agent 返回空流）；未产出内容时降级 `_fallback_summary` + `_chunk_answer` 模拟流式。`references`/`sufficient` 仍由检索 hits 结构化计算，`test_chat_rag_e2e` 断言不受影响；移除 `llm_service`/`LLMNotConfiguredError`/`build_tutor_prompt`（保留于 `rag.py` 供兼容）与未使用的 `ChatSessionOut` 导入。
   5. **统一接入端点** `app/api/v1/endpoints/agents.py` + `app/schemas/agent.py`：`GET /agents`（8 个 Agent 清单）、`POST /agents/run`（AgentRunIn → AgentRunOut，未配置/失败含 degraded 标记）、`POST /agents/stream`（SSE：delta/done，供 Tutor/Coach 等逐字渲染）；挂载 `/api/v1` 与 `/api` 双前缀（router.py + main.py）。
   6. **新增测试** `tests/test_agents_api_e2e.py`：21 条断言全过（双前缀清单 8 项、未鉴权 401、未知 agent 错误结构、coach+fallback 降级返回规则结果、SSE stream 含 done、stream 未鉴权 401）。
   7. **验证**：全量回归（user24/assess56/skill51/learning66/exam46/chat49/business36/agent_service38/agents_api21 = **387 断言 FAIL=0**）；`app.main` 导入正常（77 路由含 6 个 agents 端点）；前端 `npm run build` 通过；沙箱 `scripts/run_demo_sqlite.py` 冒烟通过（health → 注册 → /api/agents 8 项 → /agents/run degraded=True 返回规则结果 → /agents/stream done 事件）。

---

## 模块 9：游戏化成长体系（XP / 段位 / 成就 / 连击 / 番茄钟 / 每日督导）

- **日期**：2026-09-26
- **用户 Prompt 摘要**：实现游戏化系统（模块9）：XP 经验与六段位（青铜→王者）、6 个成就、连击（连续学习天数）、番茄钟（25/40 分钟专注）、每日督导（Coach Agent 生成今日任务）；前端配套成长首页与成就中心页面。核心原则：**能规则算的不用大模型** —— XP/等级/段位/连击/成就/番茄钟全部规则计算，LLM 仅做文本增强（Coach Agent），未配置 `HUAWEI_LLM_API_KEY` 自动降级为规则任务。
- **码道执行动作**：
  1. **数据层** `app/models/gamification.py`：4 张表 `achievements`（含 hidden/sort_order/xp_reward/condition_json）、`user_achievements`、`xp_logs`（含 metadata_json）、`pomodoro_sessions`（含笔记/轮次/奖励）；注册 `models/__init__.py` + `db/base.py`；Alembic 迁移 `20260110_0010_gamification_tables.py`（继承 0009）。
  2. **成就 Seed** `app/db/seed_gamification.py`：幂等 upsert 6 个成就（first_steps 初出茅庐/streak_3 连续学习/question_slayer 问题终结者/boss_slayer Boss Slayer/skill_lighter 技能树点亮者/hidden_achievement 隐藏成就，条件存 condition_json，XP 5/10/15/20/25/50）。
  3. **规则引擎服务** `app/services/gamification.py`：
     - **段位**：`TIER_RULES`（Lv0/3/5/7/10/14 → 青铜/白银/黄金/铂金/钻石/王者）+ `tier_of/tier_index_of/tier_percentage`；复用 users.py 的 `level_from_xp/xp_to_next_level`（50*level*(level-1)）。
     - **XP**：`ACTION_XP_RULES` 定额表（学习20/任务15/项目50/答疑5/番茄钟10/弱点20）+ `add_xp`（写流水 + 累加 `learning_archives.total_xp`）/`record_action_xp`/`today_xp`/`recent_xp_logs`。
     - **连击**：`compute_streak`（以今天或昨天为终点往前数连续学习日，源 = XpLog + LearningRecord 日期集合）+ `check_in` 每日打卡（当天首次 +10 XP 去重）。
     - **成就**：`try_unlock_achievements`（condition_json 规则校验：total_xp/streak/qa_count/boss_pass/mastered_skills，幂等解锁并发成就 XP）+ `user_achievements_view`（隐藏成就未解锁时描述打码"……"）。
     - **番茄钟**：`complete_pomodoro`（focus 25min+8 / deep 40min+12）/`pomodoro_stats`。
     - **每日督导**：`build_daily_tasks` 规则生成（弱点攻克/路径当前节点/番茄钟/答疑最多 4 项）+ `build_daily_supervision` 调 `agent_service.run(coach)` 增强（未配置降级回规则 daily_plan/encouragement）+ `complete_daily_task`（当天 daily_task 类型去重只发一次奖励）。
     - **聚合**：`build_overview`（等级/段位/总XP/距下一级/今日XP/连击/是否已打卡/番茄钟统计/今日任务/成就中心/最近流水 8 条）。
  4. **API 层** `app/schemas/gamification.py` + `app/api/v1/endpoints/gamification.py`：7 个接口（GET overview / GET achievements / GET xp-logs 分页 / POST checkin / POST pomodoro / GET today-tasks / POST tasks/complete），挂 `/api/v1` 与 `/api` 双前缀。
  5. **既有流程埋点**：`chat.py` 答疑成功 `record_action_xp(+5)`；`boss_service.py` 结算写 XpLog 流水行（`total_xp` 口径不变，只补流水）。
  6. **端到端测试** `tests/test_gamification_e2e.py`：54 条断言全过（段位映射/段位下标递增/连击 3 含今天/学习与项目 XP 流水/每日打卡去重/番茄钟 focus·deep 奖励/任务完成与去重/成就中心隐藏打码/初出茅庐自动解锁/连续学习成就解锁条件/隐藏成就 1500 XP 解锁切换黄金段位）。
  7. **前端配套**：
     - `src/types/gamification.ts`（Overview/DailyTask/Achievement/XP 流水/番茄钟/督导）+ `src/api/gamification.ts`（7 个 API）。
     - 重写 `src/views/Home.vue` 为成长首页：段位标签 + 升级 XP 进度条（按 `50*level*(level-1)` 级距计算）+ 今日 XP / 连击 / 每日打卡按钮 / 今日任务完成 + 番茄钟弹窗（focus+8/deep+12）/ 成就简览前 4 + 跳转 / 最近成长记录表。
     - 新增 `src/views/gamification/AchievementCenter.vue`：统计头（已解锁/总数 + 进度条）+ 成就卡片墙（已解锁绿色渐变置前、图标 emoji 映射、隐藏成就未解锁描述由后端打码）。
     - `router/index.ts` 新增 `/achievements`；`BasicLayout.vue` 菜单新增「成就中心」（Medal 图标）。
     - 演示脚本 `scripts/run_demo_sqlite.py` 增加 `seed_achievements(s)` 调用（成就 seed 随演示库初始化）。
- **生成/修改文件**：
  - 新增（后端）：`app/models/gamification.py`、`alembic/versions/20260110_0010_gamification_tables.py`、`app/db/seed_gamification.py`、`app/services/gamification.py`、`app/schemas/gamification.py`、`app/api/v1/endpoints/gamification.py`、`tests/test_gamification_e2e.py`
  - 修改（后端）：`app/models/__init__.py`、`app/db/base.py`、`app/api/v1/router.py`（+gamification 路由）、`app/main.py`（+/api 别名）、`app/api/v1/endpoints/chat.py`（答疑+5 XP 埋点）、`app/services/boss_service.py`（Boss 奖励写 XpLog 流水）、`tests/test_business_loop_e2e.py`（总 XP 断言改为 fin["reward_xp"]+5 兼容答疑 XP）、`scripts/run_demo_sqlite.py`（+seed_achievements）
  - 新增（前端）：`src/types/gamification.ts`、`src/api/gamification.ts`、`src/views/gamification/AchievementCenter.vue`
  - 修改（前端）：`src/views/Home.vue`（占位页重写为成长首页）、`src/router/index.ts`（+成就中心路由）、`src/layouts/BasicLayout.vue`（+成就中心菜单）
- **验证结果**：
  - 后端 E2E：游戏化 54 条全绿；全量回归（agents_api21/assess56/business36/chat49/exam46/**gamification54**/learning66/skill51/user24 = **403 断言 FAIL=0**）。
  - 前端：`npm run typecheck`（vue-tsc）通过；`npm run build` 成功。
  - 沙箱演示 HTTP 冒烟（端口 3902 + 新库 /tmp/sq_demo_m9.db）：登录 → overview（Lv1 青铜 XP0）→ 成就中心 6 项全未解锁 → today-tasks（pomodoro+10 / ask_tutor+5，degraded=True 返回规则督导文案）→ checkin +10 XP → pomodoro deep +12 XP → overview 刷新 today_xp=27（checkin10+pomodoro12+初出茅庐成就5）成就 1/6 自动解锁 → 前端 vite dev（5175，代理 →3902）页面 200 / 代理登录 HTTP 200 / 未鉴权 401 → **SMOKE-OK**。
- **排错/重构记录**：
  - **`TIER_KEYS` 顺序写反**：初版写成降序导致 `tier_index_of` 下标错位，改为 `list(reversed(...))` 保证青铜→王者递增。
  - **Boss 成就永不解锁（seed/服务条件 key 不一致）**：seed 里 boss_slayer 用 `boss_pass_count`，而引擎校验只识别 `boss_pass` → 该成就永远无法解锁；修复 seed 条件为 `boss_pass`（回归全绿）。
  - **`test_agent_service.py` 顶层 SystemExit 导致 pytest 收集崩溃**：e2e 均为此模式，改用逐个 `python tests/test_*_e2e.py` 运行回归。
  - **沙箱 python 环境 PYTHONHOME 污染**：默认 `python` 报 `No module named 'encodings'`；回归/演示需 `env -u PYTHONHOME .venv/bin/python`。
  - **登录入参为 `account` 而非 `username`**：冒烟登录改用 `{"account":"hunter",...}`。
  - **AchievementCenter 初版模板动态组件 `:is="a.iconName"` 为类型 hack**：改用后端 icon 语义 key → emoji 映射函数（trophy/calendar/chat/sword/star/medal），Home 同步复用。
  - **Home 升级进度初算公式错误**：改为按 `50*level*(level-1)` 级距计算当前等级起点→下一级起点进度。
  - **演示脚本缺 gamification seed**：补 `seed_achievements(s)`，否则演示库成就中心为空。
- **结束状态**：模块 9 完成。游戏化全链路（规则计算）后端 403 断言 FAIL=0、前端构建与冒烟通过；服务已在沙箱 3902（后端）+ 5175（前端 vite dev）运行中，等待用户反馈是否需要 DevBridge 分享链接。
