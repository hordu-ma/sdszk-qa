# Infrastructure 基础设施配置

本文档说明 `src/infra` 目录中各个配置文件的作用及其适用场景。

## 目录结构

```
infra/
├── compose/
│   ├── compose.yaml       # 基础服务定义（通用模板）
│   ├── dev.yml            # 本地开发环境配置
│   ├── prod-a.yml         # 生产环境 A（API + 反向代理）
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
DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/clinic_sim
MINIO_ENDPOINT=minio:9000
LLM_BASE_URL=http://host.docker.internal:8001
LLM_MODEL=<必须与/v1/models返回的id一致>
ENV=dev
```

---

### 3. **prod-a.yml** - 生产环境 A

**作用**：生产环境配置，服务器 A 运行 API 和基础服务，由外部 Nginx 反向代理。

**包含的服务**：

- PostgreSQL（无端口暴露）
- MinIO（无端口暴露）
- **API 容器**
  - 从编译后的源代码构建
  - 仅暴露端口 8000（给反向代理访问）
  - 没有卷挂载（使用构建时的源代码）

**主要特点**：

- ✅ 生产级安全配置（仅必要端口暴露）
- ✅ 数据库和 MinIO 凭证由环境变量强制指定（无默认值）
- ✅ 不包含 Nginx（由外部反向代理或 CDN 管理）

**使用场景**：

- 需要 API 和数据库在同一服务器
- 外部有独立的反向代理（如云服务提供商的 Nginx）

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

### 5. **nginx/nginx.conf** - 反向代理配置

**作用**：Nginx 反向代理配置，负责流量分发和 SSL/TLS 终止，部署在生产环境 A。

**上游配置**：

```nginx
upstream backend {
    server <B服务器IP>:8000;
}
```

- 指向生产环境 B 的 API 服务器

**路由规则**：

| 路由        | 目标                 | 说明                                       |
| ----------- | -------------------- | ------------------------------------------ |
| `/`         | 本地静态文件         | Vue.js 前端应用（`/usr/share/nginx/html`） |
| `/api/*`    | 后端服务             | 常规 API 请求代理                          |
| `/api/chat` | 后端服务（特殊处理） | SSE 流式响应，禁用缓冲                     |

**特殊配置**：

- **SSL/TLS 支持**：443 端口，使用证书文件
- **SSE 流式传输**（`/api/chat`）：
  - 禁用缓冲：`proxy_buffering off; proxy_cache off;`
  - 禁用分块编码：`chunked_transfer_encoding off;`
  - HTTP/1.1 支持长连接

**使用方式**：

- 挂载至容器：`./nginx/nginx.conf:/etc/nginx/nginx.conf:ro`
- 需在容器部署时准备 SSL 证书：`./nginx/ssl/{cert.pem, key.pem}`

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
│  服务器 A (prod-a.yml)                │
│  ├─ Nginx (80, 443)   [nginx.conf]    │
│  ├─ PostgreSQL        [无端口暴露]    │
│  ├─ MinIO             [无端口暴露]    │
│  └─ API (8000)                        │
│      ↓                                │
│    (反向代理)                         │
│      ↓                                │
│  服务器 B (prod-b.yml)                │
│  ├─ vLLM (8001) [GPU 加速]           │
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
| `POSTGRES_DB`         | clinic_sim          | 数据库名     |
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

**服务器 A：**

```bash
# 创建 .env 配置
DATABASE_URL=postgresql+psycopg://user:password@prod-b-server:5432/clinic_sim
MINIO_ENDPOINT=prod-b-server:9000
MINIO_ACCESS_KEY=your-key
MINIO_SECRET_KEY=your-secret
JWT_SECRET=your-secret-key
LLM_BASE_URL=http://prod-b-server:8001
LLM_MODEL=your-model

# 启动
docker compose -f src/infra/compose/prod-a.yml up -d
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
   - 为 Nginx 准备有效的 SSL 证书
   - 配置防火墙规则，仅开放必要端口
   - 定期备份 PostgreSQL 和 MinIO 数据

3. **GPU 支持**：`prod-b.yml` 需要服务器安装 NVIDIA Docker runtime，参考 [NVIDIA Container Toolkit](https://docs.nvidia.com/ai-enterprise/deployment-guide-vmware/0.1.0/docker-setup.html)
