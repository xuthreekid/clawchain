# CLI 初始化速查

> summary: 用 CLI 完成 setup/onboard/serve/doctor 全链路  
> read_when: 你希望可脚本化、可复现地初始化项目

## 目标

通过命令行完成配置初始化与健康检查。

## 前置条件

- 已安装后端依赖
- 从仓库根目录进入：`cd backend`

## 最小步骤

```bash
cd backend
python cli.py setup
python cli.py onboard
python cli.py doctor
python cli.py serve
```

## 命令说明

- `setup`：创建 `data/config.json` 与默认工作区模板文件
- `onboard`：交互式写入 Provider、模型、默认 agent model
- `doctor`：检查配置完整性与关键文件状态
- `serve`：启动 FastAPI 服务

## 常见错误与修复

- `serve` 报未初始化：使用 `python cli.py setup` 后重试。
- `onboard` 后无模型：确认 `agents.defaults.model` 指向 `provider/modelId`。
- 端口占用：用 `--port` 更换端口，例如 `python cli.py serve --port 8010`。

## 下一步

- `../configuration/providers.md`
- `../help/troubleshooting.md`
