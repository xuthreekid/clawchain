# 5 分钟上手

> summary: 本地启动 ClawChain 并完成首轮对话验证  
> read_when: 你第一次运行项目或刚克隆仓库

## 目标

在 5 分钟内完成后端、前端启动，并确认流式对话可用。

## 前置条件

- Python 3.11+
- Node.js 20+
- 可用模型 Provider API Key（或本地 Ollama）

## 最小步骤

（以下命令均从仓库根目录 `clawchain/` 出发）

```bash
python scripts/dev.py
```

可选：仅启动后端或前端

```bash
python scripts/dev.py --backend-only
python scripts/dev.py --frontend-only
```

打开 `http://localhost:3000`，发送一句“你好”。

首次使用若未配置 Provider/模型：启动后在 Web 配置中心完成，或先运行 `cd backend && python cli.py onboard` 完成 CLI 配置后再执行 `python scripts/dev.py`。

## 成功判据

- 前端可看到 assistant 流式输出
- 后端日志无 500 错误
- Inspector 中能看到 lifecycle 事件

## 常见错误与修复

- `ModuleNotFoundError`：确认在 `backend/` 下执行并已安装依赖。
- 前端一直转圈：先检查后端 `http://localhost:8002/api/health` 是否可访问。
- 无模型响应：检查配置中心的 Provider `apiKey` 与默认模型是否匹配。
- 首次启动想免交互：使用 `python cli.py start --provider deepseek --api-key "sk-xxx" --model deepseek-chat`。
- 需要回到干净目录：使用 `python cli.py clean --clean`。
- 想跳过依赖安装：使用 `python scripts/dev.py --skip-install`。

## 下一步

- `quickstart-cli.md`
- `../configuration/index.md`
