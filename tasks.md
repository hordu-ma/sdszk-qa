# 主账本：项目优化任务清单（Tasks Ledger）

结论：本账本把当前可见的优化空间转成“可执行任务 + 验收标准 + 影响范围”。优先从 **P0（稳定性/安全/性能）** 开始，确保不影响现有业务链路（登录→选题→会话→SSE问答→历史）。

> 假设/待确认：不同机器的仓库目录可能不同。本文为可点击定位方便，使用了本次环境的绝对路径根：`/home/runner/work/sdszk-qa/sdszk-qa`；迁移到你的环境时可整体替换为你的仓库根目录。

## 1. 使用方式

- 状态：`TODO` / `DOING` / `DONE` / `BLOCKED`
- 优先级：`P0`（必须）/ `P1`（重要）/ `P2`（可选）
- 字段含义：
  - `影响面`：用户体验 / 生产安全 / 性能 / 可观测性 / 维护性 / 交付效率
  - `范围`：主要涉及的文件/目录（绝对路径）
  - `验收`：可以客观验证的条件
  - `回滚`：若上线有风险，如何快速撤回

## 2. 优先级定义

- P0：会影响稳定性/安全/性能的主链路问题（SSE、LLM、鉴权、数据一致性、限流、多实例）
- P1：提高可观测性、数据治理、测试覆盖、开发体验的一致性
- P2：结构优化、抽象收敛、长期演进项（不应阻塞 P0/P1）

## 3. 基线记录（当前仓库状态）

- CI 校验目标（见 `/home/runner/work/sdszk-qa/sdszk-qa/.github/workflows/ci.yml`）：后端 `ruff`/`basedpyright`/`pytest`；前端 `npm ci && npm run build`。
- 本地基线（本次环境）：
  - `make setup` 成功（会安装包含 `vllm/torch` 在内的大体量依赖，耗时与磁盘占用显著）。
  - `make test` 中 `tests/test_integration.py::test_e2e_flow` 失败，原因是本机未启动 PostgreSQL（`localhost:5432` 连接拒绝）；其余测试通过。

## 4. 任务清单

### P0（必须优先）

#### T-P0-001：SSE 心跳 + 客户端断连快速收敛

- 状态：TODO
- 影响面：稳定性 / 用户体验 / 成本
- 背景：SSE 长连接在代理或浏览器空闲时可能被断开；服务端也可能在客户端断连后仍继续请求 LLM，造成资源浪费。
- 范围：
  - `/home/runner/work/sdszk-qa/sdszk-qa/src/apps/api/routes/chat.py`
  - `/home/runner/work/sdszk-qa/sdszk-qa/src/apps/web/src/views/Chat.vue`
- 建议实现：
  - 服务端：每隔 N 秒发送心跳事件（如 `data: {"type":"ping"}`）；检测客户端断连后尽早停止读取/请求下游（结合 FastAPI/Starlette 的 disconnect 信号）。
  - 前端：支持 `AbortController`（点击“停止生成”时中断 fetch），并能忽略/处理心跳事件。
- 验收：
  - 代理层（Nginx）下连续对话 5 分钟不出现无输出断开（或断开后前端提示可重试）。
  - 点击“停止生成”后 1 秒内结束流读取，服务端不再继续落库“半截”回复（允许落库用户输入）。
- 回滚：以 feature flag（如环境变量）禁用心跳与中断逻辑，回退到原始 SSE。

#### T-P0-002：避免全量加载历史消息（chat 路由内存/性能）

- 状态：TODO
- 影响面：性能 / 成本
- 背景：当前 chat 路由通过 `selectinload(Session.messages)` 加载会话的全量消息，消息量增大后会拖慢请求并增加内存占用。
- 范围：
  - `/home/runner/work/sdszk-qa/sdszk-qa/src/apps/api/routes/chat.py`
  - `/home/runner/work/sdszk-qa/sdszk-qa/src/apps/api/models/`（若需要索引/字段补齐）
- 建议实现：
  - 将“最近 N 条消息”作为查询条件：只取最近 20 条（与当前构建 prompt 的逻辑一致），并按时间排序。
  - 只选择必要字段（role/content/created_at/tokens 等），避免 ORM 携带无用列。
- 验收：
  - 对于消息数 1000 的会话，`/api/chat` 请求耗时与内存显著低于全量加载（给出简单基准：例如请求前后 RSS/耗时对比）。
  - 回归：历史最近 20 条参与 prompt 与之前行为一致。
- 回滚：保留原查询方式的开关或回退提交。

#### T-P0-003：LLM 错误处理结构化与脱敏（避免把内部错误透出给用户）

- 状态：TODO
- 影响面：安全 / 用户体验 / 可运维
- 背景：当前会将下游 LLM 的原始错误文本直接返回给前端；若包含内部地址/栈信息可能造成信息泄露。
- 范围：
  - `/home/runner/work/sdszk-qa/sdszk-qa/src/apps/api/routes/chat.py`
  - `/home/runner/work/sdszk-qa/sdszk-qa/src/apps/api/exceptions.py`（若要统一错误模型）
- 建议实现：
  - 服务端：对 LLM 非 200 的响应只输出“用户可理解 + 可行动”的消息；内部细节仅写日志（带 trace_id）。
  - 前端：对 `parsed.error` 做统一渲染（避免把内部字段原样显示）。
- 验收：
  - 用户侧不出现下游 URL、端口、栈追踪等内部信息。
  - 日志中仍能通过 `trace_id` 定位具体下游错误。
- 回滚：恢复原样透出（不推荐），或仅回退到旧错误文案。

#### T-P0-004：限流在多实例下可用（slowapi 存储后端）

- 状态：TODO
- 影响面：生产安全 / 稳定性
- 背景：`slowapi` 若使用内存存储，在多副本部署时限流不一致，可能导致穿透或误杀。
- 假设/待确认：生产是否多副本、是否允许引入 Redis（或已有 Redis）。
- 范围：
  - `/home/runner/work/sdszk-qa/sdszk-qa/src/apps/api/rate_limit.py`
  - `/home/runner/work/sdszk-qa/sdszk-qa/src/infra/compose/`（若需要新增依赖服务）
- 建议实现：
  - 配置集中式存储（Redis）作为限流存储，区分 dev/prod。
  - 记录限流 key 规则（优先 user_id，回退 IP）。
- 验收：
  - 两个 API 实例共享同一限流计数；同一用户在任意实例请求都按统一阈值限制。
- 回滚：切回内存存储（仅单实例可接受）。

#### T-P0-005：Nginx 对 SSE 的超时/头转发补全

- 状态：TODO
- 影响面：稳定性 / 可观测性
- 背景：SSE 对 `proxy_read_timeout` 等较敏感；同时 trace_id 等头需要贯通。
- 范围：
  - `/home/runner/work/sdszk-qa/sdszk-qa/src/infra/compose/nginx/nginx.conf`
- 建议实现：
  - 对 `/api/chat` location 增加 `proxy_read_timeout`、`proxy_send_timeout`（例如 3600s），并转发 `X-Trace-ID`。
  - 明确 `Content-Type: text/event-stream` 的代理行为（已禁用 buffering，但建议补齐必要头）。
- 验收：
  - SSE 连续输出时不因默认超时断开；断开时可追踪 `X-Trace-ID`。
- 回滚：回退该 location 片段到旧版本。

---

### P1（重要）

#### T-P1-001：把前端 SSE 解析抽到 api 层（可复用、可测试）

- 状态：TODO
- 影响面：维护性 / 用户体验
- 范围：
  - `/home/runner/work/sdszk-qa/sdszk-qa/src/apps/web/src/views/Chat.vue`
  - `/home/runner/work/sdszk-qa/sdszk-qa/src/apps/web/src/api/`（新增/重构模块）
- 建议实现：
  - 新建 `src/apps/web/src/api/chat.ts`（或同名文件）封装：发起请求、SSE 解析、错误归一、支持 abort。
  - `Chat.vue` 只保留“状态机 + UI”。
- 验收：
  - `Chat.vue` 体积明显下降；SSE 错误处理逻辑集中且单元可测（若已有前端测试框架则加，否则仅保持结构可测）。
- 回滚：回退到 view 内联 fetch。

#### T-P1-002：结构化日志字段一致化（trace_id/user_id/session_id）

- 状态：TODO
- 影响面：可观测性 / 运维
- 范围：
  - `/home/runner/work/sdszk-qa/sdszk-qa/src/apps/api/logging_config.py`
  - `/home/runner/work/sdszk-qa/sdszk-qa/src/apps/api/middleware.py`
  - `/home/runner/work/sdszk-qa/sdszk-qa/src/apps/api/routes/chat.py`
- 建议实现：
  - 明确日志字段键名（`trace_id`、`user_id`、`session_id`、`latency_ms`、`llm_model`）。
  - 下游 LLM 调用日志打点：请求开始/结束/异常。
- 验收：
  - 任意一次对话可通过 `trace_id` 串起：入口请求→LLM调用→落库→响应完成。
- 回滚：回退日志字段新增（不影响业务）。

#### T-P1-003：测试可复现：集成测试在本地可一键启动依赖

- 状态：TODO
- 影响面：交付效率 / 质量
- 背景：`tests/test_integration.py::test_e2e_flow` 依赖本机 `localhost:5432`；对新环境不友好。
- 范围：
  - `/home/runner/work/sdszk-qa/sdszk-qa/tests/test_integration.py`
  - `/home/runner/work/sdszk-qa/sdszk-qa/src/infra/compose/dev.yml`
  - `/home/runner/work/sdszk-qa/sdszk-qa/Makefile`
- 方案选项（需先定一条）：
  - A：在测试中检测 DB 不可用时 `skip`（保持 CI 仍可通过真实 DB 跑完整 e2e）。
  - B：CI 与本地都显式用 `docker compose` 拉起依赖后再跑 e2e（更真实，耗时更高）。
- 验收：
  - 新环境按 README/Makefile 指令能 10 分钟内跑通完整测试流程（含 e2e）。
- 回滚：恢复原 e2e 连接方式。

#### T-P1-004：数据治理：messages/audit_logs 增长与归档策略

- 状态：TODO
- 影响面：成本 / 维护性 / 合规
- 范围：
  - `/home/runner/work/sdszk-qa/sdszk-qa/src/apps/api/models/`
  - `/home/runner/work/sdszk-qa/sdszk-qa/src/apps/api/migrations/`
- 建议实现：
  - 定义保留期/归档周期（例如消息保留 180 天，审计保留 365 天；仅示例，需业务确认）。
  - 为高频查询补索引；定期清理/归档任务（cron/运维流程）。
- 验收：
  - 数据量持续增长时，核心查询（会话列表/会话详情/聊天落库）P95 不明显劣化。
- 回滚：仅保留索引变更；禁用归档任务。

#### T-P1-005：依赖分层：将 vLLM/torch 作为“可选运行依赖”

- 状态：TODO
- 影响面：开发体验 / 交付效率
- 背景：当前 `uv sync --extra dev` 会拉取 `vllm/torch` 等大包，导致新环境准备成本很高；但 API 在调用外部 vLLM 时并不一定需要本地安装 vLLM。
- 假设/待确认：项目是否必须在 API 容器内安装 `vllm`（例如同机推理模式）？是否有“仅调用远程 LLM”的部署形态？
- 范围：
  - `/home/runner/work/sdszk-qa/sdszk-qa/pyproject.toml`
  - `/home/runner/work/sdszk-qa/sdszk-qa/uv.lock`
  - `/home/runner/work/sdszk-qa/sdszk-qa/src/infra/compose/`（如需在推理节点安装）
- 建议实现：
  - 将 `vllm` 移到额外的 optional extra（例如 `llm-local`），默认开发只装 API 运行所需依赖。
  - 对生产推理节点/容器明确安装策略。
- 验收：
  - “仅开发 API + 前端”场景下依赖安装时间/体积显著下降。
- 回滚：恢复依赖列表与 lock。

---

### P2（可选/长期）

#### T-P2-001：路由更薄：prompt 构建与 LLM client 下沉到 services

- 状态：TODO
- 影响面：维护性 / 可测试性
- 范围：
  - `/home/runner/work/sdszk-qa/sdszk-qa/src/apps/api/routes/chat.py`
  - `/home/runner/work/sdszk-qa/sdszk-qa/src/apps/api/services/`（新增 chat 服务）
- 建议实现：
  - 新建 `services/chat.py`（或同类模块）统一：消息截断、prompt 拼装、下游调用、错误归一。
  - 路由仅负责鉴权、参数校验与 StreamingResponse。
- 验收：
  - 服务层可在 pytest 中直接调用并 mock httpx，下游错误分支覆盖率提升。
- 回滚：回退模块拆分。

#### T-P2-002：统一任务入口与文档对齐（Makefile/README/CI）

- 状态：TODO
- 影响面：交付效率
- 范围：
  - `/home/runner/work/sdszk-qa/sdszk-qa/Makefile`
  - `/home/runner/work/sdszk-qa/sdszk-qa/README.md`
  - `/home/runner/work/sdszk-qa/sdszk-qa/.github/workflows/ci.yml`
- 建议实现：
  - Makefile 中前端安装建议改为 `npm ci`（与 CI 对齐，需保证 lock 完整）。
  - README 写清楚：e2e 需要 docker compose 依赖、以及如何跑最小子集测试。
- 验收：
  - 新人按 README 可成功跑通：lint/typecheck/unit/integration/web-build。
- 回滚：回退文档与 make target 改动。

## 5. 建议的执行顺序（路线图）

1. P0：T-P0-001 → T-P0-002 → T-P0-003（先稳住 SSE/LLM 主链路）
2. P0：T-P0-004/T-P0-005（对齐生产多实例与代理）
3. P1：T-P1-003（让测试/环境可复现，减少回归成本）
4. P1/P2：按团队节奏推进观测、数据治理与结构收敛

