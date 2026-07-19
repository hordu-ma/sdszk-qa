# 阶段 2 WP2.3 证据化诊断收口记录

日期：2026-07-19  
状态：内部工程收口；允许进入 WP2.4  
边界：不等于阶段 2、G2、客户验收或专家签字

## 1. 已完成范围

- 已有教案可预览结构识别结果，教师可校正标题和结构类型后显式确认；确认写入不可变 `ProjectVersion`。
- `skill.diagnose_artifact` v1.1.0 输出稳定 `item_id`，并逐条提供原文位置、规则依据、可见证据、影响、建议、示例改写和修订目标。
- 教师可逐条采纳、忽略、编辑后采纳或申请专家复核；每次决定生成新版本并记录为 L4 信号。
- 所有 L4 信号默认 `authorized_for_training=false`，不能直接进入训练或微调数据。
- `skill.apply_revision` v1.0.0 只应用采纳/编辑后采纳项；忽略和专家复核项跳过，字段锁定时服务端拒绝修改。
- 二次修改稿保留诊断历史和应用清单，移除当前诊断，要求修改后重新诊断；不覆盖任何历史版本。
- 桌面工作台新增结构确认、证据对照、四类决定和采纳项修订面板；不提供总分、排名或教师绩效界面。

## 2. 接口与数据影响

- 新增 `GET/POST /api/workbench/projects/{id}/diagnosis/structure`。
- 新增 `POST /api/workbench/projects/{id}/diagnosis/items/{item_id}/decision`。
- 新增 `POST /api/workbench/skills/apply-revision`。
- `diagnose-artifact` 新增可选 `source_version`，输出项增加证据定位字段；原入口保留兼容。
- 无数据库 Schema 变化；结构、决定、信号和修订记录均存入不可变项目版本内容。

## 3. 验证证据

- `make harness-quick`：ruff、basedpyright、51 项非集成测试和前端生产构建通过。
- 独立 PostgreSQL 17 测试库：8 项集成测试通过，总计 59 项测试。
- 真实 `luyun-int` API：结构确认、三条诊断证据、采纳、编辑后采纳和 `apply_revision` 通过；只应用两条明确采纳项，临时项目已清理。
- Web：根页面、诊断面板静态资源、Chromium 渲染和 Tailnet HTTPS 健康通过。
- 迁移：`m2a3b4c5d678 (head)`，本轮无迁移。
- 回滚：实际切换到 `stage2-wp22-closure-20260719-r3`，API/Web healthy 且页面可访问；随后恢复 WP2.3 镜像。

## 4. 部署记录

- 环境：`luyun-int`
- 标签：`stage2-wp23-closure-20260719-r1`
- API 镜像：`c03324da3765...`
- Web 镜像：`3d5e240f370f...`
- 备份：`/home/pgx/backups/luyun-sizheng/20260719-stage2-wp23-closure-r1-predeploy/`
- PostgreSQL 归档 SHA256：`5efc2ca1de9fc3d1a2a2f7e7ebb40cf566c9ae6f146c412c485af97822114658`
- `luyun-demo`：保持 `stage1-workbench-ux-20260719-r1`，未晋级。

构建时 npm registry 对同一依赖下载连续两次超时。前端已先用仓库锁文件完成本地生产构建，发布改用该 `dist` 离线封装 Web 镜像，并显式规范静态文件读取权限；仓库 Dockerfile 和依赖未变。

## 5. 未完成与下一步

- 当前三维规则仍是高中议题式内部工程规则，分学段正式量规需后续专家补签，不能表述为专家确认。
- 真实教师长教案可用性、客户专属材料和专家复核尚未完成。
- 下一纵向增量为 WP2.4：内部评测/仲裁工程化、发布清单回归与失败阻断；外部专家任务仍留在补签清单。
