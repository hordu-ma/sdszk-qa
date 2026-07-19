# 鲁韵思政大模型

面向山东省大中小学思政课教师、教研员和管理者的教学智能支持平台。
今天它是一个"可信问答 + 教学工作台雏形"；按计划它将分阶段成长为覆盖教学设计生产、证据化诊断、四学段一体化的完整平台。

> **一条总规则：** 产品范围、阶段、验收标准只看[主开发计划](src/docs/2026-luyun-curriculum-pedagogy-development-plan.md)（v1.0）。
> 本 README 只描述当前实现和使用入口；凡是标注"目标 / 计划"的能力都尚未实现，任何文档、演示和注释都不得把它们写成已完成。

## 当前状态（2026-07-19）

| 范围 | 状态 | 说明 |
| --- | --- | --- |
| 开发策略 | 自助开发模式生效 | 客户/专家暂不参与；外部签字项冻结为补签清单，工程按内部代理决策与 M0-int/M1-int 内部门推进（主计划 §0.5） |
| 问答 MVP | 可用 | 登录、主题、会话、历史、SSE 流式问答 |
| 阶段 1A | 工程底座可用，整体未验收 | `luyun-int` 已固定使用 vLLM 主链，语义 RAG、来源标记和版本化工程评测已实现；候选模型与完整 G0 外部签字未冻结 |
| 阶段 1B / G1 | M1-int 内部门通过，未通过 G1 | 高中议题式闭环、140 例内部金标 v0、工作台内部走查和同镜像稳定环境晋级已完成；真实专家金标与外部签字仍未完成 |
| 阶段 2 | WP2.1 首个纵向增量已进入集成环境 | 专业输入确认、显式冲突检查、假设确认、Memory 引用和不可变版本衔接已实现；不代表阶段 2 或 G2 完成 |
| Base-Spark 接入 | 双环境链路已通 | `luyun-int` 与 `luyun-demo` 独立运行并通过 Tailnet HTTPS 访问；ACL 授权由 Tailnet 管理侧负责 |

### 已实现能力

**问答链路**

- 本地账密登录（目标为思政课平台统一登录）、主题浏览、会话与历史、SSE 流式问答
- 消息、会话、用户操作全链路留痕；基础限流与结构化日志

**教学工作台（阶段 1A 增量）**

- 教学项目与版本：创建项目、保存不可变版本快照
- 资料库：上传（DOCX / 文本 PDF / Markdown / TXT）、后台解析分块、审核门禁（未审核资料不进入检索）
- 依据检索：`skill.retrieve_basis` v1.2.0，`pg_trgm` + pgvector 语义召回 + Reranker；Provider 故障或项目缺语义索引时显式回退字符向量链；引用带段落/PDF 页码定位；过期资料不进入检索；无候选或 top1 相关度低于内部标定阈值时明确提示"资料不足"（低置信候选明示为参考）
- 知识索引版本：Embedding/Reranker 仓库、revision、维度和配置哈希可追溯；新索引完整构建后才原子激活
- 版本化工程评测：数据集按 key/version 冻结，内容 SHA256 不可变；运行绑定应用、vLLM、模型 revision、检索参数和 Skill 版本发布清单
- 评测来源门禁：数据集显式区分 `synthetic`、`internal_authored`、`customer_provided`、`expert_authored`；模拟数据不能被审核成正式专家集，内部自研数据永远明示非专家来源
- 内部金标 v0：`stage1-internal-gold` 140 例无泄漏自研评测集（`seed_internal_gold.py`），已走通双评/第三人仲裁全流程并冻结；内部阈值见《[内部阈值标定报告 v0](src/docs/2026-stage1-internal-gold-threshold-report-v0.md)》
- 金标治理：支持最多 200 例批量导入、审核员正式集复核队列、两位不同审核人独立复核、分歧时由第三人仲裁、占位案例阻止冻结，以及金标状态/最近运行汇总报告；只有数据集所有者可导入、冻结和运行
- Skills 运行时：统一权限、Schema、运行审计、停用与降级契约；已注册查依据、专业输入确认、对齐卡、蓝图、分块生成、形成性诊断和导出七个 Skill
- Memory：账户偏好、班情档案、项目/模板钉选；每次注入必须由用户在界面显式勾选，支持导出；一键清除前显示对象数量和不可撤销确认
- 异步任务：排队、进度、取消、重试，应用重启后自动恢复
- 高中议题式样板：依据对齐卡 → 目标—证据—任务蓝图 → 课时分块 → 非评分诊断 → 结构化标准 Word 导出；界面按前置成果逐步解锁
- 版本工作区：每步形成不可变版本，可在专业结构化编辑器中修改教学成果、保存为新版本、查看修改前后差异，并追溯到 SkillRun、来源版本和导出模板
- 阶段 2 专业输入：显式确认主题、核心议题、课程依据、班情、课型、课时、资源和教师意图；阻断课型/时间/数字资源冲突，空白项只以“假设/待确认”继续；保存时使下游旧成果在新版本中失效，原版本保留
- 角色边界：教师负责创建、上传和使用资料；管理员/审核员负责资料审核；后台任务失败时界面显示具体错误原因

**工程质量**

- 模型调用走最小 ModelClient（业务只认逻辑模型名，支持 Ollama / OpenAI 兼容接口）
- vLLM 运行时固定为 `0.18.0` 镜像摘要，生成、Embedding、Reranker 候选模型固定 Hugging Face revision 并登记入库
- `luyun-int` 与 `luyun-demo` 使用独立端口、数据卷和 Secret，并以同一 API/Web 镜像摘要晋级；模拟环境在页面显示不可用于专业验收的提示
- 种子案例一致性校验（`make validate-cases`）
- "无评分/排名"防护测试：API 和数据模型中出现评分类标识符会使测试失败

### 尚未完成（主要项）

专家审核的完整阶段 1 Skill/规则目录、真实专家金标 120–160 个案例及专业阈值、候选模型正式选型、Virtus 人工验收和 G0/G1 外部签字。金标双评/仲裁工具已经实现，但当前三个模型仍是工程兼容性候选，64 个案例仍是模拟工程集；都不代表专业验收。完整清单见主开发计划 §1.2。

自 2026-07-17 起，上述外部依赖项按主计划 §0.5 自助开发模式冻结为补签清单，不再阻塞开发。自助优先级 1–5 已完成，`stage1-workbench-ux-20260719-r1` 已以同一镜像摘要晋级 `luyun-demo`，完成备份、Tailnet 冒烟和上一镜像回滚恢复；M1-int 内部门结论为通过，详见《[M1-int 收口记录](src/docs/2026-stage1-m1-int-closure.md)》。当前 `luyun-int` 为 Stage 2 候选 `stage2-professional-input-20260719-r1`，`luyun-demo` 保持 Stage 1 稳定镜像。M1-int 不等于 G1，内部产物一律不得表述为客户确认或专家签字。

## 系统组成

| 层 | 技术 | 说明 |
| --- | --- | --- |
| 前端 | Vue 3 + Vant + Vite | 当前为轻交互问答 + 桌面优先工作台内部版，支持结构化专业编辑、版本保护和基础无障碍操作 |
| 后端 | FastAPI + SQLAlchemy（异步） | 薄路由 + services 业务层 |
| 存储 | PostgreSQL + pgvector + MinIO | 业务数据、语义向量 + 原始文件 |
| 模型 | vLLM 0.18.0 候选主链 / Ollama 明示备用 | 经 Provider Adapter 调用，业务不感知具体引擎；`luyun-int` 当前使用 vLLM |
| 代理 | Nginx | HTTPS 与 SSE 反代 |

## 主要使用流程

- **问答：** 登录 → 选主题 → 创建会话 → 流式问答 → 查看历史
- **工作台：** 登录 → 创建项目 → 上传并审核资料 → 显式选择 Memory → 确认专业输入并处理冲突 → 依序运行纵向样板 → 诊断/版本差异 → 导出 Word

## 关键接口

- 认证：`POST /api/auth/login`、`GET /api/auth/me`
- 主题与会话：`GET /api/topics`、`POST /api/sessions`、`GET /api/sessions`
- 对话：`POST /api/chat`（SSE）
- 项目与任务：`/api/workbench/projects`、`/api/workbench/tasks`
- 资料：`/api/workbench/projects/{id}/documents`、`/api/workbench/documents/{id}/review`
- Skills：`GET /api/workbench/skills`、`POST /api/workbench/skills/{retrieve-basis|confirm-professional-input|alignment-card|design-blueprint|generate-section|diagnose-artifact|export-artifact}`
- Memory：`/api/workbench/memory/preference`、`class-profiles`、`pinned-items`、`export`、`clear`
- 版本/导出：`/api/workbench/projects/{id}/versions`、`versions/diff`、`/api/workbench/exports/{id}/download`
- 模型/索引：`/api/workbench/runtime/model-assets`、`/api/workbench/projects/{id}/knowledge-indexes`
- 工程/金标评测：`/api/workbench/evaluation/datasets`、`/api/workbench/evaluation/datasets/{id}/cases/import`、`/api/workbench/evaluation/cases/{id}/reviews`、`/api/workbench/evaluation/datasets/{id}/report`、`/api/workbench/evaluation/runs/{id}/results`

## 快速开始

```bash
make harness-bootstrap   # 安装依赖
make harness-quick       # lint + 类型检查 + 单测 + 前端构建
make dev-up              # 本地 PostgreSQL / MinIO / API
make test-integration    # 集成测试
```

完整命令分层、交付标准和高风险区域见[开发指南](src/docs/DEVELOPMENT.md)。

## 文档地图

| 文档 | 内容 | 何时读 |
| --- | --- | --- |
| [主开发计划](src/docs/2026-luyun-curriculum-pedagogy-development-plan.md) | 范围、阶段 0–4、验收、Skills/Memory 设计（唯一权威） | 涉及产品范围、排期、验收时 |
| [开发指南](src/docs/DEVELOPMENT.md) | 上手、命令、验证分层、交付标准 | 开始开发前 |
| [阶段 1 工程冻结基线](src/docs/2026-stage1-g0-engineering-baseline.md) | 当前样板、Skills、Memory、诊断与外部签字边界 | 开发或验收纵向样板时 |
| [M1-int 收口记录](src/docs/2026-stage1-m1-int-closure.md) | 阶段 1 内部门结论、双环境晋级、回滚证据和外部补签边界 | 进入阶段 2 或复核 G1 状态时 |
| [模拟信息替换台账](src/docs/2026-stage1-synthetic-replacement-ledger.md) | 当前模拟项、真实替换入口、门禁与回归要求 | 替换客户资料或准备正式 G0/G1 时 |
| [架构说明](src/docs/ARCHITECTURE.md) | 当前结构与目标架构边界 | 了解代码组织时 |
| [基础设施说明](src/infra/README.md) | Compose、部署、base-spark 运维手册 | 部署与运维时 |
| [AGENTS.md](AGENTS.md) | coding agent 的工作规则 | agent 交付前 |
| [.github/INDEX.md](.github/INDEX.md) | 按任务类型索引的工作流文档 | 需要具体工作流时 |
| [对外方案](src/docs/2026-luyun-external-solution-v1.0.md) / [Word 版](鲁韵思政大模型建设方案_v1.0_对外版.docx) | 客户对外表达版 | 对外沟通时 |
| `2026-product-extension-*.md` | 能力图与方向稿（**非排期**） | 仅作背景参考 |

阶段状态不另设排期文件；变化直接以"实施记录"写入主开发计划。

## 演示环境（base-spark）

- 集成环境：<https://base-spark.tail84088a.ts.net/>（仅同一 Tailnet 内可访问）
- 稳定模拟演示：<https://base-spark.tail84088a.ts.net:8443/>（仅同一 Tailnet 内可访问）
- 教师账号：`demo_teacher`
- 管理员账号：`demo_admin`
- 密码只保存在各环境仓库外 `0600` env 文件中，不写入 Git 或文档
- 启停、状态检查与故障处理见[基础设施说明](src/infra/README.md#tailscale-serve-启用停用与验证)

> 两个账号及全部资料均仅用于阶段 1 模拟工程验证；页面和 API 会显示模拟标记。正式部署前必须替换资料并轮换账号与 Secret。

## 项目边界

这些是写进主开发计划的硬约束，代码和文档都必须遵守：

1. **不做评分排名。** 教学诊断是形成性建议，不输出教师/学生总分或排名；仓库内有防护测试兜底。
2. **不做注册和实名。** 用户注册、短信、身份核验由思政课平台用户管理系统实现（计划 §2.6）；本仓只消费平台签发的身份信息，当前本地登录仅为过渡。
3. **不绑定推理引擎。** 正式环境和验收默认 vLLM，Ollama 只用于开发过渡和明示降级；业务代码只使用逻辑模型名。
4. **不虚报能力。** 演示和文档不得用模拟资料或工程评测冒充专家验收；`luyun-int`/`luyun-demo` 都不替代客户生产方案。
5. **Memory 不做画像。** 只保存用户显式录入、可删除、可审计的教学工作记忆，禁止任何形式的思想侧写或绩效画像。

## 可审计数据

- 问答：messages、sessions、audit_logs
- 工作台：teaching_projects、project_versions、knowledge_documents、knowledge_chunks、knowledge_index_versions
- 运行留痕：task_runs、skill_runs（含 input_hash、memory_refs、error_code）、model_call_audits
- Skills 与 Memory：skill_definitions、user_preferences、class_context_profiles、pinned_memory_items、memory_injection_audits
- 导出：artifact_exports（关联项目、版本、SkillRun、模板和校验和）
- 模型与评测：model_assets、evaluation_datasets/cases/case_reviews/runs/case_results（双评/仲裁、冻结哈希与发布清单）
