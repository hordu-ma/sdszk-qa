# 阶段 1 模拟信息替换台账

> 日期：2026-07-17
> 状态：工程可执行；真实资料、专家审核和客户签字待补
> 结论：当前 `luyun-int`/`luyun-demo` 用模拟信息验证工程链路，不构成 G0/G1 专业验收。

## 1. 识别与门禁

- 运行环境通过 `CONTENT_MODE=synthetic` 和 `CONTENT_DISCLAIMER` 向 API/工作台显示模拟状态。
- 模拟项目标题以 `[模拟]` 开头，资料文件名使用 `synthetic-stage1-*`，资料正文包含模拟免责声明。
- 评测数据集 `data_origin` 只允许 `synthetic`、`customer_provided`、`expert_authored`。
- `synthetic` 数据集的 `review_status` 固定为 `not_applicable`；审核 API 拒绝将其标记为 `approved`。
- `customer_provided`/`expert_authored` 新数据集初始为 `pending`，只能由 `reviewer`/`admin` 留下审核意见后变更状态。

## 2. 当前模拟项与替换入口

| 模拟项 | 当前内容 | 代码/数据入口 | 真实替换要求 | 替换后验证 |
| --- | --- | --- | --- | --- |
| 样板范围 | 高中、议题式、家国情怀与青年责任 | `seed_demo.py`、工程冻结基线 | 客户确认学段、课型、主题与成果类型 | 四类任务主链、版本差异、Word 导出 |
| 可信资料 | 8 份自造 Markdown 资料 | `seed_demo.py`、MinIO `synthetic/stage1/` | 导入已授权原件，登记版本、有效期、责任人；不得覆盖模拟原件 | 解析、审核、引用定位、资料不足 |
| 工程案例 | 8 个主题 × 8 个问题，共 64 例 | `stage1-synthetic-g0` v1 | 新建 `customer_provided` 或 `expert_authored` 数据集版本；禁止修改冻结集 | 冻结哈希、逐案例结果、发布清单 |
| 专家金标 | 当前没有 | 评测案例 `case_metadata` 和预期文档 | 专家填写预期依据、关键错误和仲裁结论 | 双专家一致性、专业阈值、一票否决项 |
| 教学结构/诊断 | 三个工程诊断维度 | 工程冻结基线、Skill 输出 Schema | 专家确认规则字典和适用范围 | 非评分防护、诊断证据与建议回归 |
| Word 模板 | `word-standard-v2` | 导出 Skill/模板版本 | 提供客户标准模板、必填栏目和视觉规范 | DOCX 完整性、LibreOffice/WPS 打开检查 |
| 模型资产 | 固定 vLLM 工程候选 | Compose、模型资产表、发布清单 | 完成专业质量、上下文、并发和容量 Go/No-Go | 同数据集 Provider 回归、模型 revision 冻结 |
| 账号与身份 | `demo_teacher`、`demo_admin` | 仓库外 env、`seed_demo.py` | 换成思政课平台 claims 与正式角色映射 | 登录、RBAC、跨用户/组织隔离、审计 |
| 演示访问 | Tailnet 根入口和 `:8443` | Tailscale Serve、仓库外 env | 确认 ACL/Grant 身份、演示日期和现场网络 | 未授权设备不可达、Virtus 人工黄金脚本 |

## 3. 推荐替换顺序

1. 客户确认样板范围、成果类型和 Word 模板。
2. 导入真实授权资料，保留模拟资料但停用，不覆盖原始记录。
3. 创建新的 `customer_provided`/`expert_authored` 评测数据集版本。
4. 完成专家审核、仲裁和候选模型专业评测；模拟集继续只作工程回归。
5. 将通过门禁的同一镜像先部署 `luyun-int`，完成迁移、恢复、降级和 Virtus 黄金脚本。
6. 同镜像摘要晋级 `luyun-demo`；确认没有模拟资料进入正式演示后，才将 `CONTENT_MODE` 改为 `production`。

## 4. 当前工程基线结果

- 发布：`stage1-synthetic-gate-20260717-r1`。
- 迁移：`j0e1f2a3b456 (head)`。
- 双环境：API/Web 使用同一镜像摘要；PostgreSQL、MinIO、vLLM 端口、卷和 Secret 隔离。
- 模拟评测：64 例，43 `matched`、21 `failed`、0 `error`。该结果仅用于暴露工程候选检索差距，不设置专业通过阈值。
- 已验证：六个 Skill 主链、显式 Memory、版本、Word 导出、真实 vLLM SSE、Reranker 停机降级、应用旧镜像回滚与恢复。

## 5. 正式状态限制

在真实资料、专家金标、模型专业冻结、ACL/Grant 责任确认和 Virtus 人工验收完成前：

- 不得把模拟数据集改名或改状态冒充正式集；
- 不得将 `CONTENT_MODE` 改成 `production`；
- 不得标记阶段 1A、阶段 1B、G0 或 G1 整体完成；
- 不得把 43/64 工程命中率解释为教学质量指标。
