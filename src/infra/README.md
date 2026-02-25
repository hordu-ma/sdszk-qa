# Infrastructure 基础设施配置

本文档说明 `src/infra` 目录中各个配置文件的作用及其适用场景。

> 本地开发启动请参考：`src/docs/本地开发启动指南.md`。

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

- **PostgreSQL (15-Alpine)**
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

> 提示：若 API 调用 vLLM 出现 `404/502`，先检查 `.env` 中 `LLM_MODEL` 是否与 `curl http://localhost:8001/v1/models` 返回的 `id` 完全一致。

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
