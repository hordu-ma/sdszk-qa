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
│   └── views/        # 登录/主题列表/问答页/历史会话页
├── package.json
└── vite.config.ts
```

## 主要页面

- `Login.vue`：登录页
- `CaseList.vue`：主题/场景列表页
- `Chat.vue`：问答页（SSE 流式）
- `SessionList.vue`：历史会话页

## 前端调用链

1. 用户登录后进入主题列表。
2. 选择主题创建会话。
3. 进入问答页，通过 `/api/chat` 进行流式对话。
4. 在历史会话页回看会话内容。

## 运行命令

```bash
npm install
npm run dev
npm run build
```
