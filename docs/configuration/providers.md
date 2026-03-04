# Provider 与模型配置

> summary: 为 OpenAI/Anthropic/DeepSeek/OpenRouter/Ollama 配置最小可运行模型  
> read_when: 你要切换模型厂商或新增模型

## 目标

用统一结构配置多家模型服务，并让前端可直接选择。

## 最小示例

```json
{
  "models": {
    "providers": {
      "openai": {
        "baseUrl": "https://api.openai.com/v1",
        "apiKey": "${OPENAI_API_KEY}",
        "api": "openai-completions",
        "models": [
          { "id": "gpt-4o-mini", "name": "GPT-4o Mini", "contextWindow": 128000, "maxTokens": 16384 }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": "openai/gpt-4o-mini"
    }
  }
}
```

## 厂商差异

- OpenAI / DeepSeek / OpenRouter：通常使用 `openai-completions`。
- Anthropic：使用 `anthropic-messages`。
- Ollama：本地推理，`baseUrl` 常见为 `http://localhost:11434`。

## 常见错误与修复

- 401：`apiKey` 错误或未替换环境变量。
- 404 model not found：`model.id` 与厂商端实际 ID 不一致。
- 前端下拉无模型：检查 provider 下 `models` 数组是否为空。

## 下一步

- `../start/getting-started.md`
- `../help/troubleshooting.md`
