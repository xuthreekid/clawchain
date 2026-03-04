const API_BASE = typeof window !== "undefined"
  ? `http://${window.location.hostname}:8002/api`
  : "http://localhost:8002/api";

export interface SSEEvent {
  type: string;
  content?: string;
  tool?: string;
  name?: string;
  input?: any;
  input_preview?: string;
  args?: any;
  output?: string;
  error?: string;
  session_id?: string;
  title?: string;
  query?: string;
  results?: any[];
  response?: string;
  event?: string;
  run_id?: string;
  usage?: TokenUsage;
  result?: any;
  approval_id?: string;
}

export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  duration_ms: number;
}

export interface AgentStatus {
  agent_id: string;
  total_turns: number;
  total_input_tokens: number;
  total_output_tokens: number;
  compaction_count: number;
  thinking: boolean;
  verbose: boolean;
  reasoning: boolean;
  last_active: number;
  heartbeat_active: boolean;
}

export interface InitStatus {
  file_initialized: boolean;
  config_ready: boolean;
  providers_count: number;
  valid_providers_count: number;
  default_model: string | null;
  missing: string[];
}

async function readErrorMessage(resp: Response): Promise<string> {
  const fallback = `Request failed: ${resp.status}`;
  try {
    const data = await resp.json();
    if (typeof data?.detail === "string" && data.detail) return data.detail;
    if (typeof data?.error === "string" && data.error) return data.error;
    if (typeof data?.message === "string" && data.message) return data.message;
    return fallback;
  } catch {
    return fallback;
  }
}

/** Get chat timeout config. timeoutSeconds=0 means no timeout */
export async function fetchChatTimeout(): Promise<{ timeoutSeconds: number }> {
  const resp = await fetch(`${API_BASE}/config/chat`);
  return resp.json();
}

export async function streamChat(
  message: string,
  sessionId: string,
  agentId: string,
  onEvent: (event: SSEEvent) => void,
  opts?: { signal?: AbortSignal; timeoutMs?: number },
): Promise<void> {
  const { signal: userSignal, timeoutMs } = opts ?? {};
  const controller = new AbortController();
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  let timeoutFired = false;
  if (timeoutMs != null && timeoutMs > 0) {
    timeoutId = setTimeout(() => {
      timeoutFired = true;
      controller.abort();
    }, timeoutMs);
  }
  if (userSignal) {
    userSignal.addEventListener("abort", () => {
      if (timeoutId) clearTimeout(timeoutId);
      controller.abort();
    });
  }
  const effectiveSignal = controller.signal;

  async function consumeStream(reader: ReadableStreamDefaultReader<Uint8Array>) {
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        if (buffer.trim()) {
          const remaining = buffer.trim();
          if (remaining.startsWith("data: ")) {
            try {
              const parsed = JSON.parse(remaining.slice(6)) as SSEEvent;
              onEvent(parsed);
            } catch {
              // ignore
            }
          }
        }
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const parsed = JSON.parse(line.slice(6)) as SSEEvent;
            onEvent(parsed);
          } catch {
            // ignore
          }
        }
      }
    }
  }

  try {
    const resp = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId, agent_id: agentId, stream: true }),
      signal: effectiveSignal,
    });
    if (!resp.ok) throw new Error(`Chat failed: ${resp.status}`);
    const reader = resp.body?.getReader();
    if (!reader) throw new Error("No response body");
    await consumeStream(reader);
  } catch (e) {
    if (timeoutFired && e instanceof Error && e.name === "AbortError") {
      throw new Error(`Request timeout (${Math.round((timeoutMs ?? 0) / 1000)}s)`);
    }
    throw e;
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

export async function abortChat(
  agentId: string,
  sessionId: string,
  opts?: { clearFollowups?: boolean },
): Promise<{ aborted: boolean; pending_followups: number; cleared_followups: number }> {
  const resp = await fetch(`${API_BASE}/chat/abort`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      agent_id: agentId,
      session_id: sessionId,
      clear_followups: Boolean(opts?.clearFollowups),
    }),
  });
  if (!resp.ok) {
    throw new Error(await readErrorMessage(resp));
  }
  return resp.json();
}

// ---------- REST API ----------

export async function fetchAgents(): Promise<any[]> {
  const resp = await fetch(`${API_BASE}/agents`);
  return resp.json();
}

export async function createAgent(data: { id: string; name: string; description?: string; model?: string }) {
  const resp = await fetch(`${API_BASE}/agents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error((err as any)?.detail || `Create failed: ${resp.status}`);
  }
  return resp.json();
}

export async function deleteAgent(agentId: string) {
  const resp = await fetch(`${API_BASE}/agents/${agentId}`, { method: "DELETE" });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error((err as any)?.detail || `Delete failed: ${resp.status}`);
  }
  return resp.json();
}

export async function fetchAgentStatus(agentId: string): Promise<AgentStatus> {
  const resp = await fetch(`${API_BASE}/agents/${agentId}/status`);
  return resp.json();
}

export async function fetchAgentUsage(agentId: string, sessionId?: string): Promise<any> {
  const params = sessionId ? `?session_id=${sessionId}` : "";
  const resp = await fetch(`${API_BASE}/agents/${agentId}/usage${params}`);
  return resp.json();
}

export async function fetchAuditLog(agentId: string, limit: number = 50): Promise<any[]> {
  const resp = await fetch(`${API_BASE}/agents/${agentId}/audit-log?limit=${limit}`);
  return resp.json();
}

export async function fetchHeartbeatConfig(agentId: string): Promise<{ enabled: boolean; every: string; interval_seconds?: number }> {
  const resp = await fetch(`${API_BASE}/agents/${agentId}/heartbeat/config`);
  if (!resp.ok) throw new Error("Failed to fetch heartbeat config");
  return resp.json();
}

export async function fetchHeartbeatHistory(agentId: string, limit: number = 30): Promise<any[]> {
  const resp = await fetch(`${API_BASE}/agents/${agentId}/heartbeat/history?limit=${limit}`);
  return resp.json();
}

export async function updateHeartbeatEnabled(enabled: boolean): Promise<void> {
  await updateConfig({
    agents: {
      defaults: {
        heartbeat: { enabled },
      },
    },
  });
}

export async function resolveApproval(approvalId: string, decision: "approved" | "denied"): Promise<void> {
  const resp = await fetch(`${API_BASE}/approvals/${approvalId}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error((err as any)?.detail || `Confirm failed: ${resp.status}`);
  }
}

export async function fetchCronJobs(): Promise<any[]> {
  const resp = await fetch(`${API_BASE}/cron/jobs`);
  return resp.json();
}

export async function createCronJob(body: {
  name: string;
  description?: string;
  agent_id?: string;
  enabled?: boolean;
  deleteAfterRun?: boolean;
  schedule: { kind?: string; at?: string; everyMs?: number; expr?: string; tz?: string };
  payload: { kind: string; text: string };
}) {
  const resp = await fetch(`${API_BASE}/cron/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`Create failed: ${resp.status}`);
  return resp.json();
}

export async function updateCronJob(jobId: string, body: Partial<{ name: string; description: string; agent_id: string; enabled: boolean; schedule: any; payload: any }>) {
  const resp = await fetch(`${API_BASE}/cron/jobs/${jobId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`Update failed: ${resp.status}`);
  return resp.json();
}

export async function deleteCronJob(jobId: string) {
  const resp = await fetch(`${API_BASE}/cron/jobs/${jobId}`, { method: "DELETE" });
  if (!resp.ok) throw new Error(`Delete failed: ${resp.status}`);
  return resp.json();
}

export async function runCronJob(jobId: string) {
  const resp = await fetch(`${API_BASE}/cron/jobs/${jobId}/run`, { method: "POST" });
  if (!resp.ok) throw new Error(`Trigger failed: ${resp.status}`);
  return resp.json();
}

// --- Main Session API ---

export async function fetchMainSession(agentId: string) {
  const resp = await fetch(`${API_BASE}/agents/${agentId}/session`);
  return resp.json();
}

export async function fetchMainSessionMessages(agentId: string) {
  const resp = await fetch(`${API_BASE}/agents/${agentId}/session/messages`);
  return resp.json();
}

export async function resetMainSession(agentId: string) {
  const resp = await fetch(`${API_BASE}/agents/${agentId}/session/reset`, {
    method: "POST",
  });
  return resp.json();
}

// --- Model API ---

export async function fetchModels() {
  const resp = await fetch(`${API_BASE}/models`);
  return resp.json();
}

export async function fetchCurrentModel(agentId: string) {
  const resp = await fetch(`${API_BASE}/models/current/${agentId}`);
  return resp.json();
}

export async function switchModel(agentId: string, model: string, scope: "agent" | "default" = "agent") {
  const resp = await fetch(`${API_BASE}/models/switch/${agentId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, scope }),
  });
  if (!resp.ok) throw new Error(await readErrorMessage(resp));
  const data = await resp.json();
  if (data?.status === "error") {
    throw new Error(data?.error || "Model switch failed");
  }
  return data;
}

export async function updateSecrets(path: string, value: string) {
  const resp = await fetch(`${API_BASE}/config/secrets`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, value }),
  });
  if (!resp.ok) throw new Error(`Update failed: ${resp.status}`);
  return resp.json();
}

export async function fetchRawConfig(): Promise<any> {
  const resp = await fetch(`${API_BASE}/config/raw`);
  if (!resp.ok) throw new Error(await readErrorMessage(resp));
  return resp.json();
}

// --- Legacy API compat ---

export async function fetchSessions(agentId: string): Promise<any[]> {
  const resp = await fetch(`${API_BASE}/agents/${agentId}/sessions`);
  return resp.json();
}

export async function fetchHistory(agentId: string, sessionId: string) {
  const resp = await fetch(`${API_BASE}/agents/${agentId}/sessions/${sessionId}/history`);
  return resp.json();
}

export async function fetchMessages(agentId: string, sessionId: string) {
  const resp = await fetch(`${API_BASE}/agents/${agentId}/sessions/${sessionId}/messages`);
  return resp.json();
}

export async function readFile(agentId: string, path: string): Promise<{ path: string; content: string }> {
  const resp = await fetch(`${API_BASE}/agents/${agentId}/files?path=${encodeURIComponent(path)}`);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error((err as any)?.detail || `Read failed: ${resp.status}`);
  }
  return resp.json();
}

export async function saveFile(agentId: string, path: string, content: string) {
  return fetch(`${API_BASE}/agents/${agentId}/files`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, content }),
  });
}

export async function fetchSkills(agentId: string): Promise<any[]> {
  const resp = await fetch(`${API_BASE}/agents/${agentId}/skills`);
  return resp.json();
}

export interface ToolItem {
  name: string;
  description: string;
  category: string;
  allowed: boolean;
}

export async function fetchTools(agentId: string): Promise<ToolItem[]> {
  const resp = await fetch(`${API_BASE}/agents/${agentId}/tools`);
  return resp.json();
}

export async function updateToolPolicy(agentId: string, toolName: string, allowed: boolean): Promise<{ status: string; config: any }> {
  const resp = await fetch(`${API_BASE}/config/tools-policy`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent_id: agentId, tool_name: toolName, allowed }),
  });
  if (!resp.ok) throw new Error(`Update failed: ${resp.status}`);
  return resp.json();
}

export async function fetchToolsCatalog(): Promise<{ tools: string[] }> {
  const resp = await fetch(`${API_BASE}/tools/catalog`);
  return resp.json();
}

export interface SubagentTreeItem {
  run_id: string;
  label: string;
  task: string;
  target_agent_id: string;
  status: string;
  state?: "running" | "succeeded" | "failed" | "cancelled" | "timed_out" | "interrupted" | "orphaned";
  terminal_reason?: string | null;
  elapsed: number | null;
  duration_ms?: number | null;
  started_at?: number | null;
  ended_at?: number | null;
  result_summary: string;
  messages: { role: string; content: string; tool_calls?: any[] }[];
  created_at: number;
  spawn_depth?: number;
  requester_session_key?: string;
  child_session_key?: string;
  announce_state?: "pending" | "retrying" | "delivered" | "dropped";
  announce_retry_count?: number;
  archive_at_ms?: number | null;
  descendants_active_count?: number;
  children?: SubagentTreeItem[];
}

export interface SubagentsResponse {
  tree: SubagentTreeItem[];
  flat: SubagentTreeItem[];
  include_recent_minutes?: number;
}

export async function fetchSubagents(
  agentId: string,
  sessionId?: string,
  includeRecentMinutes?: number
): Promise<SubagentsResponse> {
  const search = new URLSearchParams();
  if (sessionId) search.set("session_id", sessionId);
  if (includeRecentMinutes != null && includeRecentMinutes > 0) {
    search.set("include_recent_minutes", String(includeRecentMinutes));
  }
  const params = search.toString() ? `?${search}` : "";
  const resp = await fetch(`${API_BASE}/agents/${agentId}/subagents${params}`);
  const data = await resp.json();
  if (Array.isArray(data)) {
    return { tree: data, flat: data };
  }
  return data;
}

export async function killSubagent(
  agentId: string,
  target: string,
  sessionId?: string,
): Promise<{ ok: boolean;[k: string]: any }> {
  const resp = await fetch(`${API_BASE}/agents/${agentId}/subagents/kill`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target, session_id: sessionId }),
  });
  return resp.json();
}

export async function steerSubagent(
  agentId: string,
  runId: string,
  message: string,
): Promise<{ ok: boolean;[k: string]: any }> {
  const resp = await fetch(`${API_BASE}/agents/${agentId}/subagents/steer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: runId, message }),
  });
  return resp.json();
}

export function subscribeAgentEvents(
  agentId: string,
  onEvent: (event: SSEEvent) => void,
  onError?: (error: unknown) => void,
): () => void {
  const url = `${API_BASE}/agents/${agentId}/events`;
  const es = new EventSource(url);

  es.onmessage = (evt) => {
    try {
      const parsed = JSON.parse(evt.data) as SSEEvent;
      onEvent(parsed);
    } catch {
      // ignore malformed events
    }
  };

  es.onerror = (err) => {
    onError?.(err);
  };

  return () => {
    es.close();
  };
}

export async function compressSession(agentId: string, sessionId: string) {
  const resp = await fetch(`${API_BASE}/agents/${agentId}/sessions/${sessionId}/compress`, {
    method: "POST",
  });
  return resp.json();
}

export async function resetSession(agentId: string, sessionId: string) {
  const resp = await fetch(`${API_BASE}/agents/${agentId}/sessions/${sessionId}/reset`, {
    method: "POST",
  });
  return resp.json();
}

export async function fetchConfig(): Promise<any> {
  const resp = await fetch(`${API_BASE}/config`);
  return resp.json();
}

export async function fetchConfigPath(): Promise<{ path: string }> {
  const resp = await fetch(`${API_BASE}/config/path`);
  return resp.json();
}

export async function fetchInitStatus(): Promise<InitStatus> {
  const resp = await fetch(`${API_BASE}/init/status`);
  if (!resp.ok) throw new Error(await readErrorMessage(resp));
  return resp.json();
}

export async function replaceConfig(config: Record<string, any>): Promise<any> {
  const resp = await fetch(`${API_BASE}/config/replace`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config }),
  });
  if (!resp.ok) throw new Error(await readErrorMessage(resp));
  return resp.json();
}

export async function updateConfig(updates: Record<string, any>): Promise<any> {
  const resp = await fetch(`${API_BASE}/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ updates }),
  });
  if (!resp.ok) throw new Error(await readErrorMessage(resp));
  return resp.json();
}

export async function updateRagMode(enabled: boolean) {
  return updateConfig({ rag_mode: enabled });
}

export async function updateSkillEnabled(agentId: string, skillName: string, enabled: boolean) {
  const resp = await fetch(`${API_BASE}/agents/${agentId}/skills`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ skill_name: skillName, enabled }),
  });
  if (!resp.ok) throw new Error(`Update failed: ${resp.status}`);
  return resp.json();
}
