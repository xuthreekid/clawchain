# ClawChain Desktop (Tauri)

桌面端目标：提供 macOS 常驻后台体验（托盘、通知、后端伴随进程），让本地 Agent 在桌面场景稳定运行。

## 当前状态

Alpha（可开发可运行，未做生产级发布）

- 已实现
  - Tauri 主程序入口与窗口生命周期管理（关闭即隐藏到后台）
  - 系统托盘菜单（显示窗口 / 退出）
  - 后端启动双路径：
    - 优先使用打包 sidecar（`python-backend`）
    - 开发态自动回退到 `backend/cli.py serve --sidecar`
  - 后端健康检查链路（`/api/health`）与就绪等待
  - 一键桌面开发脚本（前端 + Tauri）
- 当前边界
  - 仍未完成生产签名、自动更新、崩溃恢复与跨平台 sidecar 打包

## 目录结构

- `desktop/src-tauri/`：Rust 入口、托盘、sidecar 与 Tauri 配置
- `desktop/package.json`：桌面开发/构建脚本

## 开发运行

前置要求：

- Node.js 22+
- Rust stable
- Python 环境可运行 `backend/cli.py`

执行：

```bash
cd desktop
npm install
npm run doctor
npm run dev
```

默认端口：

- 前端：`http://localhost:3717`
- 后端：`http://localhost:3716`

## 构建验证

```bash
cd desktop
npm run build:frontend
```

如需进一步尝试 Tauri 构建：

```bash
cd desktop
npm run build:tauri
```

> 说明：当前配置将 `bundle.active=false`，用于先验证工程链路；后续补齐应用图标、签名与 sidecar 打包后再切换正式发布配置。
