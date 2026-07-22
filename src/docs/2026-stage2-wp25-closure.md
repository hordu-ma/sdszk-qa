# 阶段 2 WP2.5 安全、性能与恢复 · 收口记录（增量 1–2）

日期：2026-07-20（增量 1）、2026-07-22（增量 2）  
状态：WP2.5 增量 1（安全测试与输入防护）、增量 2（试点组织白名单与最小 RBAC）内部工程收口；WP2.5 整体未收口  
边界：不等于阶段 2、G2、客户验收、安全审计或渗透测试结论；组织隔离、复核与防护均为内部工程口径

## 1. 已完成范围（第一增量：主计划 WP2.5 第 1 条）

- 恶意文件防护：上传在既有后缀白名单与大小上限之外，新增按真实内容校验的 `validate_upload_content`（不信任客户端声明 MIME）。
  - 任何后缀拒绝可执行文件魔数（Windows PE、Linux ELF、Mach-O、Java class）。
  - `.pdf` 必须以 `%PDF-` 开头；`.docx` 必须是含 `[Content_Types].xml` 与 `word/` 结构的 ZIP，且拒绝 `vbaProject.bin` 宏载荷；`.txt/.md` 必须为 UTF-8 且不含 NUL 字节。
  - 不符内容返回 415，错误信息不回显文件内容。
- 提示注入隔离：系统提示新增「数据与指令边界」规则；用户可控的主题上下文（含自定义会话主题）包裹在【主题上下文数据-开始/结束】定界块内并声明块内指令无效；历史消息注入前强制角色白名单（仅 user/assistant），防止存量数据提升为 system 指令。
- 安全回归测试：跨用户越权、跨角色边界、敏感数据不外泄和恶意文件的自动回归套件（见 §3）。

## 2. 接口与数据影响

- 无新增路由、无新增表、无 Schema 变化（迁移保持 `n3b4c5d6e789`）。
- `POST /api/workbench/projects/{id}/documents` 在大小校验后新增内容校验分支，返回 415；其余行为不变。
- 无前端改动。

## 3. 验证证据

- 本地门禁：ruff、basedpyright、74 项非集成测试（新增 `tests/test_security_hardening.py` 8 例纯函数：五类恶意内容拒绝、注入话术保持在数据块内、历史角色不升权）、10 项集成测试（临时 pgvector PostgreSQL 17，新增 `tests/test_security_boundaries.py`：跨用户 11 个端点 403/404、教师角色 6 个复核入口 403、匿名 401/403、恶意文件 API 面 415、登录与 `/auth/me` 不含口令散列）通过。
- 真实 `luyun-int` API：五类恶意文件（假 DOCX/PE、假 PDF/脚本、含 NUL 文本、宏 DOCX、EXE）上传均 415 且正常 Markdown 202；跨用户四类资源 403/404、教师角色三类复核入口 403、匿名 401/403；注入话术经自定义主题与用户消息走真实 vLLM SSE，链路稳定并以 `[DONE]` 结束（385 事件）；`/api/workbench/model-status` 未降级；登录与 `/auth/me` 不泄露口令散列。
- 回滚：实际切换回 `stage2-wp24-spotcheck-20260720-r1` 后 API/Web healthy，随后恢复当前镜像并复验 `/healthz` 与 Tailnet HTTPS；无数据库变更。
- 临时冒烟数据（入侵者账号、项目、会话与自定义主题）已清理。

## 4. 部署记录

- 环境：`luyun-int`
- 标签：`stage2-wp25-security-20260720-r1`
- API 镜像：`95b5bc8a8151...`
- Web 镜像：`1bd060766861...`
- 数据库：`n3b4c5d6e789 (head)`（无变化）
- 备份：`/home/pgx/backups/luyun-sizheng/20260720-stage2-wp25-security-r1-predeploy/`（397 TOC 条目）
- PostgreSQL 归档 SHA256：`afc6c8d1c4ef98c3715b2ce779e57788256a2fcd738780cc17a0d3507fc6e87a`
- `luyun-demo`：保持 `stage1-workbench-ux-20260719-r1`，未晋级。

## 5. 增量 2：试点组织白名单与最小 RBAC（2026-07-22，主计划 WP2.5 第 2 条）

### 5.1 已完成范围

- 组织模型：新增 `organizations`（code 唯一、status=pilot_active/suspended）与 `users.organization_id`（nullable FK，ON DELETE SET NULL）。白名单 = status=pilot_active。
- 试点白名单门禁：新增 `get_pilot_user` 依赖并作用于整个工作台路由。平台 admin 放行；其余用户须属于白名单（pilot_active）组织，否则 403（`pilot_membership_required` / `pilot_org_not_whitelisted`）。
- 最小 RBAC 收敛：把原先分散在各服务的 `role not in {admin, reviewer}` 判定收敛到 `services/rbac.py`（`is_platform_admin`、`is_privileged`、`owner_in_actor_scope`、`scope_owner_ids`、`require_pilot_membership`）。
- 跨组织隔离（reviewer 仅本组织，平台 admin 覆盖全部）覆盖全部特权跨用户路径：评测 `get_accessible_dataset`、`review_dataset`、`list_review_queue`、`submit_case_review`、`list_case_reviews`；抽检 `sample_spot_checks`、`list_spot_checks`、`get_spot_check_detail`、`submit_spot_check_review`；`l4_signal_summary`（项目与全局两支）；资料审核 `review_document`。
- 组织管理路由 `/api/organizations`（平台 admin 专用，不受试点门禁限制）：列出、创建、置状态、指派用户组织。
- 迁移 `o4c5d6e7f890` 创建组织表与默认试点组织 `luyun-pilot-default`，并将存量用户回填该组织，保证升级后既有账号继续可用；`seed_demo` 与测试夹具共用同一默认组织口径。

### 5.2 显式设计缺口（内部自助模式）

平台 `admin` 为内部运营角色，组织无关、可跨全部组织访问、并独占组织白名单开关。这是「跨组织隔离」的一处**有意缺口**，仅限自助内部模式；组织管理入口限平台 admin。多校真实试点前须按客户身份体系重新界定运营边界。

### 5.3 验证证据

- 本地门禁：ruff、basedpyright、74 项非集成测试、11 项集成测试（临时 pgvector PostgreSQL 17，新增 `test_cross_org_isolation_and_pilot_whitelist`：暂停组织成员 403、org A reviewer 对 org B 的项目/数据集/报告/审核/资料审核/L4 全部 403/404、复核队列不含跨组织数据集）通过。
- 迁移：独立测试库完成 `n3b4c5d6e789 → o4c5d6e7f890 → n3b4c5d6e789 → o4c5d6e7f890` 往返，并验证默认组织创建与用户回填。
- 真实 `luyun-int` API：存量 demo_teacher（默认组织）工作台可用；平台 admin 组织管理（创建/置暂停）成功、教师越权 403；暂停组织成员登录成功但工作台 403；org A reviewer 对 org B 项目/数据集/报告/审核/L4 全部 403/404 且复核队列不含跨组织数据集；平台 admin 跨组织可见（记录缺口）；vLLM 未降级。
- 回滚：实际切换回 `stage2-wp25-security-20260720-r1`（升级后 DB，nullable+回填保证向后兼容）后 API/Web healthy，随后恢复当前镜像并复验本机与 Tailnet `/healthz`。
- 临时冒烟数据（组织、账号、项目、审计）已清理。

### 5.4 部署记录（增量 2）

- 环境：`luyun-int`
- 标签：`stage2-wp25-orgrbac-20260722-r1`
- API 镜像：`5ed2cba33a88...`
- Web 镜像：`b2e874eb6a72...`
- 数据库：`o4c5d6e7f890 (head)`（自 `n3b4c5d6e789` 升级；新增 `organizations` 表 + `users.organization_id` 列，nullable+回填）
- 备份：`/home/pgx/backups/luyun-sizheng/20260722-stage2-wp25-orgrbac-r1-predeploy/`（397 TOC 条目）
- PostgreSQL 归档 SHA256：`bfb6d811c1262f7c64031308e1956dfc173075c4e154c590b69d9363a6ee6d74`
- `luyun-demo`：保持 `stage1-workbench-ux-20260719-r1`，未晋级。

## 6. 未完成与下一步

- 提示注入防护为工程缓解措施；模型对注入话术的语义抵抗仍属内部工程口径，不代表安全审计或渗透测试。
- 平台 admin 跨组织可见为有意缺口（见 §5.2），多校真实试点前须重新界定。
- WP2.5 剩余增量：模型/RAG/队列分级降级；备份恢复、任务恢复与版本回滚演练；试点并发下的运行指标。未完成这些能力不得开展多校真实试点。
- 完成 WP2.5 全部增量后转入 WP2.6（样板场景试点）与 WP2.7（双环境晋级 v2）。
