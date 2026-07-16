# 鲁韵思政大模型

面向山东省大中小学思政课教师、教研员和管理者的教学智能支持平台。
今天它是一个"可信问答 + 教学工作台雏形"；按计划它将分阶段成长为覆盖教学设计生产、证据化诊断、四学段一体化的完整平台。

> **一条总规则：** 产品范围、阶段、验收标准只看[主开发计划](src/docs/2026-luyun-curriculum-pedagogy-development-plan.md)（v1.0）。
> 本 README 只描述当前实现和使用入口；凡是标注"目标 / 计划"的能力都尚未实现，任何文档、演示和注释都不得把它们写成已完成。

## 当前状态（2026-07-16）

| 范围 | 状态 | 说明 |
| --- | --- | --- |
| 问答 MVP | 可用 | 登录、主题、会话、历史、SSE 流式问答 |
| 阶段 1A | 进行中 | 已部署 `luyun-int` 并经 Virtus 验证；尚未满足 1A 全部验收条件 |
| 阶段 1B / G1 | 未开始验收 | 纵向样板、导出、专家评测与稳定环境晋级未完成 |
| Base-Spark 接入 | 链路已通 | Tailnet HTTPS 可访问；ACL 授权由 Tailnet 管理侧负责 |

### 已实现能力

**问答链路**

- 本地账密登录（目标为思政课平台统一登录）、主题浏览、会话与历史、SSE 流式问答
- 消息、会话、用户操作全链路留痕；基础限流与结构化日志

**教学工作台（阶段 1A 增量）**

- 教学项目与版本：创建项目、保存不可变版本快照
- 资料库：上传（DOCX / 文本 PDF / Markdown / TXT）、后台解析分块、审核门禁（未审核资料不进入检索）
- 依据检索：`skill.retrieve_basis`，PostgreSQL 库内相似度排序，检索不到可靠依据时明确提示"资料不足"
- Skills 运行时：Skill 注册表 + 统一执行入口（权限、输入输出校验、运行审计、停用开关）；当前仅注册 `retrieve_basis`
- Memory：账户偏好、班情档案，注入必须由用户显式指定并留审计，支持一键清除和导出
- 异步任务：排队、进度、取消、重试，应用重启后自动恢复

**工程质量**

- 模型调用走最小 ModelClient（业务只认逻辑模型名，支持 Ollama / OpenAI 兼容接口）
- 种子案例一致性校验（`make validate-cases`）
- "无评分/排名"防护测试：API 和数据模型中出现评分类标识符会使测试失败

### 尚未完成（主要项）

向量混合检索（待模型选型）、其余阶段 1 Skills（待阶段 0 目录冻结）、Memory 注入确认界面、教学设计生成/诊断/导出的纵向样板、固定版本 vLLM、`luyun-demo` 稳定演示环境。完整清单见主开发计划 §1.2。

## 系统组成

| 层 | 技术 | 说明 |
| --- | --- | --- |
| 前端 | Vue 3 + Vant + Vite | 当前为轻交互问答 + 工作台基础页；目标形态是桌面优先工作台 |
| 后端 | FastAPI + SQLAlchemy（异步） | 薄路由 + services 业务层 |
| 存储 | PostgreSQL + MinIO | 业务数据 + 原始文件 |
| 模型 | Ollama（过渡）/ vLLM（正式基线） | 经 ModelClient 调用，业务不感知具体引擎 |
| 代理 | Nginx | HTTPS 与 SSE 反代 |

## 主要使用流程

- **问答：** 登录 → 选主题 → 创建会话 → 流式问答 → 查看历史
- **工作台：** 登录 → 创建项目/版本 → 上传资料 → 审核 → 检索依据（可注入班情 Memory）→ 查看任务留痕

## 关键接口

- 认证：`POST /api/auth/login`、`GET /api/auth/me`
- 主题与会话：`GET /api/topics`、`POST /api/sessions`、`GET /api/sessions`
- 对话：`POST /api/chat`（SSE）
- 项目与任务：`/api/workbench/projects`、`/api/workbench/tasks`
- 资料：`/api/workbench/projects/{id}/documents`、`/api/workbench/documents/{id}/review`
- Skills：`GET /api/workbench/skills`、`POST /api/workbench/skills/retrieve-basis`
- Memory：`/api/workbench/memory/preference`、`/api/workbench/memory/class-profiles`、`/api/workbench/memory/export`、`POST /api/workbench/memory/clear`

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
| [架构说明](src/docs/ARCHITECTURE.md) | 当前结构与目标架构边界 | 了解代码组织时 |
| [基础设施说明](src/infra/README.md) | Compose、部署、base-spark 运维手册 | 部署与运维时 |
| [AGENTS.md](AGENTS.md) | coding agent 的工作规则 | agent 交付前 |
| [.github/INDEX.md](.github/INDEX.md) | 按任务类型索引的工作流文档 | 需要具体工作流时 |
| [对外方案](src/docs/2026-luyun-external-solution-v1.0.md) / [Word 版](鲁韵思政大模型建设方案_v1.0_对外版.docx) | 客户对外表达版 | 对外沟通时 |
| `2026-product-extension-*.md` | 能力图与方向稿（**非排期**） | 仅作背景参考 |

阶段状态不另设排期文件；变化直接以"实施记录"写入主开发计划。

## 演示环境（base-spark）

- 地址：<https://base-spark.tail84088a.ts.net/>（仅同一 Tailnet 内可访问，不对公网开放）
- 测试账号：`demo_teacher` / `Luyun-Stage1A-0715!`
- 启停、状态检查与故障处理见[基础设施说明](src/infra/README.md#tailscale-serve-启用停用与验证)

> 该账号仅用于阶段 1A 内部验证（含审核演示权限），正式部署前必须删除或轮换。

## 项目边界

这些是写进主开发计划的硬约束，代码和文档都必须遵守：

1. **不做评分排名。** 教学诊断是形成性建议，不输出教师/学生总分或排名；仓库内有防护测试兜底。
2. **不做注册和实名。** 用户注册、短信、身份核验由思政课平台用户管理系统实现（计划 §2.6）；本仓只消费平台签发的身份信息，当前本地登录仅为过渡。
3. **不绑定推理引擎。** 正式环境和验收默认 vLLM，Ollama 只用于开发过渡和明示降级；业务代码只使用逻辑模型名。
4. **不虚报能力。** 演示和文档不得用原型冒充已实现功能；`luyun-int` 是集成环境，不是稳定演示环境或客户生产方案。
5. **Memory 不做画像。** 只保存用户显式录入、可删除、可审计的教学工作记忆，禁止任何形式的思想侧写或绩效画像。

## 可审计数据

- 问答：messages、sessions、audit_logs
- 工作台：teaching_projects、project_versions、knowledge_documents、knowledge_chunks
- 运行留痕：task_runs、skill_runs（含 input_hash、memory_refs、error_code）、model_call_audits
- Skills 与 Memory：skill_definitions、user_preferences、class_context_profiles、memory_injection_audits
