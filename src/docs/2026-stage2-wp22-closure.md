# 阶段 2 WP2.2 内部工程收口记录

日期：2026-07-19

状态：内部工程收口；允许进入 WP2.3 纵向增量

边界：不代表阶段 2 完成、G2 通过、客户模板确认、真实教师验收或专家签字

## 1. 收口结论

WP2.2 已形成从结构化生成到受控修改、恢复和导出的内部工程闭环：

1. `alignment_card`、`design_blueprint` 和 `generate_section` 按前置成果依序运行，上游重跑会使未锁定的下游成果失效。
2. 教师可编辑目标、证据、任务和课堂活动映射；可锁定章节或配套成果，服务端拒绝绕过锁定的写入和局部重生成。
3. 局部重生成只修改指定字段，并通过 `source_version` 阻止多标签页或旧页面覆盖最新版本。
4. 历史恢复创建新版本，不删除或改写原快照；版本比较同时提供字段级和章节级差异。
5. 当前蓝图和课时设计可派生课堂任务单、非评分观察量规、板书、课件提纲和实践任务，并汇总进入标准 Word。

## 2. 接口与版本契约

- `skill.generate_section`：v1.1.0。
- 规则集：`stage2-structured-gen-v1`。
- `POST /api/workbench/skills/generate-section`：支持 `artifact_kind`、`target_path`、`guidance` 和 `source_version`。
- `POST /api/workbench/projects/{id}/versions/locks`：更新锁定路径并创建新版本。
- `POST /api/workbench/projects/{id}/versions/restore`：从历史快照创建恢复版本。
- `POST /api/workbench/projects/{id}/versions`：教师编辑必须携带来源版本；锁定字段变化返回冲突。
- `GET /api/workbench/projects/{id}/versions/diff`：同时返回 `changed_sections` 和 `field_changes`。
- 本轮复用 `ProjectVersion.content` 保存 `editor_state` 和 `teaching_artifacts`，无数据库迁移。

## 3. 锁定、失效与恢复规则

- 支持锁定目标、蓝图证据、单个学习任务、课堂导入、单个活动、评价证据、教师提示和单项配套成果。
- 局部重生成与教师保存均由服务端比较锁定路径，不能依赖前端禁用状态保证安全。
- 课时设计变化会清除旧诊断和未锁定配套成果；锁定配套成果保持不变，但由教师承担继续保留的显式决定。
- 专业输入、对齐卡或蓝图变化会清理不再适用的课时、诊断、配套成果和编辑锁定状态。
- 恢复操作完整复制选定历史快照，并以 `restore_version` 轨迹创建新的最新版本。

## 4. 验证证据

| 层级 | 结果 |
| --- | --- |
| 静态门禁 | ruff、basedpyright 通过，0 error / warning |
| 后端单元 | 51 passed，覆盖 Skill 版本、非评分防护和含配套成果的 Word |
| 后端集成 | PostgreSQL 17 独立测试库 7 passed，覆盖锁定、并发版本、局部变化、多成果、差异和恢复 |
| 前端 | Vue TypeScript 检查与 Vite 生产构建通过 |
| API 冒烟 | 锁定目标 409；目标字段单独变化；五类成果生成；历史恢复和 SkillRun 审计通过 |
| Chromium | 锁定/解锁、按钮禁用、局部重生成、任务单生成、字段差异和确认式恢复通过 |
| Tailnet | 页面新资产可达，`skill.generate_section` 返回 v1.1.0 |
| 数据清理 | API 与 Chromium 临时项目计数为 0 |

## 5. 部署与回滚

- 集成环境：`luyun-int`。
- 当前镜像：`stage2-wp22-closure-20260719-r3`。
- API/Web 镜像 ID：`7b1b9cd91085...` / `9b0be24e6495...`。
- 数据库：`m2a3b4c5d678 (head)`；本轮无 Schema 变化。
- 发布前备份：`/home/pgx/backups/luyun-sizheng/20260719-stage2-wp22-closure-r3-predeploy/`。
- 数据库归档 SHA256：`49087e3088956e3f4476c88c1e89a9239d366ba6bba688f9f667dd6747c1b254`。
- 回滚演练：实际恢复 `stage2-wp22-closure-20260719-r2`，API/Web 健康后重新部署当前镜像；无需数据库降级。
- 稳定演示环境：`luyun-demo` 保持 `stage1-workbench-ux-20260719-r1`，未接收本增量。

## 6. 外部补签与下一阶段边界

- 当前使用内部标准模板 `word-standard-v2`；客户专属 Word 模板实物到位后必须新增模板版本并重新跑导出回归，不得把标准模板写成客户确认模板。
- 尚未进行真实教师长文档可用性研究，内部 Chromium 结果只代表工程链路可用。
- WP2.3 的已有教案结构校正、证据化诊断、逐条采纳/忽略/编辑和 `apply_revision` 尚未实现。
- WP2.4–WP2.7、阶段 2 Beta 和 G2 门禁仍未完成。
