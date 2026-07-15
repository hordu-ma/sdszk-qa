# API 模块说明（鲁韵思政）

本目录包含鲁韵思政问答系统的后端 API，基于 FastAPI + SQLAlchemy（异步）构建，提供认证、主题管理、会话管理与 SSE 流式问答能力。

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

## 服务层（services）

- 目标：问答编排、提示词构建、（阶段 1+）产品 Skills、Memory、RAG、任务编排等业务逻辑。
- **现状：** 几乎仅有 `audit.py`；核心 LLM/SSE 编排仍在 `routes/chat.py`。开发计划要求阶段 1 抽离到 `services/` 并引入 Skills/Memory，当前均未实现。
- **禁止：** 实现教师/学生总分评分排名模块（与产品“诊断非评分”原则冲突）。

## 工具层（utils）

- `utils/jwt.py`
  - JWT token 创建与解析

## 数据模型层（models）

- `users`：用户信息与角色
- `sessions`：会话状态与时间信息
- `messages`：对话消息与统计信息
- `cases`：主题模板/场景配置
- `audit_logs`：审计记录

## 调用链路

1. 前端请求路由层（`routes/*`）。
2. 路由层校验请求并注入鉴权与数据库依赖。
3. 调用服务层组织问答上下文并请求 LLM。
4. 通过 SSE 返回内容并写入消息审计数据。

## 模型服务边界

- 当前实现由 `routes/chat.py` 使用 `LLM_BASE_URL` 和 `LLM_MODEL` 直接调用 OpenAI 兼容的 `/v1/chat/completions`，尚未实现 ModelGateway / 产品 Skills 运行时。
- 目标架构由 ModelGateway 使用逻辑模型名和 Provider Adapter 统一调用；教学任务经产品 Skills 编排；正式环境、稳定演示和最终验收默认采用 vLLM，Ollama 仅用于前期开发、兼容性验证和明确标注的降级。
- vLLM 与 Ollama 的模型 ID、Tokenizer、Chat Template、量化和输出行为必须分别登记并通过同一套回归，不能仅通过修改 URL 就视为等价。
- 模型接入、Skills、Memory 升级以 `src/docs/2026-luyun-curriculum-pedagogy-development-plan.md`（v1.0）为准；本说明不表示目标能力已经实现。
- 用户注册与认证分级在**思政课平台用户管理**实现；本 API 目标态校验平台身份 claims，**不实现**手机注册/KYC（见计划 §2.6）。当前仍为本地 JWT 登录 MVP。

## 运行与验证

```bash
pytest
ruff check .
```
