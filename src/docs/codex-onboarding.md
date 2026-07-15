# Codex Onboarding

本文件用于让 Codex 或其他代码代理快速进入可工作状态，减少重复探测和误改。

## 项目目标

- 当前代码基线是“问答 MVP + 阶段 1A 首个可部署增量”：已含 Teaching Project/Version、资料/任务、审核门禁、`retrieve_basis`、最小 ModelClient、工作台基础页和 `base-spark/luyun-int`
- 完整产品 Skills、核心用户 Memory、混合 RAG、诊断/导出纵向样板、完整 ModelGateway、门禁化多智能体/多模态/微调等仍未实现；不得在代码注释或 PR 中写成已完成
- 正式模型服务和最终验收默认 vLLM；当前 `luyun-int` 使用 Ollama `qwen3.5:27b` 作为明示过渡 Provider，vLLM D0 和 `luyun-demo` 尚未完成
- 文档权威：产品范围/阶段/验收以开发计划 v1.0 为准；`2026-product-extension-*.md` 非排期
- 用户注册/认证（registered vs verified）在思政课平台用户管理实现；本仓禁止新增注册/短信/KYC，只消费平台 token/claims（计划 §2.6）
- 后端位于 `src/apps/api`
- 前端位于 `src/apps/web`
- 基础设施与 compose 位于 `src/infra/compose`
- 测试位于 `tests`

## 优先遵循的规则

1. 先读根目录 `AGENTS.md`；涉及产品范围时读开发计划相关章节；再经 `.github/INDEX.md` 打开最小指令/skill
2. 保持最小可行改动，不做无关重构；优先服务当前纵向样板，不并行铺模块
3. 后端保持薄路由，业务逻辑放入 `services`；问答编排已抽离，后续工作继续沿用该边界
4. 外部 LLM 调用在测试中必须 mock，不依赖真实模型服务
5. 改配置或接口时，说明影响范围与回滚方式
6. 不实现教师/学生总分排名或 scoring 模块；诊断为非评分
7. 不把隐式会话历史当作用户 Memory；Memory/Skills 按开发计划对象设计
8. 不创建 `tasks.md` 维护产品阶段或排期；开发计划是唯一真源，日期化实施状态直接更新计划，避免双轨漂移

## 常用命令

优先使用根目录 `Makefile`：

```bash
make harness-bootstrap
make harness-quick
make harness-backend
make test-unit
make test-integration
make harness-full
make dev-up
make dev-down
make doctor
```

Codex harness 说明见 `src/docs/codex-harness.md`。

等价原生命令：

```bash
uv sync --frozen --extra dev
npm --prefix src/apps/web install
uv run --frozen --extra dev ruff check .
uv run --frozen --extra dev basedpyright
uv run --frozen --extra dev pytest -m "not integration"
uv run --frozen --extra dev pytest -m integration
npm --prefix src/apps/web run build
docker compose -f src/infra/compose/dev.yml up -d
```

## 最低交付标准

- 代码修改后至少运行与改动直接相关的验证
- 后端行为变更优先补或更新 `tests/` 中的回归测试
- 前端行为变更至少执行一次 `make web-build`
- 无法验证时，明确说明原因、影响范围和残余风险

## 高风险区域

- `src/apps/api/routes/chat.py`：SSE 输出链路，容易受响应格式和缓冲行为影响
- `src/apps/api/config.py`：配置项在导入时生效，测试环境变量需稳定
- `src/infra/compose/*.yml` 与 `src/infra/compose/nginx/nginx.conf`：涉及部署和联调，改动前后要说明影响范围
- 数据库模型与迁移：变更 schema 时要同步考虑 migration、service、schema 和 tests

## 推荐工作流

1. 先定位改动表面和依赖文件
2. 优先查找现有 `.github/skills/` 是否已有匹配技能
3. 做最小改动，避免顺手重构
4. 先跑最小相关验证，再决定是否扩大验证范围
5. 输出结果时附关键文件路径和未验证风险
