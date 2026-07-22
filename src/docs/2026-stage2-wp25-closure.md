# 阶段 2 WP2.5 安全、性能与恢复 · 第一增量收口记录

日期：2026-07-20  
状态：WP2.5 第一增量（安全测试与输入防护）内部工程收口；WP2.5 整体未收口  
边界：不等于阶段 2、G2、客户验收、安全审计或渗透测试结论；复核与防护均为内部工程口径

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

## 5. 未完成与下一步

- 提示注入防护为工程缓解措施；模型对注入话术的语义抵抗仍属内部工程口径，不代表安全审计或渗透测试。
- WP2.5 后续增量：试点组织白名单与最小 RBAC、跨组织隔离与全链路审计；模型/RAG/队列分级降级；备份恢复、任务恢复与版本回滚演练；试点并发下的运行指标。未完成这些能力不得开展多校真实试点。
- 完成 WP2.5 全部增量后转入 WP2.6（样板场景试点）与 WP2.7（双环境晋级 v2）。
