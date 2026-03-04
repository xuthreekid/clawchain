# 配置总览

> summary: 理解 `config.json` 的结构、优先级和安全写回策略  
> read_when: 你要改模型、工具、会话或初始化逻辑

## 目标

明确配置从模板到运行时的完整链路，避免“改了没生效”。

## 前置条件

- 已有 `backend/data/config.json`

## 结构概览

- `agents`：默认 agent 配置、agent 列表
- `models.providers`：各厂商 API、模型列表
- `tools`：工具总开关与细粒度配置
- `chat`：聊天请求超时（`timeoutSeconds`，0=无超时，默认 120）
- `session`：压缩、清理、上限
- `cron`：定时任务

### 超时配置

| 配置路径 | 说明 | 默认 |
|---------|------|------|
| `chat.timeoutSeconds` | 聊天请求超时秒数，0=无超时 | 120 |
| `agents.defaults.subagents.run_timeout_seconds` | 子 Agent 执行超时，0=无超时 | 0 |

### Exec 执行确认

`tools.exec.approval` 控制 exec、process_kill 等危险工具的执行前确认：

| 字段 | 说明 | 默认 |
|------|------|------|
| `security` | `deny` | `allowlist` | `full` | 安全策略 | 无配置时 `full` |
| `ask` | `off` | `on_miss` | `always` | 何时弹确认 | 无配置时 `off` |
| `ask_timeout_seconds` | 确认超时秒数 | 60 |
| `allowlist` | 白名单模式（glob） | [] |

- `security=full` + `ask=off`：无确认直接执行（当前默认行为）
- `security=allowlist`：仅白名单内命令可执行
- `ask=always`：每次执行都需用户确认
- `ask=on_miss`：白名单未命中时需确认

可选：`data/exec-approvals.json` 可追加 allowlist，与 config 合并。

## 生效机制

1. 读取原始配置（保留 `${ENV_VAR}`）。
2. 运行时解析环境变量得到 resolved 配置。
3. 前端提交时做 schema 校验与敏感字段保护。
4. 保存回 raw 配置，防止模板占位符丢失。

## 常见错误与修复

- 保存后密钥变成掩码：已做后端保护，不会覆盖真实密钥。
- provider/model 不匹配：检查 `agents.defaults.model` 是否为 `provider/modelId`。
- JSON 编辑器改完无效：确认提交后接口返回 200 且无校验错误。

## 下一步

- `providers.md`
- `../api/reference.md`
