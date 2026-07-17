# 阶段 1 工程冻结基线

> 日期：2026-07-16
> 状态：工程侧 v1，可执行；专家、客户、资料授权和正式模型选型签字待完成
> 权威范围：产品范围、阶段与 G 门仍以《2026 鲁韵课程与教学论开发计划》为准

## 1. 结论

本文件冻结阶段 1 当前可由工程团队独立确定的输入，作为单一纵向样板的开发、测试和演示基线。它不代表 G0 或 G1 已通过，也不替代专家对教学结构、诊断规则和案例的审核。

工程基线固定为：

- 学段：高中。
- 课型：议题式教学。
- 样板主题：家国情怀与青年责任。
- 核心议题默认值：青年如何把个人理想融入国家发展。
- 闭环：依据对齐卡 → 目标—证据—任务蓝图 → 课时分块 → 形成性诊断 → `word-standard-v2` 结构化 Word 导出；界面只在前置成果存在时解锁下一步。
- 诊断原则：只给证据、状态和修改建议，不给教师/学生总分、等级、排名或绩效结论。
- Memory 原则：只注入用户在本次运行中显式勾选的对象；清除后不可用于新 SkillRun。
- 模型与检索原则：固定运行时和模型 revision 仅作为工程候选；专业选型仍待专家金标评测。
- 数据原则：缺少真实资料时只允许使用显式 `synthetic` 数据；模拟集不能审核成正式专家集，替换规则见《阶段 1 模拟信息替换台账》。

## 2. 产品 Skills 目录 v1（工程冻结部分）

| skill_id | 当前版本 | 输入要点 | 输出要点 | 失败/降级策略 | 成熟度 |
| --- | --- | --- | --- | --- | --- |
| `skill.retrieve_basis` | 1.1.0 | project、查询、limit | 资料不足、检索模式、引用 | 无可靠依据时明确资料不足 | baseline |
| `skill.alignment_card` | 1.0.0 | 主题、核心议题、依据查询 | 目标、依据摘要、引用、警告 | 资料不足时只产出待补依据草案 | vertical_sample |
| `skill.design_blueprint` | 1.0.0 | project、课时分钟数 | 目标、证据、学习任务 | 缺少对齐卡时拒绝执行 | vertical_sample |
| `skill.generate_section` | 1.0.0 | project、分块名称、教师指导 | 导入、活动、评价证据、教师提示 | 缺少蓝图时拒绝执行 | vertical_sample |
| `skill.diagnose_artifact` | 1.0.0 | project | 结论、诊断项、阻断问题 | 仅返回需关注项，不产生总分 | vertical_sample |
| `skill.export_artifact` | 1.0.0 | project、模板名 | 导出件、下载地址、模板/版本 | 未完成诊断时拒绝导出 | vertical_sample |

所有 Skill：

- 统一经过 `run_skill` 做权限、Schema、status、输入哈希和运行留痕。
- Memory 只通过 `memory_refs` 注入，并记录快照审计。
- 输出写入 `SkillRun.output_payload`；样板中间成果写入不可变 `ProjectVersion`。
- 配额类和超时字段进入 SkillDefinition；阶段 1 当前使用 `standard` 配额类，正式额度需客户确认。
- Agent 不得绕过以上 Skill 注册表。

## 3. Memory 边界 v1（工程冻结部分）

允许：

- 账户偏好：学段、课型、教材版本、导出模板。
- 命名班情：班额、设备条件、用户主动填写的教学关注点。
- 用户钉选的本人项目和模板。
- SkillRun 注入审计快照。

禁止：

- 从聊天历史静默推断长期偏好。
- 思想侧写、能力评级、绩效画像。
- 组织或管理员静默读取教师私有班情。
- 将原始 Memory 默认用于训练。
- 删除后继续解析旧引用。

界面约束：保存 Memory 不等于注入。用户必须在执行 Skill 前勾选“本次显式使用”；清除动作先展示偏好、班情和钉选项数量并要求确认不可撤销，历史审计仅用于追溯。

## 4. 教学结构与形成性诊断规则 v1

当前纵向样板只冻结三个可执行诊断维度：

| 维度 | 证据 | `aligned` 条件 | `needs_attention` 条件 |
| --- | --- | --- | --- |
| 依据可追溯 | 审核资料引用片段 | 至少一条可定位引用 | 无审核引用 |
| 目标—证据一致 | 蓝图中的目标和课堂证据 | 两者同时存在 | 目标或证据缺失 |
| 任务可实施 | 课时活动、时长、教师/学生活动 | 至少一个结构化活动 | 活动结构缺失 |

诊断输出只允许：`dimension`、`status`、`evidence`、`suggestion`。禁止任何总分、百分制、排名和教师能力结论。

## 5. 检索与模型工程决策

当前完整检索链为 PostgreSQL `pg_trgm` + pgvector 余弦候选召回，再经 vLLM Reranker 重排，模式名为 `hybrid_trgm_pgvector_reranker`。Embedding/Reranker 不可用时显式降级为 `hybrid_trgm_char_vector`；两条链均保留审核过滤和资料不足阈值。

工程候选冻结为 vLLM `0.18.0` 镜像摘要、`Qwen/Qwen2.5-0.5B-Instruct`、`BAAI/bge-small-zh-v1.5`（512 维）和 `BAAI/bge-reranker-v2-m3` 的精确 Hugging Face revision。知识索引记录模型、revision、维度、配置哈希和状态；新版本完整写入后才激活，失败版本不替换上一有效索引。

边界：以上是工程兼容性候选，不代表正式教学质量选型。生成模型继续通过逻辑模型名调用；`luyun-int` 当前固定使用 vLLM 生成主链，Ollama 只作明示备用；`luyun-demo` 正式候选仍须通过专家金标回归和 Go/No-Go。

## 5.1 可版本化工程评测

- 数据集按 `project + dataset_key + version_number` 递增；冻结后禁止修改，记录 canonical JSON 的 SHA256。
- 每次运行绑定数据集哈希与应用发布、vLLM 镜像、三个模型 revision、检索参数和 Skill 版本清单。
- 单案例只记录 expected document/资料不足是否命中、检索模式、延迟和错误；汇总为 matched/failed/error 技术计数。
- 当前框架不含专家金标，不设置专业通过阈值，也不输出教师/学生总分、等级或排名。
- 评测集记录 `data_origin`、外部审核状态/意见/审核人/时间；`synthetic` 审核状态固定为 `not_applicable`。

## 6. 版本、导出与追溯

- 每个样板步骤生成新的不可变 ProjectVersion。
- 版本内容携带 skill_run_id、skill_id、skill_version 和来源版本。
- 版本差异按结构化顶层章节输出，不对自然语言结果做误导性的质量判定。
- Word 导出件记录 project、user、SkillRun、ProjectVersion、模板版本、对象键和 SHA256；`word-standard-v2` 使用标题、列表和表格表达结构化成果，不输出内部字典文本。
- 下载端点按当前用户鉴权，不向前端暴露 MinIO 凭据或对象键。

## 7. 当前验收脚本

工程自动门禁：

```bash
make harness-full
```

纵向样板人工顺序：

1. 创建高中议题式项目。
2. 上传并审核资料。
3. 确认知识索引为 `active`，检索模式为 `hybrid_trgm_pgvector_reranker`。
4. 保存偏好或班情，并显式勾选本次使用项。
5. 运行对齐卡、蓝图、课时设计、形成性诊断。
6. 比较 v1 与最新版本，导出并打开 DOCX。
7. 创建工程评测数据集和案例，冻结后确认不可修改，执行并核对发布清单与逐案例结果。
8. 停止 Reranker，确认检索显式降级且不返回 5xx；恢复服务后确认健康。
9. 清除 Memory，确认旧引用不能用于新 SkillRun。
10. 分别以 `demo_teacher` 和 `demo_admin` 验证教师不可审核、管理员可审核；确认失败任务显示服务端错误原因。

## 7.1 模拟工程门禁记录（2026-07-17）

- `seed_demo` 幂等生成 8 份显式模拟资料、一个初始项目版本和 64 个冻结工程案例。
- 64 例语义检索工程回归结果为 43 `matched`、21 `failed`、0 `error`；该结果保留候选检索差距，不作为专业通过率。
- `luyun-int` 与 `luyun-demo` 使用 `stage1-synthetic-gate-20260717-r1` 同一 API/Web 镜像摘要；数据库、MinIO、模型端口、卷和 Secret 独立。
- `luyun-demo` 通过六 Skill 主链、显式 Memory、版本、`word-standard-v2`、真实 vLLM SSE 和 Reranker 停机降级验证。
- `luyun-int` 已验证回滚到 `stage1-browser-fixes-20260716-r1` 后健康，再恢复当前镜像；迁移已在独立测试库通过 `i9 → j0 → i9 → j0`。
- Base-Spark 本机已通过 Tailnet `:8443` HTTPS 验证；新增模拟数据和双环境界面仍待 Virtus 人工复核。

## 8. 仍需外部签字的 G0 输入

- 专家确认教学结构、三个诊断维度及后续规则字典。
- 客户确认样板主题、对外话术、试点人员和 G1 阈值。
- 资料版权、有效期、更新责任人和审核 SLA。
- 60–80 个 G0 种子案例审核；G1 扩展到 120–160 个。
- Embedding、Reranker、生成模型的专业冻结，以及长上下文/并发/容量 Go/No-Go。
- ACL/Grant、身份声明、合规、RTO/RPO、红队和事故流程责任人。

以上未签字前，结论保持：工程纵向样板可运行；阶段 1A、阶段 1B、G0、G1 均不得标记为整体完成。
