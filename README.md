# 鲁韵思政大模型

面向山东省大中小学思政课一体化建设指导中心的教学智能支持平台。当前仓库实现仍是问答 MVP；目标产品将按阶段 0–4 升级为教学设计生产、证据化诊断、产品 Skills、核心用户 Memory、四学段一体化、受控多智能体和多模态教学证据平台。

> **文档权威：** 范围、阶段、验收、Skills/Memory 与工程顺序以 [教学与课程论驱动的分阶段开发计划](src/docs/2026-luyun-curriculum-pedagogy-development-plan.md)（v0.4+）为唯一主依据。  
> 目标能力不得被描述为当前已经实现。`2026-product-extension-*.md` 仅为能力图/方向稿，**不是排期依据**。

## 当前实现基线

- 登录认证（本仓本地账密；目标为思政课平台统一登录）
- 主题/场景列表浏览
- 会话创建与历史查询
- SSE 流式问答
- 问答消息全链路可审计

> 当前代码只提供问答支持，**不包含评分/排名模块**；目标产品的教学诊断同样不以教师总分或排名为默认输出。  
> 产品 Skills 运行时、核心用户 Memory、教学成果对象、RAG、ModelGateway 等均属目标能力，尚未实现。

### 用户注册 / 认证（不在本仓开发）

目标用户体系（见开发计划 §2.6）：

| 级别 | 条件 | 说明 |
| --- | --- | --- |
| **注册用户** | 手机号+验证码，并强制填写姓名+工作单位（步骤 1–4） | 身份信息自填登记，**不是**权威实名核验 |
| **认证用户** | 完成步骤 5（SSO/三要素/邀请或通讯录等） | 机审升级，无注册人工审批岗 |

- **实现位置：思政课平台用户管理**（本大模型所在业务平台），**不在本仓库实现注册、短信、KYC。**
- 本仓目标态只校验平台签发的会话/claims（含 `account_level=registered|verified`）。
- 默认不采集未核验身份证号；不得将自填证号宣称为实名认证。

## 目标能力摘要（未实现）

按开发计划阶段交付，摘要如下：

| 阶段 | 目标 |
| --- | --- |
| 0 | 领域模型、量规、Skills 目录、Memory 边界、评测与硬件基线 |
| 1 | 纵向样板 + RAG + 异步任务 + Skills 运行时 + Memory 最小集 + 轻量诊断/导出 |
| 2 | 完整生成—诊断—采纳—导出闭环与试点 |
| 3 | 四学段、一体化、运营与权限；小程序按数据决策 |
| 4 | 门禁化多智能体（复用 Skills）、多模态、微调评估 A/B |

## 系统组件

- 前端：Vue 3 + Vant（当前为轻交互问答；目标为桌面优先教学工作台）
- 后端：FastAPI + SQLAlchemy（异步）
- 模型：当前 API 使用 OpenAI 兼容接口，现有生产编排以 vLLM 为基线
- 存储：PostgreSQL（业务数据）、MinIO（对象存储）
- 代理：Nginx（HTTPS 与 SSE 反代）

## 核心流程（当前）

登录 -> 选择主题 -> 创建会话 -> 流式问答 -> 查看历史会话

## 目标核心流程（计划）

平台注册/认证（用户管理）-> 统一登录进入鲁韵 -> 任务入口（产品 Skills）-> 可选加载 Memory -> 检索依据 / 生成或诊断 -> 局部修改与版本 -> 导出成果

## 关键接口（当前）

- 认证：`POST /api/auth/login`、`GET /api/auth/me`
- 主题：`GET /api/topics`、`GET /api/topics/{id}`
- 会话：`POST /api/sessions`、`GET /api/sessions`、`GET /api/sessions/{session_id}`
- 对话：`POST /api/chat`（SSE）

## 开发与部署

- 开发规范：见 [AGENTS.md](AGENTS.md)
- 主开发计划：见 [src/docs/2026-luyun-curriculum-pedagogy-development-plan.md](src/docs/2026-luyun-curriculum-pedagogy-development-plan.md)
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
- 演示不得用原型冒充已实现 Skills/Memory/增强能力。
- 上述演示环境和流水线属于待开发目标，当前 Compose 文件不能直接视为已经完成的 Base-Spark 部署方案。

## 测试

```bash
make harness-bootstrap
make harness-quick
make test-integration
make harness-full
make test-cov
```

## 可审计数据（当前）

- messages（问答内容、token、延迟）
- sessions（会话状态、起止时间）
- audit_logs（用户行为）

## 目标可审计数据（计划）

- SkillRun（技能版本、输入输出摘要、模型/规则/知识版本、memory_refs）
- Memory 注入与清除审计
- 教学成果版本与引用链
