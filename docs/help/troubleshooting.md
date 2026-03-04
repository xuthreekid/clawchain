# 常见问题排查

> summary: 按症状定位 ClawChain 常见故障并快速修复  
> read_when: 前端转圈、接口报错、模型不返回、初始化失败

## 目标

按“症状 -> 检查 -> 修复”方式缩短故障定位时间。

## 症状 1：前端一直转圈

- 检查后端是否可达：`GET /api/health`
- 检查 SSE 是否有 `done` 或 `aborted` 事件
- 检查浏览器控制台是否有 CORS 或网络中断

## 症状 1.1：点 stop 后消息“消失”或界面突兀刷新

- 先确认前端 stop 是否调用了 `POST /api/chat/abort`（而不仅是本地断开流）。
- 确认后端能返回 `aborted` 事件；该事件应带回当前 partial 内容。
- 仅在“非用户主动 stop 且未收到 done/aborted”时，才建议回退 `loadMessages`。

## 症状 2：`/new` 感觉卡住

- 当前策略是前台快速 reset、后台保存记忆
- 在 Inspector 查看 `session_memory_saved` 或 `session_memory_failed`
- 若长期无事件，检查模型延迟与磁盘写入权限

## 症状 3：模型不可用

- 校验 `agents.defaults.model` 与 provider/modelId 是否一致
- 校验 `apiKey`、`baseUrl`、网络连通性
- 对私有网关检查兼容的 OpenAI 协议字段

## 症状 4：配置保存异常

- 确认 JSON 结构合法
- 避免将掩码值当成真实密钥提交（后端已做恢复保护）
- 看接口返回中的 schema error 详情

## 症状 5：stop 后立刻追问，内容串写到新消息

- 前端流式状态更新应锚定“本轮 assistant 消息 id”，不要依赖“最后一条消息”。
- 在 stop 后保留被中断 partial，可作为下一轮“否定信息”输入上下文。
- 如果偶发串写，检查是否有延迟到达的旧 run 事件未按消息 id 过滤。

## 下一步

- `../configuration/index.md`
- `../api/reference.md`
