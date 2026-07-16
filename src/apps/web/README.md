# Web 前端说明（鲁韵思政）

本目录为鲁韵思政问答系统的 Web 前端，基于 Vue 3 + Vite + TypeScript，使用 Vant 组件库，Pinia 管理状态，并通过 axios 访问后端 API。

> 基础设施与部署请参考：`src/infra/README.md`。

## 目录结构概览

```
web/
├── src/
│   ├── api/          # API 请求封装
│   ├── router/       # 路由与鉴权守卫
│   ├── stores/       # 用户状态
│   ├── types/        # 前后端对齐类型
│   └── views/        # 登录/主题/问答/历史/工作台页
├── package.json
└── vite.config.ts
```

## 主要页面（当前）

- `Login.vue`：登录页
- `CaseList.vue`：主题/场景列表页
- `Chat.vue`：问答页（SSE 流式）
- `SessionList.vue`：历史会话页
- `Workbench.vue`：桌面优先工作台基础页（项目、资料、审核、任务、依据检索）

> 当前已有轻交互问答和桌面优先工作台基础页。Skills 清单及 Memory 偏好/班情/导出/清除已有后端 API，但 Memory 注入确认和管理界面、成果编辑、诊断对照、版本 diff 与导出尚未实现；阶段 3 另交付轻量小程序端。

## 前端调用链（当前）

1. 用户登录后进入主题列表。
2. 选择主题创建会话。
3. 进入问答页，通过 `/api/chat` 进行流式对话。
4. 在历史会话页回看会话内容。
5. 从主题页进入工作台，管理项目、资料与任务，并运行依据检索。

## 运行命令

```bash
npm install
npm run dev
npm run build
```
