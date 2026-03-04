#!/usr/bin/env node
import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const desktopDir = path.resolve(__dirname, "..");
const repoDir = path.resolve(desktopDir, "..");

function checkCommand(cmd, args = ["--version"]) {
  const res = spawnSync(cmd, args, { stdio: "pipe", encoding: "utf-8" });
  if (res.status === 0) {
    const out = (res.stdout || res.stderr || "").trim().split("\n")[0];
    return { ok: true, detail: out || "ok" };
  }
  return { ok: false, detail: (res.stderr || res.stdout || "not found").trim() };
}

function checkPath(relativePath) {
  const full = path.resolve(repoDir, relativePath);
  return { ok: existsSync(full), full };
}

const checks = [
  { name: "node", result: checkCommand("node") },
  { name: "npm", result: checkCommand("npm") },
  { name: "python3", result: checkCommand("python3") },
  { name: "python", result: checkCommand("python") },
  { name: "rustc", result: checkCommand("rustc") },
  { name: "cargo", result: checkCommand("cargo") },
  { name: "backend/cli.py", result: checkPath("backend/cli.py") },
  { name: "frontend/package.json", result: checkPath("frontend/package.json") },
  { name: "desktop/src-tauri/Cargo.toml", result: checkPath("desktop/src-tauri/Cargo.toml") },
];

console.log("ClawChain Desktop Doctor");
console.log("========================");

let allOk = true;
for (const item of checks) {
  const ok = item.result.ok;
  allOk = allOk && ok;
  const icon = ok ? "[OK]" : "[FAIL]";
  const detail = item.result.detail || item.result.full || "";
  console.log(`${icon} ${item.name} ${detail ? `- ${detail}` : ""}`);
}

console.log("\nTips:");
console.log("- Development: npm run dev");
console.log("- Frontend build: npm run build:frontend");
console.log("- Tauri build: npm run build:tauri");

if (!allOk) {
  process.exitCode = 1;
}
