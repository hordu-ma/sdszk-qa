# 架构概览

本文档说明**当前问答 MVP** 的后端、前端和部署结构，并摘要**目标架构**中与开发计划一致的关键点。

> 范围、阶段、验收、产品 Skills、核心用户 Memory、用户注册/认证分级与工程顺序以  
> `src/docs/2026-luyun-curriculum-pedagogy-development-plan.md`（v1.0）为唯一主依据。
> 教学设计、诊断、Skills 运行时、Memory、ModelGateway、多智能体、多模态及 Base-Spark 双环境属于目标架构，**尚未在当前代码中实现**。  
> **用户注册与认证升级在思政课平台用户管理实现，不在本仓库。**  
> 基础设施与部署请参考：`src/infra/README.md`。

## 仓库结构

- 后端：`src/apps/api`（FastAPI + SQLAlchemy + Alembic）
- 前端：`src/apps/web`（Vue 3 + TypeScript + Vite + Vant）
- 脚本：`src/scripts`（导入/同步等工具脚本）
- 计划与规格：`src/docs/`

## 根目录 Python 文件

- `main.py` 是一个小型演示入口，不用于启动 API。
- API 入口为 `src/apps/api/main.py`。

## 后端结构（当前）

### 核心运行模块

- `src/apps/api/main.py`：创建 FastAPI 应用，注册中间件、异常处理器与路由
- `src/apps/api/config.py`：环境配置
- `src/apps/api/exceptions.py`：`BusinessError` 与全局异常处理
- `src/apps/api/middleware.py`：Trace ID、请求日志、认证上下文（供限流，不做鉴权判定）
- `src/apps/api/logging_config.py`：Loguru 结构化日志
- `src/apps/api/dependencies.py`：数据库会话与 JWT 鉴权
- `src/apps/api/rate_limit.py`：SlowAPI 限流

### 分层模块

- `src/apps/api/routes/*`：HTTP API（auth/cases/sessions/chat）
- `src/apps/api/services/*`：当前几乎仅有审计；**核心问答编排仍在 `routes/chat.py`**（阶段 1 将抽离）
- `src/apps/api/schemas/*`：Pydantic 模型
- `src/apps/api/models/*`：SQLAlchemy ORM

## 后端调用链（当前典型请求）

1. 客户端向 `routes/*` 发起 HTTP 请求。
2. 路由使用 `schemas/*` 校验输入，并从 `dependencies.py` 注入依赖。
3. 路由（现阶段）直接编排业务或调用少量 `services/*`。
4. 使用 `models/*` 与异步 DB 会话。
5. `exceptions.py` 统一错误；日志含 trace ID。

## 前端结构（当前）

- 入口：`src/apps/web/src/main.ts`
- 路由：`src/apps/web/src/router/*`
- 状态：`src/apps/web/src/stores/*`
- API：`src/apps/web/src/api/*`
- 页面：登录 / 主题列表 / 问答 / 历史会话（Vant 轻交互）

> 目标前端为**桌面优先教学工作台**（成果编辑、诊断对照、版本 diff、Memory 管理）。Vant 手机组件叙事不作为备课主路径的长期形态。

## 交互时序图（当前问答）

```mermaid
sequenceDiagram
  autonumber
  participant 用户 as 用户
  participant 前端 as 前端(Vue)
  participant 路由 as 后端路由(routes)
  participant 服务 as 业务服务(services)
  participant 模型 as ORM模型(models)
  participant 数据库 as 数据库

  用户->>前端: 发起提问
  前端->>路由: 发起API请求（会话/聊天）
  路由->>服务: 调用问答编排逻辑（目标态）
  Note over 路由,服务: 当前实现下编排多在 routes/chat.py
  服务->>模型: 读写数据
  模型->>数据库: 执行SQL
  数据库-->>模型: 返回结果
  模型-->>服务: ORM实体
  服务-->>路由: 问答结果
  路由-->>前端: 返回响应
  前端-->>用户: 流式显示回答
```

## 目标业务调用链（计划，Skills + Memory）

```mermaid
sequenceDiagram
  autonumber
  participant 教师 as 教师
  participant UI as 教学工作台
  participant API as FastAPI
  participant Skill as 产品 Skills 运行时
  participant Mem as Memory 服务
  participant RAG as RAG/规则
  participant GW as ModelGateway
  participant DB as PostgreSQL/MinIO

  教师->>UI: 选择任务入口
  UI->>API: 调用 Skill（可附 memory 选择）
  API->>Mem: 解析已确认 memory_refs
  API->>Skill: SkillRun 开始
  Skill->>RAG: 检索/校验
  Skill->>GW: 逻辑模型名调用
  Skill->>DB: 写成果版本/审计
  Skill-->>UI: 结构化结果 + 引用
```

## 模块依赖图（当前）

```mermaid
flowchart TD
  前端[前端 Vue 应用]
  路由层[后端 路由 routes]
  服务层[后端 服务 services]
  模型层[后端 ORM models]
  Schema层[后端 schemas]
  配置[配置 config]
  依赖[依赖注入 dependencies]
  中间件[中间件 middleware]
  异常[异常处理 exceptions]
  日志[日志 logging_config]
  数据库[(数据库)]

  前端 --> 路由层
  路由层 --> 服务层
  路由层 --> Schema层
  服务层 --> 模型层
  模型层 --> 数据库
  路由层 --> 依赖
  依赖 --> 配置
  路由层 --> 中间件
  路由层 --> 异常
  服务层 --> 日志
  中间件 --> 日志
  异常 --> 日志
```

## 部署架构图（当前生产基线 A/B）

```mermaid
flowchart LR
  用户[用户/浏览器]

  subgraph A服务器["A 服务器（入口层）"]
    Nginx[Nginx 反向代理]
    前端[前端静态文件]
  end

  subgraph B服务器["B 服务器（核心层·GPU）"]
    API[后端 FastAPI 服务]
    数据库[(PostgreSQL)]
    对象存储[(MinIO)]
    LLM[vLLM 推理服务]
  end

  用户 -->|HTTPS| Nginx
  Nginx --> 前端
  Nginx -->|反代 /api/| API
  API --> 数据库
  API --> 对象存储
  API --> LLM
```

## 目标模型服务架构

当前 API 直接使用 `LLM_BASE_URL` 和 `LLM_MODEL` 请求 OpenAI 兼容接口。阶段 1 将引入 ModelGateway / ModelClient，使教学业务与产品 Skills 只使用逻辑模型名。

```mermaid
flowchart LR
  业务[教学业务 / 产品 Skills] --> 网关[ModelGateway]
  网关 -->|正式/稳定演示默认| VLLM[vLLM Provider]
  网关 -.->|前期开发/明示降级| OLLAMA[Ollama Provider]
  网关 --> 版本[模型资产与调用版本登记]
  日常[日常 OpenClaw：与鲁韵链路隔离]
```

- 正式环境、`base-spark` 稳定演示环境和最终验收默认使用 vLLM。
- Ollama 仅用于前期开发、vLLM 兼容性验证期间的过渡和明确标注的备用 Provider。
- Provider 切换不得改变教学成果 Schema、Skill 契约、规则、任务状态和审计链路。

## 目标：产品 Skills 与 Memory（计划）

| 组件 | 职责 | 阶段 |
| --- | --- | --- |
| SkillDefinition / SkillRun | 版本化任务技能、Schema、配额、审计 | 1 必交最小集 |
| UserPreference / ClassContextProfile | 显式工作记忆，可删可审计 | 1 最小集 |
| MemoryInjectionAudit | 记录注入到某次 SkillRun 的记忆引用 | 1 |
| Agent DAG | 只调用 Skills 白名单，不另开写接口 | 4 门禁交付 |

禁止：教师/学生总分排名、思想侧写式长期记忆、开放插件式任意 Skill。

## 目标：身份与登录边界（计划）

```mermaid
flowchart LR
  U[教师] --> UM[思政课平台用户管理]
  UM -->|注册用户 registered| UM
  UM -->|认证用户 verified| UM
  UM -->|token + claims| API[鲁韵 API 本仓]
  API --> APP[Skills / 教学成果 / Memory]
```

| 级别 | 达成条件 | 实现系统 |
| --- | --- | --- |
| 注册用户 | 手机验证 + 姓名 + 工作单位（步骤 1–4） | 平台用户管理 |
| 认证用户 | 步骤 5：SSO / 合规核身 / 邀请或通讯录等 | 平台用户管理 |

- 本仓当前：本地 JWT 登录（MVP）。
- 本仓目标：校验平台签发身份；**不实现**短信注册与 KYC。
- 默认不采集未核验身份证号。详见开发计划 §2.6。

## 阶段 1 工程落地顺序（摘要）

详见开发计划 §5.4.1：

1. Teaching Project / Version  
2. 服务层抽离  
3. ModelClient  
4. 异步任务  
5. RAG / `retrieve_basis`  
6. Skills 运行时  
7. Memory 最小集  
8. 样板生成—诊断—导出  
9. 桌面优先工作台  
10. 双环境晋级  

## Base-Spark 目标部署与晋级

```text
合并并通过自动测试
  → 部署 luyun-int
  → virtus 经 Tailscale 端到端验证
  → 专业、安全、迁移和回滚门禁
  → 同一镜像摘要晋级 luyun-demo
```

- 该双环境尚未落地，现有 `dev.yml` 和 `prod-b.yml` 仍是当前基线。
- 演示脚本只能覆盖已实现能力；Skills/Memory/Agent 未就绪时不得伪装。

## 一句话总结

当前由路由串联配置、中间件、异常与 SSE 问答，前端以轻交互呈现；后续按开发计划将主对象升级为教学成果，以产品 Skills 为任务入口、以受控 Memory 为显式上下文，并逐步加入 RAG、ModelGateway 与双环境持续部署。
