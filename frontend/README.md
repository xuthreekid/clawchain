# ClawChain Frontend

基于 Next.js + React + TypeScript 的 ClawChain Web 客户端。

## 技术栈

- **框架**: Next.js (App Router)
- **UI**: React + Tailwind CSS
- **状态管理**: React Context + Hooks
- **Markdown 渲染**: react-markdown + remark-gfm
- **代码编辑**: @monaco-editor/react
- **图标**: Lucide React

## 开发运行

### 前置条件

- Node.js 20+
- 后端服务已启动（默认 `http://localhost:8002`）

### 启动

```bash
# 安装依赖
npm install

# 开发模式
npm run dev

# 生产构建
npm run build

# 生产预览
npm run start

# ESLint 检查
npm run lint
```

## 目录结构

```
frontend/
├── src/
│   ├── app/              # Next.js App Router 入口
│   │   ├── page.tsx      # 主页面
│   │   ├── layout.tsx    # 根布局
│   │   └── globals.css   # 全局样式
│   ├── components/       # React 组件
│   │   ├── chat/         # 聊天相关组件
│   │   ├── inspector/    # Inspector 面板组件
│   │   ├── layout/       # 布局组件
│   │   └── editor/       # 编辑器组件
│   ├── lib/              # 工具库
│   │   ├── api.ts        # API 客户端
│   │   ├── store.tsx     # 全局状态管理
│   │   └── hooks/        # 自定义 Hooks
│   └── i18n/             # 国际化
├── package.json
├── tsconfig.json
├── tailwind.config.ts
└── postcss.config.mjs
```

## 核心组件

### ChatPanel
聊天主面板，处理消息展示、输入、流式输出

### InspectorPanel
侧边检查面板，支持文件浏览、技能管理、子 Agent 状态、审计日志等

### Navbar
顶部导航栏，包含 Agent 切换、主题切换、菜单等

### ConfigModal
配置中心弹窗，支持 Provider/模型配置

## 状态管理

使用 React Context (`AppProvider`) 统一管理：
- Agent 列表与切换
- 会话消息与流式状态
- Inspector 布局与文件操作
- 主题与国际化
- 技能热加载通知

## API 通信

所有后端请求封装在 `src/lib/api.ts`：
- SSE 流式对话 (`streamChat`)
- 中断对话 (`abortChat`)
- Agent/Session 管理
- 配置读写
- 文件读写
- 子 Agent 状态订阅

## 国际化

支持 `zh-CN` 和 `en-US`，配置文件位于 `src/i18n/locales.ts`。
用户偏好存储在 `localStorage`。

## 主题

支持 `system` / `light` / `dark` 三种模式，使用 CSS 变量实现。

## 许可证

MIT
