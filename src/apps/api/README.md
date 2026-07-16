# API 模块说明（鲁韵思政）

本目录包含鲁韵思政后端 API，基于 FastAPI + SQLAlchemy（异步）构建，当前提供认证、主题/会话、SSE 流式问答，以及项目、知识资料、任务、显式 Memory 和高中议题式纵向样板能力。

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
  - 教学项目/版本/差异、资料上传与审核、知识索引、任务、六个样板 Skill 与 Word 导出
  - 固定模型资产查询、版本化工程评测数据集/案例/冻结/运行/结果
  - Memory 端点：偏好、班情、项目/模板钉选、导出与一键清除
  - 资料审核仅限 `reviewer`/`admin` 角色，阶段 1A 审核范围为全库（可审任意用户资料）；组织级隔离按计划 WP2.5 在阶段 2 引入

## 服务层（services）

- `chat_orchestration.py`：提示词、会话上下文和 token 估算。
- `model_gateway.py`：最小 ModelClient、Ollama/OpenAI 兼容调用、统一错误和调用审计。
- `project_service.py`：教学项目和版本操作。
- `knowledge_service.py`：资料解析、任务恢复、审核过滤、版本化语义索引、pg_trgm + pgvector 混合召回与字符向量降级链。
- `retrieval_gateway.py`：vLLM Embeddings/Rerank HTTP 契约、512 token 截断边界、维度/数量/索引完整性校验。
- `model_asset_service.py`：固定 vLLM/模型 revision 登记与可复现发布清单。
- `evaluation_service.py`：评测数据集版本、冻结哈希、运行和逐案例工程结果。
- `skill_runtime.py`：Skill 注册表、权限与 Schema 校验、Memory 注入审计和 SkillRun 生命周期；`run_skill` 是唯一 Skill 执行入口。
- `memory_service.py`：偏好、班情、钉选、一键清除与导出。
- `vertical_sample_service.py`：对齐卡、蓝图、课时分块、形成性诊断、版本差异和 DOCX 导出。
当前边界（详见架构说明）：

- `retrieve_basis` 为 baseline；其余五个 Skill 为 vertical_sample，外部专业签字前不冒充正式产品成熟度。
- 配额/降级契约已登记；语义 Provider 失败时字符向量链继续提供显式降级。当前模型只是 D0 工程候选，正式专业选型待外部评审。
- Memory 注入只接受用户显式传入的 `memory_refs`，不做任何自动注入。
- 禁止实现评分/排名模块：`tests/test_no_scoring_paths.py` 做防护断言，`register_skill` 拒绝评分类 skill_id。

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
- `user_preferences` / `class_context_profiles` / `pinned_memory_items` / `memory_injection_audits`：Memory 对象与注入审计
- `artifact_exports`：关联项目、版本、SkillRun、模板与校验和的导出件
- `model_assets` / `knowledge_index_versions`：运行时、模型 revision 与知识索引配置追溯
- `evaluation_datasets` / `evaluation_cases` / `evaluation_runs` / `evaluation_case_results`：冻结数据集和绑定发布清单的技术评测

## 调用链路

1. 前端请求路由层（`routes/*`）。
2. 路由层校验请求并注入鉴权与数据库依赖。
3. 调用服务层组织问答上下文并请求 LLM。
4. 通过 SSE 返回内容并写入消息审计数据。

## 模型服务边界

- 当前问答通过逻辑模型名和 Provider Adapter 支持 Ollama 原生流式接口或 OpenAI-compatible/vLLM 接口，并记录模型调用审计。
- 完整目标仍是 ModelGateway 的模型注册、任务路由、能力发现和 Provider Adapter 一致性回归；正式环境、稳定演示和最终验收默认采用 vLLM，Ollama 仅用于前期开发、兼容性验证和明确标注的降级。
- vLLM 与 Ollama 的模型 ID、Tokenizer、Chat Template、量化和输出行为必须分别登记并通过同一套回归，不能仅通过修改 URL 就视为等价。
- 模型接入、Skills、Memory 升级以 `src/docs/2026-luyun-curriculum-pedagogy-development-plan.md`（v1.0）为准；本说明不表示目标能力已经实现。
- 用户注册与认证分级在**思政课平台用户管理**实现；本 API 目标态校验平台身份 claims，**不实现**手机注册/KYC（见计划 §2.6）。当前仍为本地 JWT 登录 MVP。

## 运行与验证

```bash
pytest
ruff check .
```
