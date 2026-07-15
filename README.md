# 鲁韵思政大模型

面向山东省大中小学思政课一体化建设指导中心的教学智能支持平台。当前仓库实现仍是问答 MVP；目标产品将按阶段 0–4 升级为教学设计生产、证据化诊断、四学段一体化、受控多智能体和多模态教学证据平台。

> 范围、阶段、模型服务和验收口径以 [教学与课程论驱动的分阶段开发计划](src/docs/2026-luyun-curriculum-pedagogy-development-plan.md) 为准。目标能力不得被描述为当前已经实现。

## 当前实现基线

- 登录认证（无注册，支持外部用户体系）
- 主题/场景列表浏览
- 会话创建与历史查询
- SSE 流式问答
- 问答消息全链路可审计

> 当前代码只提供问答支持，不包含评分模块；目标产品的教学诊断同样不以教师总分或排名为默认输出。

## 系统组件

- 前端：Vue 3 + Vant
- 后端：FastAPI + SQLAlchemy（异步）
- 模型：当前 API 使用 OpenAI 兼容接口，现有生产编排以 vLLM 为基线
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
- Codex harness：见 [src/docs/codex-harness.md](src/docs/codex-harness.md)
- Codex 辅助规则索引：见 [.github/INDEX.md](.github/INDEX.md)（`.github` 同时承载 GitHub Actions）
- 本地启动：见 `src/docs/本地开发启动指南.md`（含测试账号，不入版本控制；首次使用需从运维获取或参照 `.env.example` 自行创建）
- 架构说明：见 [ARCHITECTURE.md](src/docs/ARCHITECTURE.md)
- 基础设施：见 [src/infra/README.md](src/infra/README.md)
- 统一任务入口：优先使用根目录 `Makefile`

### 目标模型服务与持续部署原则

- 正式环境、稳定演示环境和最终验收默认使用 vLLM；Ollama 只作为前期开发、兼容性验证和明确标注的备用 Provider。
- 目标架构通过 ModelGateway、逻辑模型名和 Provider Adapter 隔离 vLLM/Ollama；当前代码尚未实现该网关，仍直接调用 `LLM_BASE_URL`。
- `base-spark` 计划建设 `luyun-int` 集成环境和 `luyun-demo` 稳定演示环境。每个可验收开发节点先部署集成环境并从 `virtus` 验证，通过门禁后以同一镜像晋级稳定演示环境。
- 上述演示环境和流水线属于待开发目标，当前 Compose 文件不能直接视为已经完成的 Base-Spark 部署方案。

## 测试

```bash
make harness-bootstrap
make harness-quick
make test-integration
make harness-full
make test-cov
```

## 可审计数据

- messages（问答内容、token、延迟）
- sessions（会话状态、起止时间）
- audit_logs（用户行为）
