export type Locale = "zh-CN" | "en-US";

export interface Messages {
  // App chrome
  appName: string;
  settings: string;
  close: string;
  save: string;
  cancel: string;
  confirm: string;
  delete: string;
  refresh: string;
  search: string;
  loading: string;

  // Inspector tabs
  tabFiles: string;
  tabTools: string;
  tabSkills: string;
  tabSubagents: string;
  tabHeartbeat: string;
  tabTasks: string;

  // Skills panel
  skillsManagement: string;
  skillsEnabled: string;
  searchSkills: string;
  noSkills: string;
  noMatchSkills: string;
  statusAvailable: string;
  statusMissingDeps: string;
  statusInvalid: string;
  missingLabel: string;
  alwaysEnabled: string;
  clickToDisable: string;
  clickToEnable: string;

  // Task dashboard
  taskHistory: string;
  taskItems: string;
  allTypes: string;
  allStatus: string;
  noTasks: string;
  heartbeat: string;
  cron: string;
  reminder: string;
  system: string;
  success: string;
  failed: string;
  running: string;
  pending: string;
  cancelled: string;
  retrying: string;
  retry: string;

  // Approval modal
  approvalTitle: string;
  approvalDesc: string;
  approvalDangerWarn: string;
  approve: string;
  deny: string;
  confirmExec: string;
  riskSafe: string;
  riskCaution: string;
  riskDanger: string;
  toolExec: string;
  toolProcessKill: string;
  toolWrite: string;
  toolEdit: string;
  toolDelete: string;
  toolApplyPatch: string;
  toolPythonRepl: string;

  // Config sections
  configCenter: string;
  configSandbox: string;
  configNotifications: string;
  configRuntime: string;
  configBrowser: string;
  configBackup: string;
  configSkills: string;
  configApp: string;
  configAdvanced: string;

  // AgentCard / Config form
  inheritDefault: string;
  heartbeatEnabled: string;
  heartbeatInterval: string;
  toolsAllow: string;
  toolsDeny: string;
  heartbeatOverride: string;
  toolsPolicyOverride: string;
  commaSeparatedEmptyInherit: string;
  commaSeparatedPreferAllow: string;
  writeApprovalLabel: string;
  writeApprovalOff: string;
  writeApprovalOnOverwrite: string;
  writeApprovalAlways: string;
  configUpdateFailed: string;

  // Exec approval
  execConfirmLabel: string;
  execConfirmOff: string;
  execConfirmOnMiss: string;
  execConfirmAlways: string;
  execConfirmHint: string;

  // Chat
  inputPlaceholder: string;
  sendHint: string;
  denied: string;
  commandPaletteTitle: string;
  cmdNewDesc: string;
  cmdResetDesc: string;
  cmdCompactDesc: string;
  cmdHelpDesc: string;
  cmdStatusDesc: string;
  cmdContextDesc: string;
  cmdUsageDesc: string;
  cmdThinkDesc: string;
  cmdVerboseDesc: string;
  cmdReasoningDesc: string;
  cmdModelDesc: string;
  cmdSubagentsDesc: string;
  cmdWhoamiDesc: string;
  cmdStopDesc: string;
  cmdResetProgressWithMemory: string;
  cmdResetProgressNoMemory: string;
  cmdResetDoneWithMemory: string;
  cmdResetDoneQueued: string;
  cmdResetDoneNoMemory: string;
  cmdCompactProgress: string;
  cmdCompactDone: string;
  cmdCompactSkipped: string;
  cmdCompactFailed: string;
  cmdCompactReasonTooFewMessages: string;
  cmdCompactReasonNoEnoughCompressible: string;
  cmdCompactReasonSessionMissing: string;
  commandNoticeTitle: string;
  helpListTitle: string;

  // Tools tab
  toolsTitle: string;
  categoryFile: string;
  categoryRuntime: string;
  categoryWeb: string;
  categoryMemory: string;
  categoryKnowledge: string;
  categoryAgent: string;
  categoryStatus: string;
  categoryOther: string;
  keyFiles: string;
  clickFileToEdit: string;

  // Subagent
  noSubagents: string;
  subagentCount: string;
  confirmKillSubagents: string;
  killedSubagents: string;
  confirmKillOne: string;
  noReply: string;
  parsingTools: string;

  // Heartbeat
  heartbeatAndCron: string;
  heartbeatLabel: string;
  noHeartbeatRecords: string;
  heartbeatStatusOn: string;
  heartbeatStatusOff: string;
  heartbeatIntervalLabel: string;
  clearedClickRefresh: string;
  cronTasks: string;
  taskName: string;
  oneTimeTask: string;
  presetCron: string;
  intervalCron: string;
  noCronTasks: string;
  enabled: string;
  disabled: string;

  // ChatPanel
  agentDescription: string;
  generating: string;

  runtimeEvents: string;

  // EventTimeline 运行时事件
  evtTurnStart: string;
  evtTurnEnd: string;
  evtTurnError: string;
  evtToolStart: string;
  evtToolEnd: string;
  evtAutoCompactStart: string;
  evtAutoCompactDone: string;
  evtRecursionLimit: string;
  evtMemorySaved: string;
  evtMemoryFailed: string;
  evtNoEvents: string;
  evtFilterAll: string;
  evtFilterMemory: string;
  evtFilterError: string;
  evtNoFilteredEvents: string;
}

export const zhCN: Messages = {
  appName: "ClawChain",
  settings: "配置中心",
  close: "关闭",
  save: "保存",
  cancel: "取消",
  confirm: "确认",
  delete: "删除",
  refresh: "刷新",
  search: "搜索",
  loading: "加载中...",

  tabFiles: "文件",
  tabTools: "工具",
  tabSkills: "技能",
  tabSubagents: "子Agent",
  tabHeartbeat: "心跳",
  tabTasks: "任务",

  skillsManagement: "技能管理",
  skillsEnabled: "已启用",
  searchSkills: "搜索技能...",
  noSkills: "暂无技能包",
  noMatchSkills: "未找到匹配的技能",
  statusAvailable: "可用",
  statusMissingDeps: "缺依赖",
  statusInvalid: "无效",
  missingLabel: "缺少",
  alwaysEnabled: "此技能始终启用",
  clickToDisable: "点击禁用",
  clickToEnable: "点击启用",

  taskHistory: "任务历史",
  taskItems: "条",
  allTypes: "全部类型",
  allStatus: "全部状态",
  noTasks: "暂无任务记录",
  heartbeat: "心跳",
  cron: "定时",
  reminder: "提醒",
  system: "系统",
  success: "成功",
  failed: "失败",
  running: "运行中",
  pending: "等待中",
  cancelled: "已取消",
  retrying: "重试中",
  retry: "重试",

  approvalTitle: "执行前确认",
  approvalDesc: "Agent 请求执行",
  approvalDangerWarn: "此操作可能修改系统状态或造成不可逆影响，请仔细确认。",
  approve: "批准",
  deny: "拒绝",
  confirmExec: "确认执行",
  riskSafe: "安全操作",
  riskCaution: "文件变更确认",
  riskDanger: "高危操作警告",
  toolExec: "Shell 命令",
  toolProcessKill: "终止进程",
  toolWrite: "写入文件",
  toolEdit: "编辑文件",
  toolDelete: "删除文件",
  toolApplyPatch: "应用补丁",
  toolPythonRepl: "Python 代码",

  configCenter: "配置中心",
  configSandbox: "沙箱安全",
  configNotifications: "通知",
  inheritDefault: "继承默认",
  heartbeatEnabled: "启用心跳",
  heartbeatInterval: "检查间隔",
  toolsAllow: "允许 (allow)",
  toolsDeny: "禁止 (deny)",
  heartbeatOverride: "心跳覆盖",
  toolsPolicyOverride: "工具策略覆盖",
  commaSeparatedEmptyInherit: "逗号分隔，为空继承全局",
  commaSeparatedPreferAllow: "逗号分隔，优先于 allow",
  writeApprovalLabel: "写入审批策略",
  writeApprovalOff: "关闭",
  writeApprovalOnOverwrite: "覆盖时确认",
  writeApprovalAlways: "始终确认",
  configUpdateFailed: "更新 Agent 配置失败",
  execConfirmLabel: "exec 命令确认",
  execConfirmOff: "关闭 — 直接执行，不弹确认",
  execConfirmOnMiss: "白名单外需确认（推荐）",
  execConfirmAlways: "始终确认",
  execConfirmHint: "exec / process_kill 执行前是否需用户确认",
  configRuntime: "运行时",
  configBrowser: "浏览器自动化",
  configBackup: "备份",
  configSkills: "技能包",
  configApp: "应用设置",
  configAdvanced: "高级设置",

  inputPlaceholder: "输入消息... / 输入斜杠查看命令",
  sendHint: "Enter 发送 · Shift+Enter 换行 · /命令",
  denied: "已拒绝执行该操作",
  commandPaletteTitle: "命令",
  cmdNewDesc: "重置会话（写入长期记忆）",
  cmdResetDesc: "重置会话（不写入长期记忆）",
  cmdCompactDesc: "压缩历史",
  cmdHelpDesc: "显示帮助",
  cmdStatusDesc: "Agent 状态",
  cmdContextDesc: "上下文使用",
  cmdUsageDesc: "Token 使用量与费用估算",
  cmdThinkDesc: "深度思考",
  cmdVerboseDesc: "详细输出",
  cmdReasoningDesc: "显示/隐藏推理过程",
  cmdModelDesc: "查看/切换模型",
  cmdSubagentsDesc: "子 Agent 列表",
  cmdWhoamiDesc: "身份信息",
  cmdStopDesc: "停止生成",
  cmdResetProgressWithMemory: "正在重置会话并写入长期记忆，可能需要数秒…",
  cmdResetProgressNoMemory: "正在重置会话（不写入长期记忆）…",
  cmdResetDoneWithMemory: "会话已重置。",
  cmdResetDoneQueued: "长期记忆将后台保存。",
  cmdResetDoneNoMemory: "会话已重置（本轮对话未写入长期记忆）。",
  cmdCompactProgress: "正在执行压缩...",
  cmdCompactDone: "压缩完成。",
  cmdCompactSkipped: "压缩未执行。",
  cmdCompactFailed: "压缩失败。",
  cmdCompactReasonTooFewMessages: "消息过少，无需压缩",
  cmdCompactReasonNoEnoughCompressible: "无足够消息可压缩",
  cmdCompactReasonSessionMissing: "会话不存在",
  commandNoticeTitle: "系统提示",
  helpListTitle: "可用命令",

  toolsTitle: "Function Call 工具",
  categoryFile: "文件",
  categoryRuntime: "运行时",
  categoryWeb: "网络",
  categoryMemory: "记忆",
  categoryKnowledge: "知识库",
  categoryAgent: "Agent / 会话",
  categoryStatus: "状态",
  categoryOther: "其他",
  keyFiles: "关键文件",
  clickFileToEdit: "点击文件查看和编辑",

  noSubagents: "暂无子 Agent",
  subagentCount: "子Agent",
  confirmKillSubagents: "确认终止当前会话树下的 {count} 个运行中子Agent？",
  killedSubagents: "已终止 {count} 个子Agent",
  confirmKillOne: "确认终止子Agent {id}？",
  noReply: "暂无回复",
  parsingTools: "正在解析工具调用...",

  heartbeatAndCron: "心跳与定时",
  heartbeatLabel: "心跳",
  noHeartbeatRecords: "暂无心跳记录",
  heartbeatStatusOn: "心跳检查已开启",
  heartbeatStatusOff: "心跳检查已关闭",
  heartbeatIntervalLabel: "检查间隔",
  clearedClickRefresh: "已清空，点击刷新可重新加载",
  cronTasks: "定时任务",
  taskName: "任务名称",
  oneTimeTask: "临时任务（一次性）",
  presetCron: "周期任务（预设）",
  intervalCron: "周期任务（间隔）",
  noCronTasks: "暂无定时任务",
  enabled: "启用",
  disabled: "禁用",

  agentDescription: "具有工具调用、长期记忆和子 Agent 协同能力的 AI 助手",
  generating: "生成中",

  runtimeEvents: "运行时事件",
  evtTurnStart: "回合开始",
  evtTurnEnd: "回合结束",
  evtTurnError: "回合错误",
  evtToolStart: "工具开始",
  evtToolEnd: "工具结束",
  evtAutoCompactStart: "自动压缩开始",
  evtAutoCompactDone: "自动压缩完成",
  evtRecursionLimit: "递归限制",
  evtMemorySaved: "记忆已保存",
  evtMemoryFailed: "记忆保存失败",
  evtNoEvents: "暂无运行时事件",
  evtFilterAll: "全部",
  evtFilterMemory: "记忆",
  evtFilterError: "错误",
  evtNoFilteredEvents: "无匹配事件",
};

export const enUS: Messages = {
  appName: "ClawChain",
  settings: "Settings",
  close: "Close",
  save: "Save",
  cancel: "Cancel",
  confirm: "Confirm",
  delete: "Delete",
  refresh: "Refresh",
  search: "Search",
  loading: "Loading...",

  tabFiles: "Files",
  tabTools: "Tools",
  tabSkills: "Skills",
  tabSubagents: "Subagents",
  tabHeartbeat: "Heartbeat",
  tabTasks: "Tasks",

  skillsManagement: "Skills Management",
  skillsEnabled: "enabled",
  searchSkills: "Search skills...",
  noSkills: "No skills available",
  noMatchSkills: "No matching skills",
  statusAvailable: "Available",
  statusMissingDeps: "Missing Deps",
  statusInvalid: "Invalid",
  missingLabel: "Missing",
  alwaysEnabled: "Always enabled",
  clickToDisable: "Click to disable",
  clickToEnable: "Click to enable",

  taskHistory: "Task History",
  taskItems: "items",
  allTypes: "All Types",
  allStatus: "All Status",
  noTasks: "No task records",
  heartbeat: "Heartbeat",
  cron: "Cron",
  reminder: "Reminder",
  system: "System",
  success: "Success",
  failed: "Failed",
  running: "Running",
  pending: "Pending",
  cancelled: "Cancelled",
  retrying: "Retrying",
  retry: "Retry",

  approvalTitle: "Confirm Before Execution",
  approvalDesc: "Agent requests to execute",
  approvalDangerWarn: "This action may modify system state or cause irreversible effects. Please confirm carefully.",
  approve: "Approve",
  deny: "Deny",
  confirmExec: "Confirm Execute",
  riskSafe: "Safe Action",
  riskCaution: "File Change Confirmation",
  riskDanger: "High Risk Warning",
  toolExec: "Shell Command",
  toolProcessKill: "Kill Process",
  toolWrite: "Write File",
  toolEdit: "Edit File",
  toolDelete: "Delete File",
  toolApplyPatch: "Apply Patch",
  toolPythonRepl: "Python Code",

  configCenter: "Settings",
  configSandbox: "Sandbox Security",
  configNotifications: "Notifications",
  inheritDefault: "Inherit default",
  heartbeatEnabled: "Enable heartbeat",
  heartbeatInterval: "Check interval",
  toolsAllow: "Allow",
  toolsDeny: "Deny",
  heartbeatOverride: "Heartbeat override",
  toolsPolicyOverride: "Tool policy override",
  commaSeparatedEmptyInherit: "Comma-separated, empty = inherit global",
  commaSeparatedPreferAllow: "Comma-separated, overrides allow",
  writeApprovalLabel: "Write approval",
  writeApprovalOff: "Off",
  writeApprovalOnOverwrite: "Confirm on overwrite",
  writeApprovalAlways: "Always confirm",
  configUpdateFailed: "Update Agent config failed",
  execConfirmLabel: "exec Command Confirmation",
  execConfirmOff: "Off — Execute directly, no confirmation",
  execConfirmOnMiss: "Confirm when not in allowlist (recommended)",
  execConfirmAlways: "Always confirm",
  execConfirmHint: "Whether exec/process_kill requires user confirmation before execution",
  configRuntime: "Runtime",
  configBrowser: "Browser Automation",
  configBackup: "Backup",
  configSkills: "Skills",
  configApp: "App Settings",
  configAdvanced: "Advanced",

  inputPlaceholder: "Type a message... / Type slash for commands",
  sendHint: "Enter to send · Shift+Enter for newline · /commands",
  denied: "Operation denied",
  commandPaletteTitle: "Commands",
  cmdNewDesc: "Reset session (save to long-term memory)",
  cmdResetDesc: "Reset session (do not save to long-term memory)",
  cmdCompactDesc: "Compact history",
  cmdHelpDesc: "Show help",
  cmdStatusDesc: "Agent status",
  cmdContextDesc: "Context usage",
  cmdUsageDesc: "Token usage and cost estimate",
  cmdThinkDesc: "Deep thinking",
  cmdVerboseDesc: "Verbose output",
  cmdReasoningDesc: "Show/hide reasoning process",
  cmdModelDesc: "View/switch model",
  cmdSubagentsDesc: "Sub-agent list",
  cmdWhoamiDesc: "Identity info",
  cmdStopDesc: "Stop generation",
  cmdResetProgressWithMemory: "Resetting session and saving long-term memory. This may take a few seconds...",
  cmdResetProgressNoMemory: "Resetting session (without writing long-term memory)...",
  cmdResetDoneWithMemory: "Session has been reset.",
  cmdResetDoneQueued: "Long-term memory will be saved in the background.",
  cmdResetDoneNoMemory: "Session has been reset (this round was not written to long-term memory).",
  cmdCompactProgress: "Compaction in progress...",
  cmdCompactDone: "Compaction completed.",
  cmdCompactSkipped: "Compaction was skipped.",
  cmdCompactFailed: "Compaction failed.",
  cmdCompactReasonTooFewMessages: "Too few messages, no compaction needed",
  cmdCompactReasonNoEnoughCompressible: "Not enough messages can be compacted",
  cmdCompactReasonSessionMissing: "Session does not exist",
  commandNoticeTitle: "System Notice",
  helpListTitle: "Available Commands",

  toolsTitle: "Function Call Tools",
  categoryFile: "File",
  categoryRuntime: "Runtime",
  categoryWeb: "Web",
  categoryMemory: "Memory",
  categoryKnowledge: "Knowledge",
  categoryAgent: "Agent / Session",
  categoryStatus: "Status",
  categoryOther: "Other",
  keyFiles: "Key Files",
  clickFileToEdit: "Click file to view and edit",

  noSubagents: "No subagents",
  subagentCount: "subagents",
  confirmKillSubagents: "Confirm kill {count} running subagents?",
  killedSubagents: "Killed {count} subagents",
  confirmKillOne: "Confirm kill subagent {id}?",
  noReply: "No reply yet",
  parsingTools: "Parsing tool calls...",

  heartbeatAndCron: "Heartbeat & Cron",
  heartbeatLabel: "Heartbeat",
  noHeartbeatRecords: "No heartbeat records",
  heartbeatStatusOn: "Heartbeat check enabled",
  heartbeatStatusOff: "Heartbeat check disabled",
  heartbeatIntervalLabel: "Check interval",
  clearedClickRefresh: "Cleared. Click refresh to reload",
  cronTasks: "Scheduled Tasks",
  taskName: "Task name",
  oneTimeTask: "One-time task",
  presetCron: "Recurring (preset)",
  intervalCron: "Recurring (interval)",
  noCronTasks: "No scheduled tasks",
  enabled: "Enabled",
  disabled: "Disabled",

  agentDescription: "AI assistant with tool calling, long-term memory and sub-agent collaboration",
  generating: "Generating",

  runtimeEvents: "Runtime Events",
  evtTurnStart: "Turn start",
  evtTurnEnd: "Turn end",
  evtTurnError: "Turn error",
  evtToolStart: "Tool start",
  evtToolEnd: "Tool end",
  evtAutoCompactStart: "Auto compact start",
  evtAutoCompactDone: "Auto compact done",
  evtRecursionLimit: "Recursion limit",
  evtMemorySaved: "Memory saved",
  evtMemoryFailed: "Memory failed",
  evtNoEvents: "No runtime events",
  evtFilterAll: "All",
  evtFilterMemory: "Memory",
  evtFilterError: "Error",
  evtNoFilteredEvents: "No matching events",
};

const localeMap: Record<Locale, Messages> = {
  "zh-CN": zhCN,
  "en-US": enUS,
};

export function getMessages(locale: Locale): Messages {
  return localeMap[locale] || zhCN;
}
