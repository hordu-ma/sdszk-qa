# Web 前端说明

本目录为临床医学模拟问诊系统的 Web 前端，基于 Vue 3 + Vite + TypeScript，使用 Vant 作为 UI 组件库，Pinia 管理状态，并通过 axios 访问后端 API。

> 生产部署流程请统一参考：`生产部署指南.md`。

## 目录结构概览

```
web/
├── README.md
├── index.html
├── package.json
├── package-lock.json
├── vite.config.ts
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
├── components.d.ts
├── public/
├── dist/
├── src/
│   ├── App.vue
│   ├── main.ts
│   ├── style.css
│   ├── api/
│   │   ├── request.ts
│   │   ├── auth.ts
│   │   ├── cases.ts
│   │   └── session.ts
│   ├── components/
│   │   └── HelloWorld.vue
│   ├── router/
│   │   └── index.ts
│   ├── stores/
│   │   └── user.ts
│   ├── types/
│   │   ├── api.ts
│   │   └── index.ts
│   └── views/
│       ├── Login.vue
│       ├── CaseList.vue
│       ├── Chat.vue
│       └── SessionList.vue
└── node_modules/ (本地依赖)
```

---

## 项目入口与构建配置

### index.html

- Vite 应用入口 HTML 模板
- 挂载点为 `#app`，入口脚本为 `src/main.ts`

### src/main.ts

- Vue 应用启动入口
- 注册 Pinia 与 Vue Router
- 引入 Vant 全局样式与全局 CSS

### src/App.vue

- 根组件
- 仅包含 `<router-view />`，页面由路由驱动

### vite.config.ts

- Vite 配置文件
- 启用 Vue 插件与 Vant 组件自动按需引入
- 开发服务器代理 `/api` → `http://localhost:8000`

### package.json

- 前端依赖与脚本
- 常用脚本：
  - `dev`：开发启动
  - `build`：类型检查 + 构建
  - `preview`：本地预览构建结果

### tsconfig.\*

- TypeScript 配置
  - `tsconfig.json`：基准与引用
  - `tsconfig.app.json`：应用源码
  - `tsconfig.node.json`：Vite 配置与 Node 侧类型

### components.d.ts

- 由 `unplugin-vue-components` 自动生成
- 提供 Vant 与全局组件类型声明

---

## API 访问层（src/api）

### api/request.ts

- axios 实例与拦截器
- 自动注入 JWT token
- 统一处理 401 与错误提示

### api/auth.ts

- 登录与用户信息接口封装
- 导出 `login()`、`getUserInfo()`

### api/cases.ts

- 病例列表、病例详情、可用检查接口封装

### api/session.ts

- 会话列表/创建/详情
- 检查申请、诊断提交
- 评分结果获取

---

## 路由与状态管理

### router/index.ts

- 路由定义：登录页、病例列表、问诊室、历史会话
- 路由守卫：未登录跳转到 `/login`

### stores/user.ts

- Pinia 用户状态
- 管理 token、用户信息
- token 持久化到 localStorage

---

## 视图页面（src/views）

### Login.vue

- 登录页面
- 调用 `auth.login` 获取 token 并拉取用户信息

### CaseList.vue

- 病例列表页
- 选择病例后创建会话并跳转问诊

### Chat.vue

- 问诊聊天页（SSE 流式响应）
- 展示聊天历史
- 申请检查、提交诊断、显示评分

### SessionList.vue

- 历史会话列表
- 进入历史会话查看详情

---

## 类型定义（src/types）

### types/api.ts

- 与后端 Pydantic schemas 对齐的接口类型
- 包含 Auth、Cases、Sessions、Scores、Tests 等结构

### types/index.ts

- 统一导出类型

---

## 样式与组件

### src/style.css

- 全局样式（Vite 模板默认样式，尚未清理）

### components/HelloWorld.vue

- Vite 模板示例组件（当前未在主流程使用）

---

## 构建产物与静态资源

### public/

- 静态资源目录（当前为空或未使用）

### dist/

- 构建产物输出目录（`vite build` 生成）

---

## 运行说明

- 开发启动：`npm run dev`
- 构建产物：`npm run build`
- 预览构建：`npm run preview`

> 开发时通过 Vite 代理 `/api` 到后端 `http://localhost:8000`。
