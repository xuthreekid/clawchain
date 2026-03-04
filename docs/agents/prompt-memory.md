# Prompt 与记忆机制

> summary: 说明 full/minimal/none 提示词层级与记忆写入策略  
> read_when: 你要调 prompt、解释心跳、优化 `/new`

## 目标

确保提示词、工具能力、记忆机制形成闭环，不出现“提示词提到但系统没有”的能力。

## Prompt 分层

- `full`：身份、工具、消息路由、安全、技能、记忆、心跳、运行时、工作区上下文
- `minimal`：子 Agent 场景，保留必要约束与工具说明
- `none`：最小身份提示，仅用于极简模式

## 文档注入策略

系统提示强制加入 `docs/` 入口，要求任务前先读文档对应页面。

## 记忆策略

- 日常记忆：`memory/YYYY-MM-DD.md`
- 长期记忆：`MEMORY.md`
- `/new`：先重置会话，再后台异步保存会话记忆并发事件反馈

## 常见错误与修复

- 心跳只回 `HEARTBEAT_OK`：应先读 `HEARTBEAT.md`，仅在无事项时返回。
- 记忆保存阻塞：检查后台任务事件 `session_memory_saved/failed`。
- 提示词过长：切换 `minimal` 并减少上下文注入。

## 下一步

- `architecture.md`
- `../help/troubleshooting.md`
