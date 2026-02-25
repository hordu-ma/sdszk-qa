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
- 主题：`GET /api/cases`、`GET /api/cases/{case_id}`
- 会话：`POST /api/sessions`、`GET /api/sessions`、`GET /api/sessions/{session_id}`
- 对话：`POST /api/chat`（SSE）

## 开发与部署

- 开发规范：见 [AGENTS.md](AGENTS.md)
- 生产部署：见 [生产部署指南.md](生产部署指南.md)
- 架构说明：见 [src/docs/ARCHITECTURE.md](src/docs/ARCHITECTURE.md)
- 执行流程（SKILL）：见 [SKILLS/README.md](SKILLS/README.md)

## 测试

```bash
pytest
pytest --cov=src/apps/api --cov-report=term-missing
```

## 可审计数据

- messages（问答内容、token、延迟）
- sessions（会话状态、起止时间）
- audit_logs（用户行为）

## 阶段进展（已完成）

> 更新日期：2026-02-25

- 已完成“临床问诊 -> 思政问答”的第一阶段改造：
  - 下线评分与检查流程，保留纯问答主链路
  - 聊天提示词切换为“鲁韵思政教学支持助手”
  - 前端问答页移除“申请检查/提交诊断”入口
- 已完成“开箱即用”主题会话能力：
  - 支持 `custom` 模式按老师输入主题直接创建会话
  - 固定主题库已替换为首批思政主题种子数据（`src/cases/*.json`）
- 已完成文档与语义清理：
  - 主文档与架构文档改为思政项目口径
  - 新增改造与迁移规划文档：
    - `鲁韵思政改造任务清单.md`
    - `数据库字段重命名迁移方案.md`

## 下一步开发计划

1. 数据层兼容迁移（阶段 B）
   - 新增思政语义字段（如 `core_request`、`scenario_text`、`reference_answer`）
   - 实现新旧字段双写与读优先新字段
2. 主题检索与推荐
   - 在固定主题库基础上增加关键词检索、学段筛选、难度筛选
3. 输出质量治理
   - 增加思政场景回归样本（教学设计/教研/评价）
   - 建立提示词版本管理与效果对比
4. 工程化收敛
   - 清理历史医疗命名的遗留代码与文案
   - 完成全量测试与前端构建验证（含本地 PostgreSQL 联调）
