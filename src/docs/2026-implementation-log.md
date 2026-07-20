# 实施记录附录（阶段 1–2）

> - 用途：汇总《2026 鲁韵课程与教学论开发计划》历次「实施记录 / 部署验收记录 / 收口记录 / 策略记录」原文，按时间排序，作为审计与回溯依据。
> - 约定：本文条目自主计划 v1.4 起从主计划正文搬入，文字保持搬移时原样，不改写、不新增结论；主计划只保留现状摘要。
> - 相关文档：结构化收口证据另见《阶段 1 M1-int 内部门收口记录》《WP2.1 / WP2.2 / WP2.3 / WP2.4 收口记录》；模拟项替换见《阶段 1 模拟信息替换台账》。

## 1. 阶段 0 数据卫生（原主计划 §6.1）

实施记录（2026-07-16）：三个错位文件已按内容重命名为 `case_002_rule_of_law.json`、`case_003_labor_education.json`、`case_005_national_security.json`（案例内容与标题未改动，导入按标题匹配不受影响）；已新增 `src/scripts/validate_cases.py` 一致性校验脚本（`make validate-cases`）并接入单元测试回归。`reference_answer.primary` 的量规化改造仍按主计划 §6.1 要求在阶段 0 完成。

## 2. 投标演示轨道 D0–D3 实施状态（原主计划 §7.7）

实施状态（2026-07-17）：D0 已形成固定版 vLLM 三类工程候选的 arm64/GB10 兼容性与模型资产登记基线，但正式模型专业选型、长上下文/并发/容量对比和 Go/No-Go 未完成；D1 已完成 `luyun-int`/`luyun-demo` 独立端口、卷、Secret 和同镜像模拟工程晋级，备份、迁移往返、重启持久化及应用回滚/恢复均通过；D2 的 Serve/MagicDNS、根入口与 `:8443` 双环境 HTTPS、真实 vLLM SSE 和完整阶段 1 模拟脚本已从 Base-Spark 验证，新增功能的 Virtus 人工界面及 ACL/Grant 验收未完成；D3 已完成一次 Reranker 故障降级和恢复工程演练，正式监控、并发/长连接目标及两次完整彩排未完成。

## 3. 阶段 1 实施状态快照（原主计划 §10.1）

实施状态（2026-07-17）：**阶段 1 工程样板进行中。** 第 1–9 步已有单一高中议题式技术闭环：Teaching Project/Version、服务层、ModelClient/Provider Adapter、应用内资料任务、审核门禁、语义混合检索与显式降级、六个样板 Skills、显式 Memory、结构化生成、非评分诊断、版本差异、结构化 Word 导出和可版本化工程评测。第 10 步已完成 64 个显式模拟案例回归、正式案例批量导入/双评/第三人仲裁工程门禁和 `luyun-int → luyun-demo` 同镜像模拟工程晋级；来源、占位案例和复核门禁阻止模拟信息冒充专家金标。固定版 vLLM 三类工程候选和模型/索引资产已登记，教师/管理员测试身份已分离，工作台显式提示模拟状态。真实资料替换、120–160 个真实专家金标、专业模型冻结、Virtus 新增功能人工验收及 G0/G1 外部签字仍未完成，因此不得标记 1A、1B、阶段 1、G0 或 G1 整体完成。

## 4. 阶段 1 第一增量（2026-07-16，§5.4.1 第 5–7 步）

实施记录（2026-07-16）：按 §5.4.1 第 5–7 步交付以下增量：
（a）`retrieve_basis` 检索从应用内词项匹配升级为 PostgreSQL `pg_trgm` 库内词法检索（相似度排序、短查询子串兜底、资料不足阈值 `RETRIEVE_MIN_RELEVANCE`）；向量 + Reranker 混合检索仍待 D0 模型选型后接入。
（b）产品 Skills 运行时最小集：SkillDefinition 注册表（含 §2.5.1 契约字段与成熟度登记）、统一 `run_skill` 执行入口（权限、输入输出 Schema 校验、input_hash、错误码、运行留痕）、数据库 status 停用开关；该增量当时仅注册 `skill.retrieve_basis` v1.1.0（基线成熟度），后续工程样板 Skill 见下方第二增量记录，均不代替专家签字冻结正式契约。
（c）核心用户 Memory 最小集：UserPreference、ClassContextProfile、MemoryInjectionAudit，显式 `memory_refs` 注入（含归属校验与快照审计）、一键清除、个人记忆清单导出；清除后引用不可再注入新 SkillRun（已回归验证）。注入确认 UX、配额/降级策略配置化执行仍未完成。
上述增量不改变“1A、阶段 1、G1 未完成”的结论。

部署验收记录（2026-07-16）：`luyun-int` 已切换至 `stage1a-20260716-7f9e9b2`，数据库为 `f7b8c9d0e123 (head)`。已通过登录/Skill 清单、Memory 写入—导出—清除、资料解析任务、审核、引用检索、应用重启持久化和真实 Ollama SSE 验收；Alembic 已通过 up/down/up，旧镜像回滚与新镜像恢复均成功。Tailscale Serve 已恢复 HTTPS 映射。

## 5. 阶段 1 第二增量（2026-07-16，纵向样板）

工程实施记录（2026-07-16，第二增量）：

（a）按 §5.4.1 第 8–9 步实现高中议题式纵向样板，注册 `alignment_card`、`design_blueprint`、`generate_section`、`diagnose_artifact`、`export_artifact`；与 `retrieve_basis` 共同覆盖“查依据—备课—诊断—导出”。中间成果逐步写入不可变 ProjectVersion，版本差异按结构化章节展示。

（b）形成性诊断只输出 `aligned/needs_attention`、证据和建议；API、OpenAPI 与数据库模型继续由无评分/排名测试守护。Word 导出件关联项目、用户、SkillRun、ProjectVersion、模板版本和 SHA256，并经鉴权下载。

（c）Memory 增加本人项目/模板钉选和桌面端显式勾选确认；清除覆盖偏好、班情和钉选，清除后的旧引用仍不得注入新 SkillRun。

（d）检索升级为 `pg_trgm` 召回 + 字符 n-gram 向量余弦重排，模式为 `hybrid_trgm_char_vector`。该实现继续作为无需外部模型的可回归降级基线；第三增量在其上接入工程候选语义 Embedding/Reranker。

（e）工程侧可确定的样板、Skills、Memory、诊断和降级边界已写入《阶段 1 工程冻结基线》。专家、客户、资料授权、模型资产、评测阈值和合规责任仍须外部签字，工程文档不得代签。

部署验收记录（2026-07-16，第二增量）：`luyun-int` 当前为 `stage1-sample-20260716-r2`，数据库为 `h8c9d0e1f234 (head)`，发布前 PostgreSQL/MinIO 备份为 `/home/pgx/backups/luyun-sizheng/20260716-121140/`。已通过六个 Skill、显式 Memory、完整纵向样板、版本差异和鉴权 Word 下载的 Tailnet HTTPS API 验收；真实 Ollama SSE 返回 `[DONE]`，API 重启后消息持久。Alembic 已通过 `f7 → h8 → f7 → h8`；`r1` 功能镜像已回滚至 `stage1a-20260716-7f9e9b2` 并恢复，迁移一致性修正后重建部署为 `r2`。用户已确认此前 Virtus 人工浏览器验收完成；本次新增纵向样板界面仍不得仅凭服务器侧 HTTPS API 验收表述为跨机人工界面验收。

## 6. 阶段 1 第三增量（2026-07-16，vLLM 固定与语义 RAG）

工程实施与部署验收记录（2026-07-16，第三增量）：

（a）固定 `vllm/vllm-openai:v0.18.0` 镜像摘要，生成、Embedding、Reranker 均固定 Hugging Face revision 和 served name；模型资产由 API 启动幂等登记，评测运行绑定应用、vLLM、模型、检索和 Skill 发布清单。上述模型均为工程候选。

（b）RAG 接入 `pgvector vector(512)` 与 HNSW，形成 `pg_trgm + pgvector + Reranker` 主路径；知识索引按项目版本化、配置哈希并原子激活，失败版本保留原因且不覆盖 active。Provider 不可用时显式回落 `hybrid_trgm_char_vector`，不把降级伪装成语义成功。

（c）评测框架支持 dataset key 自动递增版本、冻结内容哈希、冻结后不可变、发布清单绑定、逐案例 `matched/failed/error` 技术结果；当前只运行工程 fixture，不作为专业质量评分或发布签字。

（d）`luyun-int` 已部署 `stage1-rag-eval-20260716-r1`，数据库为 `i9d0e1f2a345 (head)`，发布前备份为 `/home/pgx/backups/luyun-sizheng/20260716-130000-rag-eval/`。迁移通过 `h8 → i9 → h8 → i9`；固定 vLLM 的 Chat、结构化 JSON、SSE、Embedding、Reranker 与重启通过；HTTPS 业务链完成语义索引、检索、冻结评测、结果持久化和模型资产验证；Reranker 停机时降级无 5xx；应用回滚至 `stage1a-20260716-7f9e9b2` 并恢复当前镜像成功。

## 7. 阶段 1 第四增量（2026-07-16，vLLM 主链与角色拆分）

工程实施与部署验收记录（2026-07-16，第四增量）：

（a）`luyun-int` 默认业务 Provider 从 Ollama 过渡链切换为固定 vLLM 生成服务 `teaching-chat-engineering`，仍通过逻辑模型名和 Provider Adapter 调用；Ollama 只保留为人工显式切换的备用路径。

（b）种子身份拆分为 `demo_teacher`（教师）和 `demo_admin`（管理员）。教师可创建项目、上传资料和运行教学闭环但不可审核，管理员可跨用户审核；工作台按角色隐藏审核操作。

（c）Word 模板升级为 `word-standard-v2`，使用 A4 页边距、标题、列表和表格表达对齐卡、蓝图、课堂活动与诊断，不再输出内部字典文本。工作台按最新版本的前置成果逐步解锁；Memory 清除显示对象数量并二次确认；失败任务直接显示服务端错误原因。

（d）`luyun-int` 已部署 `stage1-browser-fixes-20260716-r1`，数据库仍为 `i9d0e1f2a345 (head)`，发布前 PostgreSQL/MinIO 备份为 `/home/pgx/backups/luyun-sizheng/20260716-140000-browser-fixes/`，本轮无新迁移。Tailnet HTTPS API 验证双账号 RBAC、管理员审核、教师 403、vLLM 状态和真实 SSE；真实 Chromium 自动回归步骤门禁、Memory 确认、教师端权限、语义 RAG、失败原因和 Word 下载。导出件经 ZIP 完整性和 LibreOffice 渲染检查。该自动回归不替代新增功能的 Virtus 跨设备人工复核，也不改变阶段/G 门状态。

## 8. 阶段 1 第五增量（2026-07-17，来源门禁与双环境）

工程实施与部署验收记录（2026-07-17，第五增量）：

（a）评测数据集新增 `synthetic/customer_provided/expert_authored` 来源、外部审核状态、意见、审核人与时间；模拟集审核请求返回冲突，不能改成正式通过。`CONTENT_MODE`/免责声明通过 API 和工作台持续显示，替换路径记录在《阶段 1 模拟信息替换台账》。

（b）`seed_demo` 幂等生成 8 份模拟资料、初始 ProjectVersion 和 64 个冻结案例；工程回归为 43 `matched`、21 `failed`、0 `error`。该结果仅暴露工程候选检索差距，不设置专业阈值，不替代 60–80 个 G0 专家案例或 120–160 个 G1 金标集。

（c）Base-Spark Compose 端口全部参数化；`luyun-int`/`luyun-demo` 使用独立 PostgreSQL、MinIO、vLLM 端口、卷和仓库外 Secret。两套 API/Web 均使用 `stage1-synthetic-gate-20260717-r1` 同一镜像摘要，数据库均为 `j0e1f2a3b456 (head)`；Demo 通过 Tailnet `:8443`、六 Skill、Memory、Word、真实 vLLM SSE 和 Reranker 停机降级验证。

（d）发布前备份位于 `/home/pgx/backups/luyun-sizheng/20260717-stage1-synthetic-gate-predeploy/`。迁移在独立测试库通过 `i9 → j0 → i9 → j0`；`luyun-int` 回滚至 `stage1-browser-fixes-20260716-r1` 后健康并恢复当前镜像。新增模拟界面与 `:8443` 演示仍待 Virtus 人工复核，不改变阶段/G 门状态。

## 9. 阶段 1 第六增量（2026-07-17，金标治理）

工程实施记录（2026-07-17，第六增量）：

（a）评测数据集新增一次 1–200 例批量导入、案例列表和审核员正式集复核队列；正式来源案例记录 `pending/single_review/consensus/disputed/arbitrated` 金标状态。审核员可发现跨所有者待复核集并提交复核，只有数据集所有者可导入、冻结和运行；工作台可查看金标/最近运行汇总。

（b）两位不同 `reviewer/admin` 独立提交预期资料、资料不足结论、一票否决标签和复核依据；完全一致时形成共识，不一致时进入分歧，且只能由未参与前两次复核的第三人提交仲裁。复核记录独立留痕，不覆盖专家原始意见。

（c）`synthetic` 案例拒绝进入专家复核；`case_metadata.placeholder=true` 的占位案例即使完成复核也阻止正式冻结。非模拟数据集只有在来源审核通过、无占位案例且逐例达到共识或仲裁后才能冻结，继续禁止用工程 fixture 冒充真实金标。

（d）应用镜像 `stage1-gold-review-20260717-r1` 和迁移 `k1f2a3b4c567` 已部署到 `luyun-int`，完成 `j0 → k1 → j0 → k1` Schema 往返、上一应用镜像回滚和当前镜像恢复后，以同一 API/Web 镜像摘要晋级 `luyun-demo`。双环境通过健康检查、Tailnet HTTPS、真实 vLLM SSE、双评共识、分歧与独立仲裁、冻结运行、占位案例防冻结和 Chromium 登录页渲染验证；发布前备份位于 `/home/pgx/backups/luyun-sizheng/20260717-stage1-gold-review-predeploy/`。临时验证数据已清理；该部署不等于获得真实专家金标，不改变阶段/G 门状态。

## 10. 自助开发模式策略记录（2026-07-17）

策略记录（2026-07-17，自助开发模式）：按 §0.5 进入自助开发模式。阶段 1 剩余外部依赖项（真实授权资料、120–160 个真实专家金标、模型专业冻结、Virtus 客户人工验收、G0/G1 外部签字）整体冻结为补签清单，不再阻塞工程开发。样板范围（高中议题式）、Word 模板（`word-standard-v2`）、六个 Skill 目录和三个诊断维度沿用《阶段 1 工程冻结基线》，作为首批内部代理决策基线。工程按 §0.5 优先级推进：检索质量调优 → 内部金标 v0 → 引用精细化 → 诊断规则字典 v2 → 工作台体验；目标为通过 M1-int 内部验收。本记录不改变“阶段 1A、1B、G0、G1 未完成”的结论。

## 11. 阶段 1 第七增量（2026-07-17，自助优先级 1–3）

工程实施与部署验收记录（2026-07-17，第七增量，自助开发 §0.5 优先级 1–3）：

（a）检索质量调优：从 gold-review 部署前备份取证复现历史 43/64——该运行发生在门禁增量开发期（资料正文尚无检索问题清单），21 个 failed 全部是 Reranker 对意译措辞打分低于 0.15 阈值导致的空结果；最终版语料因正文内嵌查询原文（查询泄漏）使 64 例集失去测量意义。修复两个真实缺陷：项目缺当前模型 revision 语义向量时显式降级（`semantic_index_missing`，不再以语义模式返回纯词法结果）；`seed_demo` 现在为模拟语料构建并激活语义索引。

（b）内部金标 v0：新增 `internal_authored` 数据来源（可走双评/仲裁与来源审核全流程，永远明示非专家数据、禁止冒充正式来源）；`seed_internal_gold` 建成 `stage1-internal-gold` v1（12 份无泄漏多段落自研资料、140 例=120 检索+20 资料不足、双评 132 共识+8 预置分歧经第三人仲裁、来源审核后冻结）。内部工程阈值与 M1-int 检索质量门写入《内部阈值标定报告 v0》。

（c）引用精细化：分块记录段落区间与 PDF 页码（跨页强制切块），引用输出结构化定位；资料新增 `valid_from/valid_until`，过期或未生效资料不进入检索；资料不足策略升级为“无候选 `no_candidates` 或 top1 相关度 < 0.18 `low_relevance`”，低置信候选界面明示为参考；`skill.retrieve_basis` 升级 v1.2.0，评测运行与 Skill 共用同一策略函数；迁移 `m2a3b4c5d678`。

（d）部署验收：`luyun-int` 部署 `stage1-selfserve-rag-20260717-r1`，迁移通过独立测试库 `k1 → m2 → k1 → m2` 往返；双数据集在真实语义链下 64/64 与 140/140；Reranker 停机显式降级无 5xx；回滚至上一镜像 + 数据库降级后健康，恢复当前版本与部署后快照成功。以同一 API/Web 镜像摘要晋级 `luyun-demo`，双环境通过 Tailnet HTTPS、真实 vLLM SSE、引用定位与资料不足判定验证。发布前备份 `/home/pgx/backups/luyun-sizheng/20260717-stage1-selfserve-rag-predeploy/`。内部金标与内部阈值均为 `internal_authored` 工程产物，不代表专家金标；本记录不改变阶段/G 门状态。

## 12. 阶段 1 第八增量（2026-07-17/19，诊断规则字典 v2）

工程实施记录（2026-07-17，第八增量，自助开发 §0.5 优先级 4：诊断规则字典 v2 内部版）：把纵向样板三个工程诊断维度（依据可追溯、目标—证据一致、任务可实施）从 `diagnose_artifact_handler` 内联逻辑抽离为可配置规则字典，入口 `src/apps/api/services/diagnostic_rules.py`。每条 `DiagnosticRule` 声明 `rule_id`、维度、依赖样板小节、达标判定、可观察证据与改进建议，并可标记是否阻断；新增维度只需 `register_diagnostic_rule` 注册，诊断编排不再改动。规则字典严守 §16.1 非评分约束：只产 `aligned/needs_attention`，注册入口对评分/排名类词元（与 `tests/test_no_scoring_paths.py` 同口径）与重复注册做防护拦截。新增 `tests/test_diagnostic_rules.py` 覆盖默认三维判定、blocking 汇总、可扩展注册与防护拦截；`diagnose_artifact_handler` 输出 Schema 不变、行为等价（blocking 仍按维度名汇总）；ruff + basedpyright + 43 例非集成 pytest 全绿。三维内容与适用范围仍为待专家确认的补签项（《阶段 1 模拟信息替换台账》§2 教学结构/诊断行），本记录不改变阶段 1A/1B、G0、G1 未完成的结论。下一步转入 §0.5 优先级 5（工作台体验：专业编辑、可用性走查、无障碍）。

部署验收记录（2026-07-19，第八增量）：修复 Base-Spark MinIO 健康检查仍探测默认 `localhost:9000`、未跟随 `MINIO_PORT` 的配置缺陷；新检查按两套环境实际端口和容器内凭据执行，不把 Secret 写入仓库。`luyun-int` 与 `luyun-demo` 已部署同一 API/Web 镜像 `stage1-diagnostic-rules-20260719-r1`，镜像 ID 分别为 `b689cc492440...` / `48a805189120...`，数据库均保持 `m2a3b4c5d678 (head)`。双环境 PostgreSQL、MinIO、API、Web 和三类 vLLM 均健康；诊断规则注册、教师登录/身份、真实 vLLM SSE `data:`/`[DONE]`、Tailnet 两个 HTTPS `/healthz` 通过，临时会话及审计数据已清理。发布前备份位于 `/home/pgx/backups/luyun-sizheng/20260719-stage1-diagnostic-rules-predeploy/`。该发布只完成内部工程增量，不改变阶段 1A/1B、G0、G1 未完成的结论；下一步仍为 §0.5 优先级 5。

## 13. 阶段 1 第九增量（2026-07-19，工作台体验内部版）

工程与部署验收记录（2026-07-19，第九增量，自助开发 §0.5 优先级 5：工作台体验内部版）：在既有纵向样板和版本 API 上增加结构化专业编辑，覆盖课程依据与目标、目标—证据—任务蓝图、课时活动和教师提示；保存生成不可变新 `ProjectVersion`，保留来源版本并写入 `teacher_edit` 追踪。编辑后主动移除旧诊断、锁定流水线和导出，要求重新形成性诊断；保存后自动展示“修改前/修改后”结构化差异。可用性与基础无障碍改动包括未保存切换/离开保护、跳到主要内容、显式表单标签、键盘焦点和状态播报。`make harness-quick` 通过 ruff、basedpyright、43 例非集成测试和前端构建，工作台集成测试 5/5 通过；真实 Chromium 验证编辑、版本、诊断失效和差异闭环。`luyun-int` 已部署 `stage1-workbench-ux-20260719-r1`，API/Web 镜像 ID 为 `a74d09eff3f3...` / `77a2b532290e...`，数据库保持 `m2a3b4c5d678 (head)`，7 个容器、Tailnet HTTPS 和 Virtus 手动验证通过，临时数据已清理；发布前备份位于 `/home/pgx/backups/luyun-sizheng/20260719-stage1-workbench-ux-predeploy/`。`luyun-demo` 暂不晋级，继续保留 `stage1-diagnostic-rules-20260719-r1`。本记录完成优先级 5 内部工程增量，但真实教师可用性研究、客户/专家补签及 G0/G1 仍未完成。

## 14. M1-int 收口（2026-07-19，原主计划 §10.4）

M1-int 收口记录（2026-07-19）：自助开发优先级 1–5 的内部代理产物、140 例内部金标 v0、内部阈值、专业编辑走查、无评分防护和运行态证据已闭合，M1-int 内部门结论为**通过**，允许进入阶段 2 内部工程。`stage1-workbench-ux-20260719-r1` 已以相同 API/Web 镜像 ID `a74d09eff3f3...` / `77a2b532290e...` 从 `luyun-int` 晋级 `luyun-demo`；Demo 数据库保持 `m2a3b4c5d678 (head)`，Tailnet `:8443`、教师登录、vLLM 状态和页面渲染通过。实际回滚至 `stage1-diagnostic-rules-20260719-r1` 后健康，再恢复当前镜像；发布前备份为 `/home/pgx/backups/luyun-sizheng/20260719-m1-int-workbench-promotion/`。详细证据见《阶段 1 M1-int 内部门收口记录》。真实专家金标、客户/专家签字及 G0/G1 仍未完成。

## 15. WP2.1 专业输入与冲突检查（2026-07-19）

实施记录（2026-07-19，阶段 2 第一纵向增量，WP2.1 内部版）：新增 `skill.confirm_professional_input` v1.0.0，分步确认主题、核心议题、课程依据、班情、课型、计划课时、实际可用时间、教师意图和资源条件。Skill 只使用用户显式传入的 `memory_refs` 并保留注入快照；确定性规则阻断项目/本次课型不一致、计划时间超过可用时间，以及“数字化活动但设备或网络明确不可用”的冲突。空白课程依据、班情或资源只以“假设/待确认”列出，未经用户勾选确认不得进入对齐卡。结果写入不可变 `ProjectVersion`；上游输入变化会在新版本中移除旧对齐卡、蓝图、课时设计和诊断，原版本不变。前后端均阻止未解决状态绕过进入 `alignment_card`。

部署验证（2026-07-19）：`luyun-int` 部署 `stage2-professional-input-20260719-r1`，API/Web 镜像 ID 为 `d93ad5790121...` / `196247bc6a76...`，数据库仍为 `m2a3b4c5d678 (head)`，本轮无 Schema 变化。47 例非集成测试、5 例工作台集成测试、真实 API 纵向冒烟和 Chromium 10 项交互断言通过；Memory 追踪、冲突阻断、假设确认、版本失效和解锁对齐卡均已验证，临时数据已清理。应用回滚至 `stage1-workbench-ux-20260719-r1` 后健康并恢复当前镜像；发布前备份为 `/home/pgx/backups/luyun-sizheng/20260719-stage2-professional-input-predeploy/`。`luyun-demo` 保持 M1-int 的 Stage 1 稳定镜像；该记录不代表 WP2.1 全部完成、阶段 2 完成或 G2 通过。

收口记录（2026-07-19，WP2.1 内部工程完成）：`skill.confirm_professional_input` 升级至 v1.1.0，并以 `stage2-input-conflict-v2` 标记规则集。专业输入增加依据检索问题、教学目标、活动形式和成果用途；教师可把本次班情显式保存为班情档案，把通用专业输入显式保存为常用模板，载入后仍可逐字段覆盖，未点击保存时不写入 Memory。冲突检查改为有序、可注册的确定性规则字典，覆盖课型、时间、数字资源、目标—活动、资源—用途和协作条件，注册层禁止评分/排名类标识符。已确认专业输入版本成为后续 `alignment_card` 的服务端单一事实源；即使客户端传入不同主题、核心议题或检索问题，执行与审计仍使用已确认版本。由此 WP2.1 的内部工程范围收口，可继续 WP2.2；真实教师可用性确认、客户/专家补签、阶段 2 整体和 G2 均未完成。

收口部署验证（2026-07-19）：`luyun-int` 部署 `stage2-wp21-closure-20260719-r1`，API/Web 镜像 ID 为 `d74520905434...` / `38db8467c589...`，数据库保持 `m2a3b4c5d678 (head)`，无 Schema 变化。ruff、basedpyright、51 例非集成测试、6 例 PostgreSQL 17 独立测试库集成测试和前端生产构建通过；真实 API 冒烟覆盖三类新增冲突同时命中、冲突解除、Memory 写入和对齐卡事实源防篡改，Chromium 覆盖班情保存、模板保存/显示/载入及对齐卡入口。临时项目、班情和模板已清理。应用实际回滚至 `stage2-professional-input-20260719-r1` 后健康并恢复当前镜像；发布前 PostgreSQL 归档和 env 快照位于 `/home/pgx/backups/luyun-sizheng/20260719-stage2-wp21-closure-predeploy/`，归档 SHA256 为 `3ae04d25650601db967b37e6bef01565bc1136d7524643f80dc6295106281aa1`。`luyun-demo` 继续保持 `stage1-workbench-ux-20260719-r1`。

## 16. WP2.2 结构化生成工作台（2026-07-19）

收口记录（2026-07-19，WP2.2 内部工程完成）：`skill.generate_section` 升级至 v1.1.0，规则集标记为 `stage2-structured-gen-v1`。当前纵向样板在既有对齐卡—蓝图—分段生成链上补齐服务端章节/成果锁定、字段级局部重生成、来源版本冲突检查、字段级结构化差异和历史快照恢复；教师编辑、锁定、生成与恢复均创建不可变 `ProjectVersion`，历史恢复不覆盖或删除旧版本。局部重生成首批覆盖蓝图证据、任务证据、课堂导入、活动证据、评价证据汇总和教师提示；锁定字段在客户端禁用且服务端拒绝绕过。工作台可从当前蓝图和课时设计派生课堂任务单、非评分观察量规、板书设计、课件提纲和实践任务，未锁定的派生成果会在上游重生成后失效，锁定成果被显式保留。`word-standard-v2` 已汇总主教案、五类配套成果和非评分诊断。由此 WP2.2 内部工程范围收口，可继续 WP2.3；客户专属 Word 模板实物、真实教师长文档可用性验证和客户/专家补签仍属 §0.5 补签/替换清单，不得表述为外部验收。

收口部署验证（2026-07-19）：`luyun-int` 部署 `stage2-wp22-closure-20260719-r3`，API/Web 镜像 ID 为 `7b1b9cd91085...` / `9b0be24e6495...`，数据库保持 `m2a3b4c5d678 (head)`，无 Schema 变化。ruff、basedpyright、58 项完整测试和前端生产构建通过；真实 API 冒烟覆盖锁定绕过阻断、单字段变化、字段差异和历史恢复，Chromium 覆盖结构化编辑器、锁定、局部重生成、配套成果和恢复控件，Tailnet 返回 `skill.generate_section` v1.1.0。临时项目已清理。应用实际回滚至 `stage2-wp22-closure-20260719-r2` 后健康并恢复当前镜像；发布前 PostgreSQL 归档和 env 快照位于 `/home/pgx/backups/luyun-sizheng/20260719-stage2-wp22-closure-r3-predeploy/`，归档 SHA256 为 `49087e3088956e3f4476c88c1e89a9239d366ba6bba688f9f667dd6747c1b254`。`luyun-demo` 继续保持 `stage1-workbench-ux-20260719-r1`。

## 17. WP2.3 证据化诊断（2026-07-19）

收口记录（2026-07-19，WP2.3 内部工程完成）：纵向样板新增已有教案结构识别预览和教师校正确认，结构确认形成不可变版本；`skill.diagnose_artifact` 升级至 v1.1.0，规则集标记为 `stage2-evidence-diagnosis-v1`，每条诊断项稳定输出原文位置、规则依据、可见证据、影响、建议、示例改写和目标字段。教师可逐条采纳、忽略、编辑后采纳或申请专家复核，每次决定都形成新版本并记录为 `signal_level=L4`、`authorized_for_training=false`，不得直接进入训练。新增 `skill.apply_revision` v1.0.0，只应用明确采纳或编辑后采纳项，忽略/专家复核项不进入修改稿，并复用 WP2.2 字段锁定防护；应用后保留诊断历史、移除当前诊断并生成不可变二次修改稿。当前内部规则仍是高中议题式工程规则，不代表分学段量规获得专家确认；WP2.3 内部工程收口后转入 WP2.4。

收口部署验证（2026-07-19）：`luyun-int` 部署 `stage2-wp23-closure-20260719-r1`，API/Web 镜像 ID 为 `c03324da3765...` / `3d5e240f370f...`，数据库保持 `m2a3b4c5d678 (head)`，无 Schema 变化。ruff、basedpyright、59 项完整测试和前端生产构建通过；真实 API 冒烟覆盖结构确认、三维证据字段、逐条决定和仅采纳项修订，Web 根页、诊断面板资源、Chromium 渲染与 Tailnet 健康通过，临时项目已清理。发布时 npm registry 两次下载超时，Web 使用同一锁文件本地已验证的 `dist` 离线封装，并在镜像内修正静态文件读取权限；仓库标准 Dockerfile 未改。应用已实际回滚至 `stage2-wp22-closure-20260719-r3` 后健康并恢复当前镜像。发布前 PostgreSQL 归档和 env 快照位于 `/home/pgx/backups/luyun-sizheng/20260719-stage2-wp23-closure-r1-predeploy/`，归档 SHA256 为 `5efc2ca1de9fc3d1a2a2f7e7ebb40cf566c9ae6f146c412c485af97822114658`。`luyun-demo` 继续保持 `stage1-workbench-ux-20260719-r1`。

## 18. WP2.4 第一增量（2026-07-19，回归门禁内部版）

工程实施记录（2026-07-19，WP2.4 第一增量：变更触发回归对比与晋级阻断门禁）：新增 `services/evaluation_gate_service.py` 与 `GET /api/workbench/evaluation/datasets/{id}/regression-gate`，对冻结数据集生成回归门禁报告：

（a）发布清单变更检测：将最近一次 `EvaluationRun` 保存的 release_manifest 与当前运行时清单逐项对比（应用版本、vLLM 运行时、三类模型 revision、检索参数、全部 Skill 版本；模型列表按 `asset_type` 稳定键对比，避免顺序变化误报）。存在差异时 `verdict=stale`：最新运行不代表当前配置，阻断晋级并要求重新运行。

（b）内部阈值判定：整体匹配率 ≥ `EVAL_GATE_MIN_MATCH_RATE`（默认 0.95）、Top-1 文档命中率 ≥ `EVAL_GATE_MIN_TOP1_HIT_RATE`（默认 0.90，数据集无预期文档案例时不适用）、域外查询资料不足漏判 = 0、error 案例 = 0；阈值出自《内部阈值标定报告 v0》§5。全部通过才 `verdict=promotable`（`can_promote=true`），否则 `blocked`。报告 disclaimer 固定声明内部工程口径、不代表专家验收（主计划 §0.5 第 5 条）。

（c）运行间对比：与上一次已完成运行按 case_key 列出回退、修复和持续失败案例，并给出两次运行之间的清单差异；权限复用 `get_accessible_dataset`（所有者或 reviewer/admin）。工作台评测面板在数据集冻结后自动展示门禁结论、逐项阈值、清单变更与回退明细。

（d）验证：新增 `tests/test_evaluation_gate.py` 8 例纯函数测试（清单展平/差异/顺序不敏感、Top-1 与漏判指标、逐项阈值阻断、回退分类、免责声明口径），扩展工作台集成测试覆盖真实 API 双运行下的 promotable 结论与基线对比。ruff、basedpyright、60 例非集成测试、8 例集成测试（临时 pgvector PostgreSQL 17 容器）与前端生产构建全部通过。

部署验收记录（2026-07-19，WP2.4 第一增量）：`luyun-int` 部署 `stage2-wp24-gate-20260719-r1`，API/Web 镜像 ID 为 `8a26431c4877...` / `af4bc5e303db...`，数据库保持 `m2a3b4c5d678 (head)`，无 Schema 变化，只重建 API/Web。真实链路验证：门禁接口在历史运行上正确判定 `stale` 并列出全部 5 项清单变更（应用版本与 4 个 Skill 版本自 07-17 起的变化）；重跑 `stage1-internal-gold` 140/140、`stage1-synthetic-g0` 64/64 后两个数据集门禁均为 `promotable`（匹配率 1.0、Top-1 1.0、漏判 0、error 0），与上一运行零回退且清单差异正确归因；`/api/workbench/model-status` 报告 vLLM 未降级，真实 SSE 返回 25 个 `data:` 事件并以 `[DONE]` 结束，Tailnet HTTPS `/healthz` 通过，Web 静态包内含回归门禁面板。应用实际回滚至 `stage2-wp23-closure-20260719-r1` 后健康并恢复当前镜像。发布前 PostgreSQL 归档（357 TOC 条目，`pg_restore -l` 校验通过）与 env 快照位于 `/home/pgx/backups/luyun-sizheng/20260719-stage2-wp24-gate-r1-predeploy/`，归档 SHA256 为 `bd8d797f9c46a7bea90130358956ce1129dd8c97ced4ea0e6a5b6544e50feeb4`。临时冒烟会话与自定义主题已清理；门禁验证形成的两次评测运行作为审计产物保留。`luyun-demo` 继续保持 `stage1-workbench-ux-20260719-r1`。本轮浏览器侧仅验证静态资源与构建，未做 Virtus 跨设备人工复核。

本记录完成 WP2.4 第一增量（代码 + `luyun-int` 部署验收）；抽检队列与 L4 信号汇总为后续增量。不改变阶段 2、G2 未完成的结论。

## 19. WP2.4 第二增量与收口（2026-07-20，抽检队列 + L4 信号汇总）

工程实施记录（2026-07-20，WP2.4 第二增量）：新增抽检队列（`spot_check_items` / `spot_check_reviews`，迁移 `n3b4c5d6e789`，仅新增表）：审核员/管理员从最近完成的 SkillRun（默认 `skill.diagnose_artifact`）随机抽取未复核运行入队，每项固化抽检时刻发布清单快照与 `signal_level=L4`、`authorized_for_training=false` 声明；复核复用金标治理状态机（两位不同复核人独立提交，签名一致成共识，不一致进入分歧，仅未参与前两次复核的第三人可仲裁），结论词汇固定 `confirmed / needs_adjustment`，可附规则字典/量规修订反馈，复核记录独立留痕。新增 `GET /api/workbench/signals/l4-summary`：把 WP2.3 起的教师逐条决定按诊断规则字典维度聚合（教师限本人项目，全局仅审核角色），汇总固定声明不构成训练授权与教师评价。工作台新增「抽检复核与 L4 信号」面板。注册层与非评分防护测试继续拦截评分/排名标识符。验证：ruff、basedpyright、66 例非集成测试、9 例集成测试（独立 pgvector PostgreSQL 17，含 WP2.4 抽检闭环新用例）、前端生产构建通过；独立测试库迁移 `m2 → n3 → m2 → n3` 往返通过。

部署验收记录（2026-07-20，WP2.4 第二增量）：`luyun-int` 部署 `stage2-wp24-spotcheck-20260720-r1`，API/Web 镜像 ID 为 `3fe20bf742c9...` / `f94ec1381933...`，数据库升级至 `n3b4c5d6e789 (head)`。真实链路验证：教师纵向链（项目→版本→结构确认→诊断→三条 L4 决定）后抽样命中该诊断运行；双评分歧、重复提交 409、独立复核人仲裁 409、第三人仲裁形成 `arbitrated` 与 resolved 结论；教师访问抽检队列与全局汇总 403；项目级 L4 汇总按三维正确聚合，全局汇总可见；真实 vLLM SSE 返回 30 个 `data:` 事件并以 `[DONE]` 结束，`/api/workbench/model-status` 未降级；新 Web 静态包含抽检面板，本机与 Tailnet 两个 HTTPS `/healthz` 通过。应用实际回滚至 `stage2-wp24-gate-20260719-r1` 后健康（新表向后兼容，无数据库降级），恢复当前镜像后复验抽检接口。发布前 PostgreSQL 归档（368 TOC 条目，容器内 pg_dump）与 env 快照位于 `/home/pgx/backups/luyun-sizheng/20260720-stage2-wp24-spotcheck-r1-predeploy/`，归档 SHA256 为 `bdbba0df04c77d08ccbe74dea29ef1af3de8c4afc53000a3fddc30d096135fa3`。临时复核账号、抽检项、冒烟项目与会话已清理；`luyun-demo` 继续保持 `stage1-workbench-ux-20260719-r1`。

本记录完成 WP2.4 第二增量并收口 WP2.4 内部工程范围（详见《WP2.4 收口记录》）；复核人为内部代理，真实专家抽检与分学段量规确认仍属补签清单。不改变阶段 2、G2 未完成的结论。下一步转入 WP2.5（安全、性能、恢复）。
