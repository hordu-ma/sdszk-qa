# 鲁韵思政大模型问答系统

面向山东省大中小学思政课一体化建设指导中心的教学支持平台，为山东省思政老师提供教学设计、教学研究等场景的问答服务。

## 功能概览

- 登录认证（无注册，支持外部用户体系）
- 主题/场景列表浏览
- 会话创建与历史查询
- SSE 流式问答
- 问答消息全链路可审计

> 当前产品定位为问答支持系统，不包含评分模块。

## 系统组件

- 前端：Vue 3 + Vant
- 后端：FastAPI + SQLAlchemy（异步）
- 模型：vLLM（OpenAI 兼容接口）
- 存储：PostgreSQL（业务数据）、MinIO（对象存储）
- 代理：Nginx（HTTPS 与 SSE 反代）

## 核心流程

登录 -> 选择主题 -> 创建会话 -> 流式问答 -> 查看历史会话

## 关键接口

- 认证：`POST /api/auth/login`、`GET /api/auth/me`
- 主题：`GET /api/topics`、`GET /api/topics/{id}`
- 会话：`POST /api/sessions`、`GET /api/sessions`、`GET /api/sessions/{session_id}`
- 对话：`POST /api/chat`（SSE）

## 开发与部署

- 开发规范：见 [AGENTS.md](AGENTS.md)
- Codex 快速上手：见 [src/docs/codex-onboarding.md](src/docs/codex-onboarding.md)
- GitHub Copilot 原生协作：见 `.github/instructions/`、`.github/agents/`、`.github/skills/`
- 本地启动：见 `src/docs/本地开发启动指南.md`（含测试账号，不入版本控制；首次使用需从运维获取或参照 `.env.example` 自行创建）
- 架构说明：见 [ARCHITECTURE.md](src/docs/ARCHITECTURE.md)
- 基础设施：见 [src/infra/README.md](src/infra/README.md)
- 技能目录主入口：见 `.github/skills/`
- 统一任务入口：优先使用根目录 `Makefile`

## 测试

```bash
make lint
make typecheck
make test
make test-cov
make web-build
```

## 可审计数据

- messages（问答内容、token、延迟）
- sessions（会话状态、起止时间）
- audit_logs（用户行为）
