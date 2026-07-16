# API 模块说明（鲁韵思政）

本目录包含鲁韵思政后端 API，基于 FastAPI + SQLAlchemy（异步）构建，当前提供认证、主题/会话、SSE 流式问答，以及阶段 1A 项目、版本、知识资料、任务和依据检索基础能力。

> 基础设施与部署请参考：`src/infra/README.md`。

## 目录结构概览

```
api/
├── config.py
├── dependencies.py
├── exceptions.py
├── logging_config.py
├── main.py
├── middleware.py
├── rate_limit.py
├── models/
├── routes/
├── schemas/
├── services/
├── utils/
└── migrations/
```

## 核心入口与基础配置

- `main.py`
  - 创建应用、注册中间件/异常处理器/路由
  - 注册健康检查接口
- `config.py`
  - 集中管理数据库、LLM、JWT、CORS 等配置
- `dependencies.py`
  - 注入数据库会话与当前用户
- `middleware.py`
  - Trace ID、请求日志、认证上下文
- `exceptions.py`
  - 统一异常响应结构
- `rate_limit.py`
  - 请求限流

## 路由层（routes）

- `routes/auth.py`
  - 登录（`POST /api/auth/login`）、当前用户信息（`GET /api/auth/me`）
- `routes/cases.py`
  - 主题列表与详情（URL 前缀 `/api/topics`，文件名沿用 `cases` 以与 models/schemas 保持一致）
- `routes/sessions.py`
  - 会话创建、会话列表、会话详情
- `routes/chat.py`
  - SSE 流式问答（核心链路，`POST /api/chat`）
- `routes/workbench.py`
  - 教学项目/版本、资料上传与审核、任务列表、Skill 列表与 `retrieve_basis`
  - Memory 端点：偏好读写、班情档案增删查、导出与一键清除
  - 资料审核仅限 `reviewer`/`admin` 角色，阶段 1A 审核范围为全库（可审任意用户资料）；组织级隔离按计划 WP2.5 在阶段 2 引入

## 服务层（services）

- `chat_orchestration.py`：提示词、会话上下文和 token 估算。
- `model_gateway.py`：最小 ModelClient、Ollama/OpenAI 兼容调用、统一错误和调用审计。
- `project_service.py`：教学项目和版本操作。
- `knowledge_service.py`：资料解析、任务恢复、审核过滤和 pg_trgm 库内词法检索（`search_chunks` + `retrieve_basis_handler`）。
- `skill_runtime.py`：Skill 注册表、权限与 Schema 校验、Memory 注入审计和 SkillRun 生命周期；`run_skill` 是唯一 Skill 执行入口。
- `memory_service.py`：偏好、班情档案、一键清除与导出。
- **边界：** 当前 Skills/Memory 为最小基线，仅 `skill.retrieve_basis`（v1.1.0）达到基线成熟度；其余阶段 1 Skills 的 Schema 待阶段 0《产品 Skills 目录 v1》冻结后注册。配额/降级策略字段已登记但未启用执行；向量 + Reranker 混合检索待 D0 选型。Memory 注入仅接受用户显式传入的 `memory_refs`，不做任何自动注入。
- **禁止：** 实现教师/学生总分评分排名模块（与产品“诊断非评分”原则冲突）；`tests/test_no_scoring_paths.py` 对 API 面与领域模型做防护断言，`skill_runtime.register_skill` 拒绝评分类 skill_id。

## 工具层（utils）

- `utils/jwt.py`
  - JWT token 创建与解析

## 数据模型层（models）

- `users`：用户信息与角色
- `sessions`：会话状态与时间信息
- `messages`：对话消息与统计信息
- `cases`：主题模板/场景配置
- `audit_logs`：审计记录
- `teaching_projects` / `project_versions`：项目与版本
- `knowledge_documents` / `knowledge_chunks`：资料与片段
- `task_runs` / `skill_runs` / `model_call_audits`：任务、Skill 与模型调用留痕
- `skill_definitions`：注册 Skill 的版本、Schema、权限与停用开关
- `user_preferences` / `class_context_profiles` / `memory_injection_audits`：Memory 对象与注入审计

## 调用链路

1. 前端请求路由层（`routes/*`）。
2. 路由层校验请求并注入鉴权与数据库依赖。
3. 调用服务层组织问答上下文并请求 LLM。
4. 通过 SSE 返回内容并写入消息审计数据。

## 模型服务边界

- 当前问答通过最小 ModelClient 使用 `LLM_LOGICAL_MODEL`、`LLM_PROVIDER` 和 Provider 模型 ID，支持 Ollama 原生流式接口或 OpenAI 兼容接口，并记录模型调用审计。
- 完整目标仍是 ModelGateway 的模型注册、任务路由、能力发现和 Provider Adapter 一致性回归；正式环境、稳定演示和最终验收默认采用 vLLM，Ollama 仅用于前期开发、兼容性验证和明确标注的降级。
- vLLM 与 Ollama 的模型 ID、Tokenizer、Chat Template、量化和输出行为必须分别登记并通过同一套回归，不能仅通过修改 URL 就视为等价。
- 模型接入、Skills、Memory 升级以 `src/docs/2026-luyun-curriculum-pedagogy-development-plan.md`（v1.0）为准；本说明不表示目标能力已经实现。
- 用户注册与认证分级在**思政课平台用户管理**实现；本 API 目标态校验平台身份 claims，**不实现**手机注册/KYC（见计划 §2.6）。当前仍为本地 JWT 登录 MVP。

## 运行与验证

```bash
pytest
ruff check .
```
