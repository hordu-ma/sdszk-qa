# 鲁韵思政大模型

面向山东省大中小学思政课一体化建设指导中心的教学智能支持平台。当前已交付“问答 MVP + 阶段 1A 首个可部署增量”；目标产品继续按阶段 0–4 升级为教学设计生产、证据化诊断、产品 Skills、核心用户 Memory、四学段一体化、受控多智能体和多模态教学证据平台。

> **文档权威：** 范围、阶段、验收、Skills/Memory 与工程顺序以 [教学与课程论驱动的分阶段开发计划](src/docs/2026-luyun-curriculum-pedagogy-development-plan.md)（v1.0）为唯一主依据。
> 目标能力不得被描述为当前已经实现。`2026-product-extension-*.md` 仅为能力图/方向稿，**不是排期依据**。

## 当前实现基线

- 登录认证（本仓本地账密；目标为思政课平台统一登录）
- 主题/场景列表浏览
- 会话创建与历史查询
- SSE 流式问答
- 问答消息全链路可审计
- Teaching Project / Version、知识资料、任务运行、SkillRun 和模型调用审计基础对象
- 问答编排服务层与最小 ModelClient（逻辑模型名、Provider 标识、超时和调用审计）
- 资料上传、后台解析、审核门禁和 `retrieve_basis` 库内词法检索（pg_trgm 相似度 + 资料不足阈值）
- 产品 Skills 运行时最小集（SkillDefinition 注册表、权限与 Schema 校验、SkillRun 审计、停用开关）
- 核心用户 Memory 最小集（偏好、班情档案、显式 `memory_refs` 注入审计、一键清除与导出）
- 桌面优先工作台基础页（项目、版本、资料、任务与依据检索）
- `base-spark` 的 `luyun-int` 集成栈及 Virtus/Tailscale HTTPS 验证链路
- 种子案例一致性校验（`make validate-cases`）与"无评分/排名 API"防护测试基线

> 当前代码**不包含评分/排名模块**；目标产品的教学诊断同样不以教师总分或排名为默认输出。
> 当前只完成阶段 1A 增量，并不等于阶段 1 或 G1 完成。Skills 运行时与 Memory 已有最小基线（仅 `retrieve_basis` 达到基线成熟度；其余阶段 1 Skills 的 Schema 待阶段 0 目录冻结后注册），向量 + Reranker 混合检索、注入确认 UX、配额/降级策略配置化、纵向样板、Word 导出、固定版本 vLLM 和 `luyun-demo` 晋级仍未完成。

### 当前阶段状态（2026-07-15）

| 范围 | 状态 | 说明 |
| --- | --- | --- |
| 问答 MVP | 已保留并验证 | 登录、主题、会话、历史、Ollama SSE 问答可用 |
| 阶段 1A | 进行中 | 首个可部署增量已进入 `luyun-int` 并由 Virtus 验证；尚未满足 1A 全部门槛 |
| 阶段 1B / G1 | 未开始验收 | Skills/Memory、完整样板、导出、专家评测与稳定环境晋级未完成 |
| Base-Spark D2 接入子项 | 技术链路已完成 | Tailnet HTTPS 已启用；ACL/Grant 范围仍由 Tailnet 管理侧负责 |

本项目不启用 `tasks.md` 作为第二套排期。阶段范围与状态统一维护在主开发计划，具体启动/停用和验证步骤维护在 `src/infra/README.md`。

### 用户注册 / 认证（不在本仓开发）

目标用户体系（见开发计划 §2.6）：

| 级别 | 条件 | 说明 |
| --- | --- | --- |
| **注册用户** | 手机号+验证码，并强制填写姓名+工作单位（步骤 1–4） | 身份信息自填登记，**不是**权威实名核验 |
| **认证用户** | 完成步骤 5（SSO/三要素/邀请或通讯录等） | 机审升级，无注册人工审批岗 |

- **实现位置：思政课平台用户管理**（本大模型所在业务平台），**不在本仓库实现注册、短信、KYC。**
- 本仓目标态只校验平台签发的会话/claims（含 `account_level=registered|verified`）。
- 默认不采集未核验身份证号；不得将自填证号宣称为实名认证。

## 目标能力摘要（按阶段继续实现）

按开发计划阶段交付，摘要如下：

| 阶段 | 目标 |
| --- | --- |
| 0 | 领域模型、量规、Skills/Memory、合规、评测四库、红队与硬件基线 |
| 1 | 1A 可信平台骨架 + 1B 纵向样板、RAG、Skills/Memory、轻量诊断与导出 |
| 2 | 完整生成—诊断—采纳—导出闭环与试点 |
| 3 | 四学段、一体化、运营与权限；小程序轻量端硬交付 |
| 4 | 门禁化多智能体（复用 Skills）、多模态、微调评估 A/B |

## 系统组件

- 前端：Vue 3 + Vant（当前为轻交互问答；目标为桌面优先教学工作台）
- 后端：FastAPI + SQLAlchemy（异步）
- 模型：当前最小 ModelClient 支持 Ollama 原生流式接口与 OpenAI 兼容接口；正式生产基线仍为 vLLM
- 存储：PostgreSQL（业务数据）、MinIO（对象存储）
- 代理：Nginx（HTTPS 与 SSE 反代）

## 核心流程（当前）

- 问答兼容路径：登录 -> 选择主题 -> 创建会话 -> 流式问答 -> 查看历史会话
- 阶段 1A 路径：登录 -> 工作台 -> 创建项目/版本 -> 上传资料 -> 审核 -> 检索依据 -> 查看任务留痕

## 目标核心流程（计划）

平台注册/认证（用户管理）-> 统一登录进入鲁韵 -> 任务入口（产品 Skills）-> 可选加载 Memory -> 检索依据 / 生成或诊断 -> 局部修改与版本 -> 导出成果

## 关键接口（当前）

- 认证：`POST /api/auth/login`、`GET /api/auth/me`
- 主题：`GET /api/topics`、`GET /api/topics/{id}`
- 会话：`POST /api/sessions`、`GET /api/sessions`、`GET /api/sessions/{session_id}`
- 对话：`POST /api/chat`（SSE）
- 工作台：`/api/workbench/projects`、`/api/workbench/tasks`
- 知识资料：`/api/workbench/projects/{project_id}/documents`、`/api/workbench/documents/{document_id}/review`
- Skills：`GET /api/workbench/skills`、`POST /api/workbench/skills/retrieve-basis`（支持显式 `memory_refs` 注入）
- Memory：`/api/workbench/memory/preference`、`/api/workbench/memory/class-profiles`、`/api/workbench/memory/export`、`POST /api/workbench/memory/clear`

## 开发与部署

- 开发规范：见 [AGENTS.md](AGENTS.md)
- 主开发计划：见 [src/docs/2026-luyun-curriculum-pedagogy-development-plan.md](src/docs/2026-luyun-curriculum-pedagogy-development-plan.md)
- 对外方案源稿：见 [src/docs/2026-luyun-external-solution-v1.0.md](src/docs/2026-luyun-external-solution-v1.0.md)
- 对外 Word 发布件：见 [鲁韵思政大模型建设方案_v1.0_对外版.docx](鲁韵思政大模型建设方案_v1.0_对外版.docx)
- Codex 快速上手：见 [src/docs/codex-onboarding.md](src/docs/codex-onboarding.md)
- Codex harness：见 [src/docs/codex-harness.md](src/docs/codex-harness.md)
- Codex 辅助规则索引：见 [.github/INDEX.md](.github/INDEX.md)（`.github` 同时承载 GitHub Actions）
- 本地启动：见 [Codex Onboarding](src/docs/codex-onboarding.md) 与 [基础设施说明](src/infra/README.md)
- 架构说明：见 [ARCHITECTURE.md](src/docs/ARCHITECTURE.md)
- 基础设施：见 [src/infra/README.md](src/infra/README.md)
- 统一任务入口：优先使用根目录 `Makefile`

### Base-Spark 当前验证入口

- 地址：<https://base-spark.tail84088a.ts.net/>
- 测试用户：`demo_teacher`
- 测试密码：`Luyun-Stage1A-0715!`
- 访问条件：Virtus 已登录同一 Tailnet；该地址不对公网开放。
- 完整启用、停用、状态检查、故障处理和 SSH 降级步骤见 [src/infra/README.md](src/infra/README.md#tailscale-serve-启用停用与验证)。

> 该账号仅用于合成数据和阶段 1A 内部验证，当前具有审核演示权限；不得复用于客户生产环境，正式部署前必须删除或轮换。

### 模型服务与持续部署原则

- 正式环境、稳定演示环境和最终验收默认使用 vLLM；Ollama 只作为前期开发、兼容性验证和明确标注的备用 Provider。
- 当前已实现最小 ModelClient，以逻辑模型名和 Provider 标识隔离问答业务；完整 ModelGateway 注册、路由、能力发现和 Provider 一致性回归仍待实现。
- `base-spark` 已建设 `luyun-int` 集成环境并通过 `virtus` 验证；`luyun-demo` 稳定演示环境及同镜像晋级门禁仍待建设。
- 演示不得用原型冒充已实现 Skills/Memory/增强能力。
- 当前 `src/infra/compose/base-spark.yml` 是阶段 1A 集成环境基线，不是客户正式生产方案。

## 测试

```bash
make harness-bootstrap
make harness-quick
make test-integration
make harness-full
make test-cov
make validate-cases
```

## 可审计数据（当前）

- messages（问答内容、token、延迟）
- sessions（会话状态、起止时间）
- audit_logs（用户行为）
- teaching_projects / project_versions（项目和版本）
- knowledge_documents / knowledge_chunks（资料、审核状态和检索片段）
- task_runs / skill_runs / model_call_audits（任务、Skill 和模型调用；skill_runs 含 input_hash、memory_refs、error_code）
- skill_definitions（注册 Skill 的版本、Schema、权限与停用状态）
- user_preferences / class_context_profiles / memory_injection_audits（Memory 对象与注入审计）

## 目标可审计数据（计划）

- SkillDefinition 配额/失败降级策略的配置化执行（当前字段已登记，策略未启用）
- 教学成果版本与引用链
