# API 参考（核心）

> summary: ClawChain 前后端协同所需的核心 REST/SSE 接口  
> read_when: 你在联调前端、编写测试、排查接口问题

## 目标

快速定位关键接口和预期行为。

## 核心接口

- `POST /api/chat`：SSE 聊天流（token、tool、lifecycle、done、aborted）
- `POST /api/chat/abort`：中断指定会话正在运行的流（可选清空 followup 队列）
- `GET /api/agents`：获取 agent 列表
- `GET /api/agents/{id}/session/messages`：加载会话消息
- `PUT /api/config`：更新表单配置（脱敏字段保护）
- `GET /api/config`：脱敏后的完整配置
- `GET /api/config/chat`：聊天配置（`timeoutSeconds`，供前端请求超时）
- `GET /api/config/raw`：原始配置（默认仅 localhost）
- `PUT /api/config/replace`：整份替换配置（会恢复 masked secrets）
- `GET /api/init/status`：初始化状态（支持 CLI/前端双轨）
- `POST /api/approvals/{approval_id}/resolve`：用户确认/拒绝危险工具执行（Body: `{ "decision": "approved" | "denied" }`）

## SSE 事件建议

- 前端必须处理流结束残留 buffer，避免丢失最终 `done`。
- 对用户主动 stop，建议调用 `POST /api/chat/abort`，并优先消费 `aborted` 事件。
- 若不是用户主动停止且 `done` 未收到，回退到 `loadMessages` 做状态修复。
- 实现流式 UI 时，建议按“当前流消息 id”更新，而不是按“最后一条消息”更新，避免 stop 后立刻追问时事件串写。

## 中断与队列语义

- 会话级串行：同一 `agent_id + session_id` 同时只处理一条运行链路。
- 忙碌时新消息进入 followup 队列（返回 `queued` + `done`）。
- `POST /api/chat/abort` 会尝试取消该会话的当前运行任务。
- 发生中断时，后端会尽量保留并写入本轮 partial assistant 内容，并发送 `aborted` 终态事件。

## 常见错误与修复

- 403 on `/config/raw`：非本机访问被限制；可用环境变量显式放开。
- 422 校验错误：配置不符合 schema。
- 前端卡流：检查网络代理、SSE 分块与 `done/aborted` 事件。

## 下一步

- `../help/troubleshooting.md`
