# 阶段 2 WP2.4 内部评测与仲裁工程化收口记录

日期：2026-07-20  
状态：内部工程收口；允许进入 WP2.5  
边界：不等于阶段 2、G2、客户验收或专家签字；复核人为内部代理，不代表真实专家评测

## 1. 已完成范围

第一增量（2026-07-19，评测回归门禁，详见《实施记录附录》§18）：

- 发布清单变更检测（`stale` 阻断）、内部阈值判定（匹配率、Top-1 命中率、资料不足漏判、error 案例）与运行间回退对比。
- `GET /api/workbench/evaluation/datasets/{id}/regression-gate`，工作台冻结数据集自动展示门禁结论。

第二增量（2026-07-20，抽检队列与 L4 信号汇总，本次收口）：

- 抽检队列：审核员/管理员可从最近完成的 SkillRun（默认 `skill.diagnose_artifact`）随机抽取未复核运行进入 `spot_check_items`；每项固化抽检时刻的发布清单快照（模型 revision、检索参数、Skill 版本）与 L4/`authorized_for_training=false` 声明，复核人可对照 SkillRun 输入输出证据。
- 双评与仲裁：复用金标治理状态机口径——两位不同复核人独立提交，签名（结论 + 问题标签）完全一致形成 `consensus`；不一致进入 `disputed`，只能由未参与前两次复核的第三人提交 `arbitration`；结论词汇固定 `confirmed / needs_adjustment`，不产生分数或排名。复核记录独立留痕、不可互相覆盖，可附规则字典/量规修订反馈（`rubric_feedback`）。
- L4 信号按规则维度汇总：把 WP2.3 起累积的教师逐条决定（accept / ignore / edit / request_expert）按诊断规则字典维度聚合；教师可查看本人项目汇总，审核员/管理员可查看全局汇总。汇总固定声明 `signal_level=L4`、`authorized_for_training=false`，未经授权、脱敏和质检不得进入训练，不构成对教师或项目的任何评价。
- 工作台新增「抽检复核与 L4 信号」面板：抽样、队列状态计数、证据对照、复核/仲裁提交与维度汇总展示；教师侧仅见本人项目 L4 汇总。

结合第一增量，WP2.4 的五项内部工程口径（抽检任务与证据查看、分歧仲裁与量规反馈、变更触发离线回归、指标不达标阻断、教师/复核信号留痕）已全部闭合，WP2.4 内部工程范围收口。

## 2. 接口与数据影响

- 新增 `POST /api/workbench/spot-checks/sample`、`GET /api/workbench/spot-checks`、`GET /api/workbench/spot-checks/{id}`、`POST /api/workbench/spot-checks/{id}/reviews`（均限审核员/管理员）。
- 新增 `GET /api/workbench/signals/l4-summary`（`project_id` 缺省为全局，全局仅限审核员/管理员）。
- 新增表 `spot_check_items`、`spot_check_reviews`；迁移 `n3b4c5d6e789`（仅新增表，向后兼容）。
- 非评分防护测试自动覆盖新增表、列、路由与 OpenAPI 标识符。

## 3. 验证证据

- 本地门禁：ruff、basedpyright、66 项非集成测试（新增抽检状态机与 L4 汇总纯函数测试）、前端生产构建通过。
- 独立 pgvector PostgreSQL 17 测试库：9 项集成测试通过（新增 WP2.4 抽检双评仲裁 + L4 汇总闭环用例），总计 75 项测试。
- 迁移：独立测试库完成 `m2a3b4c5d678 → n3b4c5d6e789 → m2a3b4c5d678 → n3b4c5d6e789` 往返。
- 真实 `luyun-int` API：教师纵向链（项目→版本→结构确认→诊断→三条 L4 决定）后，抽样命中该诊断运行；双评分歧、重复提交 409、独立复核人仲裁 409、第三人仲裁形成 `arbitrated` 与 resolved 结论；教师访问抽检队列与全局汇总 403；项目级 L4 汇总按三维正确聚合（accept/edit/request_expert 各 1），全局汇总可见。
- 真实 SSE：30 个 `data:` 事件并以 `[DONE]` 结束；`/api/workbench/model-status` 报告 vLLM 未降级。
- Web：新静态包含抽检面板；本机 `/healthz` 与 Tailnet 两个 HTTPS `/healthz` 通过。
- 回滚：实际切换回 `stage2-wp24-gate-20260719-r1` 后 API/Web healthy（新表向后兼容，无需数据库降级），随后恢复当前镜像并复验抽检接口。
- 临时冒烟数据（临时复核账号、抽检项、项目、会话）已清理。

## 4. 部署记录

- 环境：`luyun-int`
- 标签：`stage2-wp24-spotcheck-20260720-r1`
- API 镜像：`3fe20bf742c9...`
- Web 镜像：`f94ec1381933...`
- 数据库：`n3b4c5d6e789 (head)`（自 `m2a3b4c5d678` 升级）
- 备份：`/home/pgx/backups/luyun-sizheng/20260720-stage2-wp24-spotcheck-r1-predeploy/`（368 TOC 条目）
- PostgreSQL 归档 SHA256：`bdbba0df04c77d08ccbe74dea29ef1af3de8c4afc53000a3fddc30d096135fa3`
- `luyun-demo`：保持 `stage1-workbench-ux-20260719-r1`，未晋级。

## 5. 未完成与下一步

- 抽检复核与仲裁均为内部代理产物；真实专家抽检、分学段量规确认与专家仲裁属 §0.5 补签清单，不得表述为专家评测。
- L4 信号仅汇总回看；训练授权、脱敏与质检门在阶段 4 另行建设，当前一律 `authorized_for_training=false`。
- 本轮浏览器侧仅验证静态资源与构建，未做 Virtus 跨设备人工复核。
- 下一纵向增量为 WP2.5：安全、性能与恢复（权限隔离/提示注入/越权测试、试点组织白名单与最小 RBAC、分级降级、备份恢复与并发指标验证）。
