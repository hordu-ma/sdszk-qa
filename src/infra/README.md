# 基础设施说明

本文档说明 `src/infra` 目录中各配置文件的作用，以及 `base-spark` 集成环境的运维步骤。

> 本地开发命令见[开发指南](../docs/DEVELOPMENT.md)。
> `base-spark.yml` 是阶段 1 工程集成环境基线；正式 A/B 生产文件仍是问答 MVP 基线。
> 演示环境只能展示已实现能力，阶段口径以主开发计划为准。

## 目录结构

```
infra/
├── compose/
│   ├── compose.yaml       # 基础服务定义（通用模板）
│   ├── dev.yml            # 本地开发环境配置
│   ├── prod-a.yml         # 生产环境 A 占位（共享现网 Nginx，不启容器）
│   ├── prod-b.yml         # 生产环境 B（vLLM 推理节点）
│   └── nginx/
│       └── nginx.conf     # 反向代理配置
└── README.md              # 本文档
```

---

## 配置文件详解

### 1. **compose.yaml** - 基础服务定义

**作用**：定义项目的核心基础服务模板，被其他 compose 文件继承使用。

**包含的服务**：

- **PostgreSQL 17 + pgvector**
  - 数据库服务
  - 默认暴露端口 5432
  - 支持环境变量配置用户名、密码、数据库名
  - 包含健康检查机制

- **MinIO (Latest)**
  - 对象存储服务（S3 兼容）
  - API 端口 9000（对象操作）
  - 控制台端口 9001（Web 管理界面）
  - 支持环境变量配置根用户凭证

**使用方式**：通常不直接使用，作为 `dev.yml` 和 `prod-b.yml` 的基础。

---

### 2. **dev.yml** - 本地开发环境

**作用**：为本地开发提供完整的运行环境，支持代码热重载和快速迭代。

**启动命令**：

```bash
docker compose -f src/infra/compose/dev.yml up -d
```

**包含的服务**：

- PostgreSQL + MinIO（继承自 compose.yaml）
- **API 容器**
  - 从项目源代码构建（Dockerfile：`src/apps/api/Dockerfile`）
  - 挂载 `src/` 卷用于代码热重载
  - 暴露端口 8000
  - 使用默认凭证和开发配置

**主要特点**：

- ✅ 所有服务端口对本机完全开放（便于调试）
- ✅ 快速迭代开发体验
- ✅ 使用默认凭证（`JWT_SECRET=dev-change-me`）
- ✅ LLM 服务指向本地外部 vLLM（`host.docker.internal:8001`）

开发期如需临时使用 Ollama，可通过当前最小 ModelClient 和 Provider Adapter 指定 `LLM_PROVIDER`、`LLM_BASE_URL` 和 `LLM_MODEL` 做问答链路验证；这不代表 Ollama 可作为正式默认配置。完整能力路由仍须由后续 ModelGateway 完成。

**环境变量示例**：

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/luyun_sizheng
MINIO_ENDPOINT=minio:9000
LLM_BASE_URL=http://host.docker.internal:8001
LLM_MODEL=<必须与/v1/models返回的id一致>
ENV=dev
```

---

### 3. **prod-a.yml** - 生产环境 A（共享 Nginx 占位）

**作用**：用于标识 A 服务器（172.18.6.117）入口层部署模式。

**当前约束**：A 服务器已有线上 Nginx 在运行，本项目不能独占 Nginx。

**文件策略**：

- `prod-a.yml` 不再启动任何容器（`services: {}`）
- A 服务器仅进行两项工作：
  - 发布前端静态资源（`dist`）到现网目录
  - 将 `nginx/nginx.conf` 的增量片段并入现有 Nginx 配置

**使用场景**：

- 单机已存在共享网关 Nginx，需要增量接入新应用
- 避免覆盖/替换现网主配置

---

### 4. **prod-b.yml** - 生产环境 B（高性能推理）

**作用**：生产环境配置，服务器 B 专用于 LLM 推理任务，具有 GPU 支持。

**包含的服务**：

- PostgreSQL + MinIO（基础服务，无端口暴露）
- **vLLM 容器**（核心组件）
  - 使用 NVIDIA GPU 加速（`runtime: nvidia`）
  - 支持 CUDA 设备选择（`CUDA_VISIBLE_DEVICES`）
  - 可配置显存利用率（`VLLM_GPU_MEMORY_UTILIZATION`）
  - 支持模型长度限制（`VLLM_MAX_MODEL_LEN`）
  - 挂载模型卷（`VLLM_MODEL_VOLUME`）
  - 暴露推理端口 8001

- **API 容器**
  - 暴露端口 8000
  - LLM 直接调用本地 vLLM（`LLM_BASE_URL=http://vllm:8001`）

**主要特点**：

- ✅ 专用 AI 推理节点
- ✅ GPU 加速推理
- ✅ 高性能、低延迟
- ✅ API 与 vLLM 同机部署，网络开销最小

**使用场景**：

- 高并发推理需求
- 需要 GPU 加速
- 独立的推理服务器

**目标口径**：

- 正式校内部署、稳定演示和最终验收默认使用 vLLM。
- Ollama 仅用于前期开发、vLLM 兼容性验证期间的过渡和明确标注的备用 Provider。
- `prod-b.yml` 已固定到 vLLM `0.18.0` 镜像摘要和生成模型 revision；进入演示冻结或生产发布前仍须在目标硬件完成专业质量、Chat Template、结构化输出、SSE、容量和重启门禁。
- 应用当前通过 ModelClient/Provider Adapter 使用逻辑模型名；完整 ModelGateway 落地前，`LLM_MODEL` 仍必须与当前 Provider 的 `/v1/models` 返回 ID 一致。

---

### 5. **nginx/nginx.conf** - 反向代理增量片段

**作用**：供 A 服务器现网 Nginx 复用的增量 `location` 片段（并入已有 `server {}`）。

**固定后端地址**：

- A 服务器：`172.18.6.117`
- B 服务器：`172.18.6.123`
- API 上游：`http://172.18.6.123:8000`

**路由规则**：

| 路由        | 目标                 | 说明                                              |
| ----------- | -------------------- | ------------------------------------------------- |
| `/`         | 本地静态文件         | Vue.js 前端应用（`/data/www/luyun-sizheng/dist`） |
| `/api/*`    | 后端服务             | 常规 API 请求代理                                 |
| `/api/chat` | 后端服务（特殊处理） | SSE 流式响应，禁用缓冲                            |

**特殊配置**：

- **SSE 流式传输**（`/api/chat`）：
  - 禁用缓冲：`proxy_buffering off; proxy_cache off;`
  - 禁用分块编码：`chunked_transfer_encoding off;`
  - HTTP/1.1 支持长连接

**使用方式**：

- 不替换主配置：将本文件内容并入现有 `server {}`（如 `include` 或手动合并）
- 在现网主配置中继续沿用既有证书、`listen 443 ssl`、`server_name`

---

## 部署架构示意

```
┌─────────────────────────────────────┐
│       本地开发环境 (dev.yml)         │
├─────────────────────────────────────┤
│  ├─ PostgreSQL (5432)               │
│  ├─ MinIO (9000, 9001)              │
│  └─ API (8000) [热重载]             │
│       ↓ (通过 host.docker.internal) │
│     外部 vLLM (8001)                │
└─────────────────────────────────────┘

┌────────────────────────────────────────┐
│  生产环境 - 双服务器部署               │
├────────────────────────────────────────┤
│                                        │
│  服务器 A (172.18.6.117)             │
│  ├─ 现网 Nginx (共享) [并入片段]      │
│  └─ 前端静态资源 (dist)               │
│      ↓ 反向代理 /api                  │
│  服务器 B (prod-b.yml)                │
│  ├─ vLLM (8001) [GPU 加速]           │
│  ├─ API (8000)                        │
│  ├─ PostgreSQL                        │
│  └─ MinIO                             │
│                                        │
└────────────────────────────────────────┘
```

## Base-Spark 集成环境与目标晋级

Base-Spark 不直接复用 `dev.yml`，也不替代客户正式 A/B 环境。当前已落地 `luyun-int`，目标仍是两套相互隔离的 Compose/Profile：

| 环境 | 用途 | 更新规则 | 模型服务 |
| --- | --- | --- | --- |
| `luyun-int` | 开发联调、迁移、Provider 切换和故障测试 | 每个可运行增量或至少每周部署 | 固定候选 vLLM 主链；允许明示测试 Ollama 备用 |
| `luyun-demo` | 随时演示和投标彩排 | 只接收通过门禁的同一不可变镜像 | 固定版本 vLLM 默认，Ollama 明示降级 |

发布链路：

```text
自动测试 → luyun-int → virtus/Tailscale 验证 → 专业与安全门禁
         → 同一镜像摘要晋级 luyun-demo → 保留上一稳定版本
```

两套环境使用不同 project name、网络、卷、Secret 和数据快照。只有 loopback Web 入口可由 Tailscale Serve 转发；API、PostgreSQL、MinIO、Redis、vLLM 和 Ollama 不直接暴露给浏览器或 Tailnet。

阶段 1 工程样板已形成“查依据—备课—诊断—导出”技术闭环，并完成 `luyun-int → luyun-demo` 同镜像模拟工程晋级。三类模型仍是工程候选资产，64 个案例是显式 `synthetic` 工程集；专家金标、正式模型选型、Virtus 新增功能人工验收和 G0/G1 外部签字尚未完成。

> 迁移 `f7b8c9d0e123` 起依赖 `pg_trgm`，迁移 `i9d0e1f2a345` 起依赖 `vector`。Base-Spark 使用固定摘要的 `pgvector/pgvector:pg17-trixie`；迁移会执行 `CREATE EXTENSION IF NOT EXISTS`，数据库用户须具备创建扩展权限。

### Base-Spark 阶段 1 集成环境

敏感变量必须保存在仓库外。Base-Spark 当前使用 `/home/pgx/luyun-sizheng-int.env`（权限 `0600`）；Snap 版 Docker Compose 无法读取 `/home/pgx/.config/` 下的运行文件，不要把 env 移回该目录。该文件是**重新构建或重新创建容器**的前置条件，不要提交到 Git。首次部署或发布新镜像的顺序：

```bash
docker compose --project-name luyun-int --env-file /home/pgx/luyun-sizheng-int.env -f src/infra/compose/base-spark.yml build
docker compose --project-name luyun-int --env-file /home/pgx/luyun-sizheng-int.env -f src/infra/compose/base-spark.yml run --rm --no-deps -w /app/src/apps/api api uv run alembic upgrade head
docker compose --project-name luyun-int --env-file /home/pgx/luyun-sizheng-int.env -f src/infra/compose/base-spark.yml --profile model-baseline --profile semantic-rag up -d --wait
docker compose --project-name luyun-int --env-file /home/pgx/luyun-sizheng-int.env -f src/infra/compose/base-spark.yml exec api uv run python -m src.apps.api.scripts.seed_demo
```

2026-07-17 当前发布候选：应用镜像 `stage1-gold-review-20260717-r1`，迁移 `k1f2a3b4c567 (head)`，发布前备份位于 `/home/pgx/backups/luyun-sizheng/20260717-stage1-gold-review-predeploy/`。迁移已在独立测试库和 `luyun-int` 通过 `j0e1f2a3b456 → k1f2a3b4c567 → j0e1f2a3b456 → k1f2a3b4c567`；`luyun-int` 已验证上一应用镜像回滚和当前镜像恢复，随后以同一 API/Web 镜像摘要晋级 `luyun-demo`。双环境已验证健康检查、真实 vLLM SSE、双评共识、分歧仲裁、冻结运行及占位案例防冻结；固定模型资产如下，均为工程候选，不代表专业选型：

本轮回滚：将仓库外 env 的 `RELEASE_TAG` 改回 `stage1-synthetic-gate-20260717-r1`，停止当前 API，将数据库降到 `j0e1f2a3b456`，再重新创建上一 API/Web；恢复当前版本时按相反顺序升级到 `k1f2a3b4c567`。数据损坏时从上述发布前备份恢复 PostgreSQL/MinIO。`luyun-demo` 可用 `tailscale serve --https=8443 off` 撤销入口，并停止其 Compose project；普通停用不得加 `-v`。

| 类型 | 资产 | 固定 revision | 服务名 / loopback |
| --- | --- | --- | --- |
| 运行时 | `vllm/vllm-openai:v0.18.0` | 镜像摘要见 Compose | — |
| 生成 | `Qwen/Qwen2.5-0.5B-Instruct` | `7ae557604adf67be50417f59c2c2f167def9a775` | `teaching-chat-engineering` / `28001` |
| Embedding | `BAAI/bge-small-zh-v1.5` | `7999e1d3359715c523056ef9478215996d62a620` | `teaching-embedding` / `28002` |
| Reranker | `BAAI/bge-reranker-v2-m3` | `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` | `teaching-reranker` / `28003` |

模型服务由 Compose profile 控制；正常停启保留模型缓存卷：

```bash
docker compose --project-name luyun-int --env-file /home/pgx/luyun-sizheng-int.env -f src/infra/compose/base-spark.yml --profile model-baseline --profile semantic-rag start vllm-generation vllm-embedding vllm-reranker
curl -fsS http://127.0.0.1:28001/health
curl -fsS http://127.0.0.1:28002/health
curl -fsS http://127.0.0.1:28003/health

docker compose --project-name luyun-int --env-file /home/pgx/luyun-sizheng-int.env -f src/infra/compose/base-spark.yml --profile model-baseline --profile semantic-rag stop vllm-reranker vllm-embedding vllm-generation
```

本轮实机验收结果：两套环境三类服务均使用固定 vLLM `0.18.0`；Demo 通过真实 SSE `[DONE]`、64 例冻结模拟集运行、六 Skill、显式 Memory、版本与 Word 导出。停用 Demo Reranker 后检索显式降级为 `hybrid_trgm_char_vector` 且无 5xx，服务恢复后健康。64 例结果为 43 `matched`、21 `failed`、0 `error`，仅作为工程差距基线。

本次 HTTPS 验收已覆盖双账号角色、六个 Skill、项目/资料/任务、管理员跨用户审核、教师审核 403、显式 Memory、对齐卡、蓝图、课时分块、非评分诊断、版本差异和 Word 下载。真实 vLLM SSE 返回内容、结束事件和 `[DONE]`，`/api/workbench/model-status` 报告 `vllm · teaching-chat-engineering` 且未降级。真实 Chromium 通过 Tailnet HTTPS 验证步骤门禁逐级解锁、Memory 清除确认、教师端隐藏审核按钮、语义 RAG、失败任务原因和 `word-standard-v2` 下载；DOCX 经 ZIP 检查和 LibreOffice 渲染为 3 页 PDF，包含标题、列表和表格且无内部字典文本。用户已完成此前工作台的 Virtus 人工浏览器验收；本轮自动 Chromium 回归在 Base-Spark 执行，不冒充新的 Virtus 跨设备人工验收。

当前已有容器的日常启用不需要重建，也不需要再次执行 seed：

```bash
docker start luyun-int-postgres-1 luyun-int-minio-1
docker start luyun-int-vllm-generation-1 luyun-int-vllm-embedding-1 luyun-int-vllm-reranker-1
docker start luyun-int-api-1
docker start luyun-int-web-1
docker ps --filter name=luyun-int --format 'table {{.Names}}\t{{.Status}}'
curl -fsS http://127.0.0.1:8088/healthz
```

日常停用应用容器使用以下顺序。维护期间建议先停 Serve，避免访问者收到代理错误：

```bash
tailscale serve --https=443 off
docker stop luyun-int-web-1 luyun-int-api-1
docker stop luyun-int-vllm-reranker-1 luyun-int-vllm-embedding-1 luyun-int-vllm-generation-1
docker stop luyun-int-minio-1 luyun-int-postgres-1
```

不要使用 `docker compose down -v` 或删除命名卷进行普通停用；`-v` 会删除数据库和对象存储数据。容器设置为 `restart: unless-stopped`，宿主重启后会自动恢复；如果曾手动 `docker stop`，需按上面的日常启用步骤重新启动。

Base-Spark 当前防火墙不允许新建 Docker bridge 从宿主转发，因此阶段 1 Compose 使用 host network，但所有服务只绑定 loopback。默认 `luyun-int` 使用 Web `8088`、API `28000`、PostgreSQL `25432`、MinIO `29000/29001`、vLLM `28001/28002/28003`；`luyun-demo` 使用 Web `8098`、API `28100`、PostgreSQL `26432`、MinIO `30000/30001`、vLLM `28101/28102/28103`。端口均由 env 参数化，示例见 `src/infra/env/base-spark-demo.env.example`。

### Base-Spark 稳定模拟演示环境

`/home/pgx/luyun-sizheng-demo.env` 为仓库外 `0600` 文件；从模板创建后必须替换全部 Secret。晋级顺序：

```bash
docker compose --project-name luyun-demo --env-file /home/pgx/luyun-sizheng-demo.env -f src/infra/compose/base-spark.yml up -d --wait postgres minio
docker compose --project-name luyun-demo --env-file /home/pgx/luyun-sizheng-demo.env -f src/infra/compose/base-spark.yml run --rm --no-deps -w /app/src/apps/api api uv run alembic upgrade head
docker compose --project-name luyun-demo --env-file /home/pgx/luyun-sizheng-demo.env -f src/infra/compose/base-spark.yml --profile model-baseline --profile semantic-rag up -d --wait
docker compose --project-name luyun-demo --env-file /home/pgx/luyun-sizheng-demo.env -f src/infra/compose/base-spark.yml exec api uv run python -m src.apps.api.scripts.seed_demo
```

晋级前必须确认 Demo 与 Int 的 API/Web 容器 `.Image` 摘要分别一致；禁止在 Demo 端使用相同 tag 重新构建一份不同镜像。

### Tailscale Serve 启用、停用与验证

当前映射：

```text
https://base-spark.tail84088a.ts.net/ -> http://127.0.0.1:8088
https://base-spark.tail84088a.ts.net:8443/ -> http://127.0.0.1:8098
```

Serve 只向同一 Tailnet 提供 HTTPS，不启用 Funnel，也不直接暴露 API、数据库、MinIO 或模型端口。`--bg` 写入 `tailscaled` 的 Serve 配置，命令退出后映射仍保持；宿主重启后仍应复核状态。

#### 每次启用

1. 先启动并检查 `luyun-int` 应用：

   ```bash
   docker start luyun-int-postgres-1 luyun-int-minio-1
   docker start luyun-int-vllm-generation-1 luyun-int-vllm-embedding-1 luyun-int-vllm-reranker-1
   docker start luyun-int-api-1
   docker start luyun-int-web-1
   curl -fsS http://127.0.0.1:8088/healthz
   ```

2. 启用 Serve 并核对映射：

   ```bash
   tailscale serve --bg http://127.0.0.1:8088
   tailscale serve status
   ```

3. 从 `base-spark` 验证 Tailnet HTTPS：

   ```bash
   curl -fsS https://base-spark.tail84088a.ts.net/healthz
   ```

4. 在已登录同一 Tailnet 的 Virtus 浏览器访问集成环境 <https://base-spark.tail84088a.ts.net/> 或稳定模拟演示 <https://base-spark.tail84088a.ts.net:8443/>，完成登录、模拟标记、工作台和 SSE 问答冒烟。

2026-07-17 记录：根入口与 `:8443` 均为 Tailnet-only，Base-Spark 通过两个 HTTPS `/healthz`；Demo 的真实 SSE、样板和降级从 Base-Spark 验证。新增模拟标记与稳定演示仍待 Virtus 人工复核，不得表述为跨设备人工验收完成。

#### 每次停用

仅停用 Tailnet HTTPS 入口、保留应用运行：

```bash
tailscale serve --https=443 off
tailscale serve status
```

如需完整停机，再按上一节顺序停止全部 7 个 `luyun-int` 容器。不要用 `tailscale serve reset` 代替普通停用；`reset` 会清空该节点全部 Serve 配置，只有确认不存在其他处理器时才可使用。

#### 测试账号

| 项目 | 值 |
| --- | --- |
| URL | `https://base-spark.tail84088a.ts.net/` |
| 教师用户名 | `demo_teacher` |
| 教师角色 | `teacher`（创建项目、上传资料和运行教学流程，不可审核） |
| 管理员用户名 | `demo_admin` |
| 管理员角色 | `admin`（审核资料） |
| 密码 | 仅存放在对应仓库外 env 文件，不写入文档或 Git |

这两个账号只用于阶段 1 合成数据验证。正式客户部署、公开演示或 Tailnet 访问范围扩大前，必须删除或轮换账号和密码；不得复用当前数据库、JWT、MinIO 等环境 Secret。

#### 常见故障

- 首次提示 `Serve is not enabled on your tailnet`：按命令输出的管理员链接启用 Serve，返回终端后重新执行启用命令。
- 出现 `Preconditions failed: etag mismatch`：说明另一个客户端刚修改 Serve 配置；先运行 `tailscale serve status`，再重试同一启用命令。2026-07-15 首次启用曾出现该竞争，重试后成功。
- HTTPS 返回 `502`：先检查 `docker ps --filter name=luyun-int` 和 `curl http://127.0.0.1:8088/healthz`；本地入口不健康时不要反复重配 Serve。
- Virtus 无法访问：确认 Virtus 已登录同一 Tailnet、MagicDNS 可解析该主机，并由 Tailnet 管理员核对 ACL/Grant；不要为排障启用 Funnel 或把服务绑定到 `0.0.0.0`。
- 宿主重启后：先运行 `systemctl is-active tailscaled snap.docker.dockerd.service`，再依次检查 `docker ps`、loopback `/healthz`、`tailscale serve status` 和 Tailnet HTTPS `/healthz`，任一层失败就从该层修复。

若 Serve 临时不可用，在 `virtus` 上使用计划允许的 SSH 转发降级路径：

```bash
ssh -N -L 18088:127.0.0.1:8088 pgx@base-spark
```

保持终端运行，并在 `virtus` 浏览器访问 `http://127.0.0.1:18088`。当前正常运行时页面应显示 `vllm · teaching-chat-engineering`；若人工切到 Ollama 备用，页面必须明确显示 Provider 变化。

---

## 环境变量配置

### 通用变量

| 变量                  | 默认值              | 说明         |
| --------------------- | ------------------- | ------------ |
| `POSTGRES_USER`       | postgres            | 数据库用户   |
| `POSTGRES_PASSWORD`   | postgres (dev)      | 数据库密码   |
| `POSTGRES_DB`         | luyun_sizheng       | 数据库名     |
| `MINIO_ROOT_USER`     | minioadmin          | MinIO 用户   |
| `MINIO_ROOT_PASSWORD` | minioadmin (dev)    | MinIO 密码   |
| `JWT_SECRET`          | dev-change-me (dev) | JWT 签名密钥 |
| `ENV`                 | dev                 | 环境标识     |

### 开发环境特定变量

| 变量           | 默认值                           | 说明         |
| -------------- | -------------------------------- | ------------ |
| `LLM_BASE_URL` | http://host.docker.internal:8001 | LLM 服务地址 |
| `LLM_MODEL`    | 与 `/v1/models` 返回 `id` 一致   | LLM 模型名称 |

### 生产环境 B 特定变量

| 变量                          | 默认值 | 说明             |
| ----------------------------- | ------ | ---------------- |
| `CUDA_VISIBLE_DEVICES`        | 0      | GPU 设备编号     |
| `VLLM_MODEL_PATH`             | 必需   | 模型文件路径     |
| `VLLM_MODEL_REVISION`         | 必需   | 模型精确 revision |
| `VLLM_MODEL_VOLUME`           | 必需   | 模型挂载卷       |
| `VLLM_MAX_MODEL_LEN`          | 8192   | 模型最大序列长度 |
| `VLLM_GPU_MEMORY_UTILIZATION` | 0.9    | GPU 显存利用率   |

---

## 快速开始

### 本地开发

```bash
# 启动开发环境
docker compose -f src/infra/compose/dev.yml up -d

# 查看日志
docker compose -f src/infra/compose/dev.yml logs -f

# 停止服务
docker compose -f src/infra/compose/dev.yml down
```

> 提示：若 API 调用 vLLM 出现 `404/502`，先检查 `.env` 中 `LLM_MODEL` 是否与 `curl http://localhost:8001/v1/models` 返回的 `id` 完全一致。Ollama 临时接入也必须使用其实际模型 ID；不能假设两个 Provider 的模型名称相同。

### 生产部署（两服务器）

**服务器 A（172.18.6.117）：**

```bash
# 1) 本地构建前端
cd src/apps/web && npm run build

# 2) 上传 dist 到 A 服务器现网静态目录（示例目录）
# rsync -avz src/apps/web/dist/ <user>@172.18.6.117:/data/www/luyun-sizheng/dist/

# 3) 将 src/infra/compose/nginx/nginx.conf 并入现网 Nginx 的目标 server {}
# 4) 校验并重载
nginx -t && nginx -s reload
```

**服务器 B：**

```bash
# 创建 .env 配置
POSTGRES_PASSWORD=your-password
MINIO_ROOT_PASSWORD=your-password
VLLM_MODEL_PATH=/path/to/model
VLLM_MODEL_VOLUME=/data/models

# 启动
docker compose -f src/infra/compose/prod-b.yml up -d
```

---

## 注意事项

1. **开发环境**：使用 `dev.yml` 时，确保本地有 vLLM 服务运行在 8001 端口
2. **生产环境**：
   - 所有凭证必须通过 `.env` 文件配置，不要使用默认值

- A 服务器沿用现网 Nginx 证书配置，不要替换主配置
- 配置防火墙规则，仅开放必要端口
- 定期备份 PostgreSQL 和 MinIO 数据

3. **GPU 支持**：`prod-b.yml` 需要服务器安装 NVIDIA Docker runtime，参考 [NVIDIA Container Toolkit](https://docs.nvidia.com/ai-enterprise/deployment-guide-vmware/0.1.0/docker-setup.html)
