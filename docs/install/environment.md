# 环境与依赖

> summary: 安装运行 ClawChain 所需环境并准备 `.env`  
> read_when: 安装阶段、升级依赖阶段

## 目标

建立稳定的本地运行环境，避免“装得上但跑不起来”。

## 前置条件

- macOS / Linux / Windows（WSL）

## 最小步骤

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
```

```bash
cd frontend
npm install
```

## 配置建议

- 在 `.env` 中维护密钥，`config.json` 使用 `${ENV_VAR}` 引用。
- 项目环境变量前缀统一为 `CLAWCHAIN_*`。

## 常见错误与修复

- `npm` 安装失败：优先使用 Node.js 20 LTS。
- `pip` 编译失败：升级 `pip setuptools wheel` 后重试。
- 环境变量不生效：确认后端启动目录为 `backend/` 且 `.env` 位于该目录。

## 下一步

- `../configuration/index.md`
