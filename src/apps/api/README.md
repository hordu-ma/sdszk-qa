# API 模块说明

本目录包含临床问诊模拟系统的后端 API 实现，基于 FastAPI + SQLAlchemy（异步）构建，并集成了 JWT 鉴权、限流、日志追踪、评分服务和迁移脚本。

> 生产部署流程请统一参考：`生产部署指南.md`。

## 目录结构概览

```
api/
├── __init__.py
├── alembic.ini
├── config.py
├── dependencies.py
├── exceptions.py
├── logging_config.py
├── main.py
├── middleware.py
├── rate_limit.py
├── Dockerfile
├── migrations/
│   ├── env.py
│   ├── README
│   ├── script.py.mako
│   └── versions/
│       └── a33b8a66fd24_initial_schema.py
├── models/
│   ├── __init__.py
│   ├── audit_logs.py
│   ├── base.py
│   ├── cases.py
│   ├── messages.py
│   ├── scores.py
│   ├── sessions.py
│   ├── test_requests.py
│   └── users.py
├── routes/
│   ├── __init__.py
│   ├── auth.py
│   ├── cases.py
│   ├── chat.py
│   └── sessions.py
├── schemas/
│   ├── __init__.py
│   ├── auth.py
│   ├── cases.py
│   ├── chat.py
│   ├── scores.py
│   ├── sessions.py
│   └── tests.py
├── services/
│   ├── __init__.py
│   └── scoring.py
└── utils/
    ├── __init__.py
    └── jwt.py
```

---

## 核心入口与基础配置

### main.py

- FastAPI 应用入口
- 初始化日志系统
- 注册中间件、异常处理器、限流处理器
- 配置 CORS
- 注册路由：auth、cases、sessions、chat
- 提供 /health 与 / 根路径

### config.py

- 应用配置集中管理
- 基于 pydantic-settings 读取 .env
- 包含数据库、MinIO、LLM、JWT、CORS 等配置项

### dependencies.py

- 依赖注入定义
- 创建异步数据库引擎与会话工厂
- 提供 get_db 与 get_current_user
- 定义 DbSession、CurrentUser 依赖类型别名

### logging_config.py

- loguru 日志配置
- 支持控制台与生产环境文件滚动
- trace_id 上下文变量注入

### middleware.py

- TraceIdMiddleware：注入 X-Trace-ID
- RequestLoggingMiddleware：记录请求与耗时

### exceptions.py

- 统一错误响应结构
- BusinessError 业务异常
- 注册全局异常处理器

### rate_limit.py

- slowapi 限流配置
- 基于用户 ID 或 IP 识别
- 超限响应标准化

### **init**.py

- 模块说明占位

---

## 运行与部署

### Dockerfile

- 使用 python:3.11-slim
- 通过 uv 安装依赖
- 启动 uvicorn 运行 FastAPI

### alembic.ini

- Alembic 配置文件
- 数据库连接由 env.py 动态注入

### migrations/env.py

- Alembic 运行入口
- 引入应用配置和模型
- 读取 .env 中的 DATABASE_URL

### migrations/README

- Alembic 迁移目录说明

### migrations/script.py.mako

- Alembic 迁移脚本模板

### migrations/versions/a33b8a66fd24_initial_schema.py

- 初始数据库结构迁移
- 创建 users、cases、sessions、messages、scores、test_requests、audit_logs 等表

---

## 路由层（routes）

### routes/**init**.py

- 路由包占位

### routes/auth.py

- 登录认证
- JWT 生成与用户信息获取
- 使用 bcrypt 校验密码

### routes/cases.py

- 病例列表与详情
- 可用检查项列表
- 根据角色返回不同字段

### routes/sessions.py

- 会话创建与列表
- 会话详情（含消息）
- 申请检查、查询检查
- 提交诊断并评分
- 获取评分详情

### routes/chat.py

- SSE 流式对话接口
- 组装提示词
- 调用 LLM 流式生成
- 保存对话消息
- 限流控制

> 设计说明（为何核心对话逻辑位于 routes 层）
>
> 当前将 chat 相关核心编排放在 `routes/chat.py`，主要是因为该接口与 HTTP/SSE 传输细节强绑定（如 StreamingResponse、事件分片、结束信号、连接头），并且需要在同一请求链路内完成鉴权、会话状态校验、限流、流式回传与消息落库。该设计优先保证功能闭环与交付效率；随着能力扩展，再逐步把可复用的 LLM 调用与提示词构建下沉到 services 层。

---

## 数据模型层（models）

### models/base.py

- SQLAlchemy Base 与元数据命名约定
- 时间戳混入
- 通用 to_dict 工具

### models/users.py

- 用户模型
- 支持角色与外部用户 ID

### models/cases.py

- 病例模型
- 存储病史、体征、检查项、标准答案

### models/sessions.py

- 会话模型
- 记录问诊状态与诊断提交

### models/messages.py

- 消息模型
- 记录对话内容与统计信息

### models/test_requests.py

- 检查申请模型
- 记录检查类型、名称与结果

### models/scores.py

- 评分模型
- 总分、维度分数与评分细节

### models/audit_logs.py

- 审计日志模型
- 记录用户操作与上下文信息

### models/**init**.py

- 汇总导出全部模型
- Alembic 自动生成所需导入入口

---

## 数据校验层（schemas）

### schemas/auth.py

- 登录凭证、Token、用户响应模型

### schemas/cases.py

- 病例列表与详情响应
- 学生与教师视图区分

### schemas/chat.py

- 聊天请求
- 流式响应片段模型

### schemas/sessions.py

- 会话创建、列表、详情与消息结构

### schemas/scores.py

- 诊断提交请求
- 评分维度与详情结构

### schemas/tests.py

- 检查申请请求与列表
- 可用检查项定义

### schemas/**init**.py

- 统一导出所有 schema

---

## 业务服务层（services）

### services/scoring.py

- 规则评分引擎
- 问诊完整性、检查合理性、诊断准确性
- 支持诊断关键词匹配与扣分规则

### services/**init**.py

- 导出 ScoringService

---

## 工具层（utils）

### utils/jwt.py

- JWT access token 生成
- 使用配置中的密钥与算法

### utils/**init**.py

- 导出 JWT 工具
