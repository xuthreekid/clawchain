# Agent 架构

> summary: 解释 ClawChain 的 LangGraph 执行流与前后端协同  
> read_when: 你要理解 `/chat` 流式处理、工具调用和子 Agent 机制

## 目标

理解一条用户消息如何从前端进入后端并产出 SSE 事件。

## 执行流（简化）

1. 前端 `streamChat` 发起请求并监听 SSE。
2. 后端按 `agent_id + session_id` 获取会话队列；忙碌则 followup 排队。
3. 后端 Agent 装配系统提示（prompt_builder + 工作区模板）。
4. 进入 LangGraph 执行：模型推理 -> 工具调用 -> 事件上报。
5. 前端根据 token/tool/lifecycle 事件实时渲染消息与 Inspector。
6. 用户主动停止时，前端调用 `/api/chat/abort`，后端取消 active run 并下发 `aborted`。

## 关键组件

- `backend/graph/agent.py`：会话、命令、工具调度核心
- `backend/graph/message_queue.py`：会话级串行与 followup 队列
- `backend/graph/prompt_builder.py`：full/minimal/none prompt 分层
- `backend/api/chat.py`：SSE 编排、中断事件与终态返回
- `frontend/src/lib/hooks/useChat.ts`：流式状态机、stop/abort 协同与异常回补
- `frontend/src/components/inspector/*`：运行态可视化

## 常见错误与修复

- 工具事件不闭合：检查 SSE `done` 或 `aborted` 是否收到，必要时前端会自动回补加载。
- `/new` 慢：当前采用后台异步记忆写入与索引重建，不阻塞主链路。
- stop 后立刻追问串写：前端应按当前流消息 id 更新，不应仅按最后一条消息更新。
- 子 Agent 状态不一致：查看 Inspector 事件和 `subagents list`。

## 下一步

- `prompt-memory.md`
- `../api/reference.md`
