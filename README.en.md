<div align="center">
  <img src="images/clawchain_logo.png" alt="ClawChain" width="400">
  <h1>ClawChain</h1>
  <p>
    <img src="https://img.shields.io/badge/python-≥3.11-blue" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>
</div>

---

**ClawChain** is a tribute to [OpenClaw](https://github.com/openclaw/openclaw) — a local AI agent engineering project built with LangChain / LangGraph.

**Positioning**: local-first, engineering-oriented, centered around Web + Desktop workflows.

[中文](README.zh-CN.md) | [中文详细版](README.md)

---

## 🏗️ Architecture

<p align="center">
  <img src="images/clawchain_arch.png" alt="ClawChain Architecture" width="800">
</p>

---

## ✨ UI Showcase

<table align="center">
  <tr align="center">
    <th><p align="center">🤖 Agent Self-Intro</p></th>
    <th><p align="center">🔀 Sub-Agent Collaboration</p></th>
    <th><p align="center">📊 Structured Report</p></th>
  </tr>
  <tr>
    <td align="center"><p align="center"><img src="images/screenshot-agent-intro.png" width="280" alt="Agent intro"></p></td>
    <td align="center"><p align="center"><img src="images/screenshot-subagents.png" width="280" alt="Sub-agents"></p></td>
    <td align="center"><p align="center"><img src="images/screenshot-report.png" width="280" alt="Report"></p></td>
  </tr>
  <tr>
    <td align="center">File read, identity, tool calls</td>
    <td align="center">Parallel sub-agents & Inspector panel</td>
    <td align="center">Brand news & sentiment report</td>
  </tr>
</table>

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+ · FastAPI · LangChain / LangGraph |
| Frontend | Next.js · React · TypeScript |
| Desktop | Tauri 2.0 · Rust (tray/window shell) |
| Storage | Local filesystem (sessions/memory/config) |

---

## Quick Start

### 1) One-command dev start (recommended)

```bash
python scripts/dev.py
```

First run: configure via Web UI after startup, or run `cd backend && python cli.py onboard` first.

Common options:

```bash
python scripts/dev.py --skip-install
python scripts/dev.py --backend-only
python scripts/dev.py --frontend-only
```

### 2) Backend only

```bash
cd backend
pip install -r requirements.txt
python cli.py start
```

Optional: use parameters for a non-interactive quick start

```bash
python cli.py start --provider deepseek --api-key "sk-xxx" --model deepseek-chat --doctor
```

### 3) Start frontend

```bash
cd frontend
npm install
npm run dev
```

Open: <http://localhost:3000>

---

## Core Capabilities

### Agents and Sessions

- Isolated workspaces per agent (config, sessions, memory, skills)
- Session management and slash commands (`/new`, `/compact`, `/status`)
- Sub-agent orchestration (`sessions_spawn` / `subagents`)

### Memory and Scheduling

- Memory writes and retrieval (`MEMORY.md` + `memory/*.md`)
- Heartbeat background checks with silent ACK (`HEARTBEAT_OK`)
- Cron scheduling and reminder delivery

### Tools and Safety

- File, command, web, memory, and session toolchain
- Path and execution constraints through policy/config
- Approval APIs for high-risk operations

### Config and Observability

- Config center (models, tool policies, runtime behavior)
- Event streams and status APIs (SSE + REST)
- Runbook docs (setup, troubleshooting, cleanup)

---

## Desktop (macOS Alpha)

`desktop/` already provides a runnable alpha:

- Tray resident mode (show window / quit)
- Hide to background on close
- Sidecar dual-path startup (bundled sidecar first, Python fallback)
- Backend readiness probe (`/api/health`)

Run it:

```bash
cd desktop
npm install
npm run doctor
npm run dev
```

Build verification:

```bash
cd desktop
npm run build:frontend
npm run build:tauri
```

Note: this is an engineering alpha.

---

## Documentation

- Docs hub: `docs/index.md`
- Getting started: `docs/start/getting-started.md`
- Configuration: `docs/configuration/index.md`
- Agent architecture: `docs/agents/architecture.md`
- Prompt and memory: `docs/agents/prompt-memory.md`
- API reference: `docs/api/reference.md`

## License

MIT
