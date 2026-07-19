# 阶段 1 模拟信息替换台账

> 日期：2026-07-17
> 状态：工程可执行；真实资料、专家审核和客户签字待补，已按主计划 §0.5 自助开发模式冻结为补签清单
> 结论：当前 `luyun-int`/`luyun-demo` 用模拟信息验证工程链路，不构成 G0/G1 专业验收。自助开发模式期间本台账的门禁与 §5 限制继续全部生效。

## 1. 识别与门禁

- 运行环境通过 `CONTENT_MODE=synthetic` 和 `CONTENT_DISCLAIMER` 向 API/工作台显示模拟状态。
- 模拟项目标题以 `[模拟]` 开头，资料文件名使用 `synthetic-stage1-*`，资料正文包含模拟免责声明。
- 评测数据集 `data_origin` 只允许 `synthetic`、`internal_authored`、`customer_provided`、`expert_authored`。
- `synthetic` 数据集的 `review_status` 固定为 `not_applicable`；审核 API 拒绝将其标记为 `approved`。
- `internal_authored`（内部自研，自助开发模式 §0.5 新增）：允许走完整双评/仲裁与来源审核流程用于内部金标和流程演练，但名称、描述与报告必须始终明示"内部自研、非专家数据"；禁止改来源冒充 `customer_provided`/`expert_authored`，其结论不得用于对外承诺。
- `customer_provided`/`expert_authored` 新数据集初始为 `pending`，只能由 `reviewer`/`admin` 留下审核意见后变更状态。
- 正式案例支持两位不同审核人独立复核；结论不一致时必须由未参与双评的第三人仲裁。`placeholder=true` 案例始终阻止正式冻结。

## 2. 当前模拟项与替换入口

| 模拟项 | 当前内容 | 代码/数据入口 | 真实替换要求 | 替换后验证 |
| --- | --- | --- | --- | --- |
| 样板范围 | 高中、议题式、家国情怀与青年责任 | `seed_demo.py`、工程冻结基线 | 客户确认学段、课型、主题与成果类型 | 四类任务主链、版本差异、Word 导出 |
| 可信资料 | 8 份自造 Markdown 资料 | `seed_demo.py`、MinIO `synthetic/stage1/` | 导入已授权原件，登记版本、有效期、责任人；不得覆盖模拟原件 | 解析、审核、引用定位、资料不足 |
| 工程案例 | 8 个主题 × 8 个问题，共 64 例 | `stage1-synthetic-g0` v1 | 新建 `customer_provided` 或 `expert_authored` 数据集版本；禁止修改冻结集 | 冻结哈希、逐案例结果、发布清单 |
| 专家金标 | 治理工具已实现，内部金标 v0（`stage1-internal-gold`，140 例，`internal_authored`）已走通双评/仲裁全流程；仍没有真实专家金标 | `evaluation_case_reviews`、案例金标状态、评测治理工作台、`seed_internal_gold.py` | 批量导入真实案例；两位专家独立复核，分歧由第三人仲裁；移除全部占位标记 | 双专家一致性、仲裁独立性、专业阈值、一票否决项 |
| 教学结构/诊断 | 三个工程诊断维度（规则字典 v2 内部版承载，`services/diagnostic_rules.py`） | 工程冻结基线、Skill 输出 Schema、`diagnostic_rules.py` | 专家确认规则字典条目和适用范围 | 非评分防护、诊断证据与建议回归 |
| Word 模板 | `word-standard-v2` | 导出 Skill/模板版本 | 提供客户标准模板、必填栏目和视觉规范 | DOCX 完整性、LibreOffice/WPS 打开检查 |
| 模型资产 | 固定 vLLM 工程候选 | Compose、模型资产表、发布清单 | 完成专业质量、上下文、并发和容量 Go/No-Go | 同数据集 Provider 回归、模型 revision 冻结 |
| 账号与身份 | `demo_teacher`、`demo_admin` | 仓库外 env、`seed_demo.py` | 换成思政课平台 claims 与正式角色映射 | 登录、RBAC、跨用户/组织隔离、审计 |
| 演示访问 | Tailnet 根入口和 `:8443` | Tailscale Serve、仓库外 env | 确认 ACL/Grant 身份、演示日期和现场网络 | 未授权设备不可达、Virtus 人工黄金脚本 |

## 2.1 自助开发模式下的推进方式（2026-07-17 起）

客户与专家暂不参与期间（主计划 §0.5）：

- §2 表中"真实替换要求"列的外部动作整体冻结为补签清单，不阻塞工程开发；本表继续作为恢复外部参与后的唯一替换入口。
- 样板范围、Word 模板、Skill 目录和诊断维度沿用《阶段 1 工程冻结基线》，登记为内部代理决策。
- 专家金标由"内部金标 v0"先行：工程团队自研 120–160 例，建 `data_origin=synthetic` 专用数据集（建议 key `stage1-internal-gold`），用双评/第三人仲裁工具走完整流程并标定内部工程阈值；禁止改名、改来源或改审核状态冒充正式集。
- §3 替换顺序不变，在外部参与恢复后执行；届时内部金标继续只作工程回归。

## 3. 推荐替换顺序

1. 客户确认样板范围、成果类型和 Word 模板。
2. 导入真实授权资料，保留模拟资料但停用，不覆盖原始记录。
3. 创建新的 `customer_provided`/`expert_authored` 评测数据集版本。
4. 完成专家审核、仲裁和候选模型专业评测；模拟集继续只作工程回归。
5. 将通过门禁的同一镜像先部署 `luyun-int`，完成迁移、恢复、降级和 Virtus 黄金脚本。
6. 同镜像摘要晋级 `luyun-demo`；确认没有模拟资料进入正式演示后，才将 `CONTENT_MODE` 改为 `production`。

## 4. 当前工程基线结果

- 发布：`stage1-diagnostic-rules-20260719-r1`（双环境同一 API/Web 镜像；包含诊断规则字典 v2 与 MinIO 健康检查端口修复）。
- 迁移：`m2a3b4c5d678 (head)`。
- 双环境：API/Web 使用同一镜像摘要；PostgreSQL、MinIO、vLLM 端口、卷和 Secret 隔离。
- 模拟评测：`stage1-synthetic-g0` 64 例现为 64 `matched`（语义索引已真实激活）。注意：该集资料正文内嵌查询原文（查询泄漏），只作工程冒烟回归下限，不能测量检索质量；历史 43/64 已取证定位为门禁开发期旧语料下 Reranker 低分被阈值过滤所致。
- 内部金标：`stage1-internal-gold` 140 例（`internal_authored`，无泄漏）双环境 140 `matched`、0 `failed`、0 `error`；内部阈值见《内部阈值标定报告 v0》。该集为内部自研，不是专家金标。
- 已验证：六个 Skill 主链、显式 Memory、版本、Word 导出、真实 vLLM SSE、Reranker 停机显式降级（含 `semantic_index_missing` 降级）、引用段落/页码定位、资料有效期过滤、资料不足两级判定、诊断规则字典 v2 注册、双环境 MinIO 正确端口健康检查、应用旧镜像回滚与数据库 `k1 ↔ m2` 往返恢复。
- 金标批量导入、双评/第三人仲裁、占位案例防冻结和报告接口已在双环境用内部金标走通全流程。该工程工具与内部金标状态不代表真实专家金标已经到位。

## 5. 正式状态限制

在真实资料、专家金标、模型专业冻结、ACL/Grant 责任确认和 Virtus 人工验收完成前：

- 不得把模拟数据集改名或改状态冒充正式集；
- 不得将 `CONTENT_MODE` 改成 `production`；
- 不得标记阶段 1A、阶段 1B、G0 或 G1 整体完成；
- 不得把 64 例含泄漏集或内部金标的工程命中率解释为教学质量指标或专业验收结论。
