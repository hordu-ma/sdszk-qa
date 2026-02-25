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
  - 登录、当前用户信息
- `routes/cases.py`
  - 主题列表与详情
- `routes/sessions.py`
  - 会话创建、会话列表、会话详情
- `routes/chat.py`
  - SSE 流式问答（核心链路）

## 服务层（services）

- 负责问答编排、提示词构建等业务逻辑。

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

## 运行与验证

```bash
pytest
ruff check .
```
