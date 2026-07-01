export type Health = {
  status: string;
  service: string;
  mode?: string;
};

export type Settings = {
  llm_provider: string;
  deepseek_model: string;
  deepseek_api_key_configured: boolean;
  wechat_process_name: string;
  wechat_window_title: string;
  rpa_dry_run: boolean;
  contact_touch_interval_days: number;
  touch_interval_mode: "test_ignore" | "production";
  active_wechat_account_id?: string;
  rpa_send_prefix: string;
  prompt_docx_path: string;
};

export type WindowProbe = {
  detected: boolean;
  process_name: string;
  window_title: string;
  pid?: number;
  path?: string;
  reason?: string;
  hwnd?: number;
  class_name?: string;
  rect?: [number, number, number, number];
  foreground_match?: boolean;
  is_minimized?: boolean;
  show_cmd?: number;
  foreground_title?: string;
};

export type SendDriverProbe = {
  mode: string;
  verified: boolean;
  message: string;
  capabilities: string[];
  blocked_reason?: string;
  calibrated?: boolean;
  calibrated_at?: string | null;
  max_batch_size?: number;
  anchors?: Record<string, { x: number; y: number }>;
  research_report_path?: string;
  research_artifacts?: Array<{
    kind: string;
    path: string;
    available: boolean;
  }>;
  last_verified_at?: string | null;
  last_receipt?: {
    receipt_id?: string;
    channel_id?: string;
    target_id?: string;
    verified_at?: string;
  } | null;
  candidates?: SendDriverCandidate[];
};

export type SendDriverCandidate = {
  id: string;
  label: string;
  status: string;
  can_send: boolean;
  requires_login_window?: boolean;
  evidence?: string;
  next_step?: string;
};

export type Contact = {
  id: string;
  account_id: string;
  wxid: string;
  nickname: string;
  remark?: string;
  alias?: string;
  raw_wxid?: string;
  source?: string;
  wechat_account_dir?: string;
  sync_batch_id?: string;
  last_synced_at?: string;
  local_type?: number;
  contact_flag?: number;
  delete_flag?: number;
  verify_flag?: number;
  is_chatroom_member?: boolean;
  excluded_reason?: string;
  tags: string[];
  eligible_for_touch: boolean;
  eligibility_reason: string;
  confirmed_for_touch: boolean;
};

export type LocalWechatAccount = {
  account_id: string;
  account_dir: string;
  contact_db_found: boolean;
  key_info_db_found: boolean;
  contact_db_encrypted: boolean;
  decrypted_contact_db_found: boolean;
  last_active_at?: string;
};

export type ContactSyncResponse = {
  success?: boolean;
  reason?: string;
  synced: number;
  excluded: number;
  friend_count: number;
  excluded_count: number;
  group_member_excluded: number;
  system_excluded: number;
  filter_version: string;
  account_id: string;
  mode: string;
  contacts: Contact[];
  needs_admin_helper?: boolean;
  diagnostic?: Record<string, unknown>;
};

export type SyncWizardStatus = {
  stage: string;
  stage_label: string;
  message: string;
  account_id?: string;
  account_dir?: string;
  friend_count: number;
  excluded_count: number;
  error_reason?: string;
  requires_admin_helper?: boolean;
  admin_action?: string;
  diagnostic?: Record<string, unknown>;
  synced?: number;
  sync_result?: {
    success?: boolean;
    reason?: string;
    account_id?: string;
    account_dir?: string;
    friend_count?: number;
    excluded_count?: number;
    group_member_excluded?: number;
    system_excluded?: number;
    needs_admin_helper?: boolean;
    diagnostic?: Record<string, unknown>;
  };
};

export type AdminContactSyncResult = {
  ok?: boolean;
  success: boolean;
  status?: string;
  reason?: string;
  message?: string;
  account_id?: string;
  account_dir?: string;
  friend_count?: number;
  excluded_count?: number;
  group_member_excluded?: number;
  system_excluded?: number;
  completed_at?: string;
  decrypt?: {
    success?: boolean;
    returncode?: number | null;
    reason?: string;
    summary?: string;
  };
  diagnostic?: Record<string, unknown>;
};

export type TaskRun = {
  id: string;
  action_type: string;
  target_id?: string;
  status: string;
  step: string;
  progress: number;
  error?: string;
};

export type CurrentTaskStatus = {
  active: boolean;
  stage: string;
  stage_label: string;
  customer: string;
  progress: number;
  message: string;
  can_pause: boolean;
  paused: boolean;
  stopped: boolean;
  task?: TaskRun;
  last_event?: TaskEvent | null;
};

export type ServiceStatus = {
  ok: boolean;
  ready: boolean;
  backend: boolean;
  sidecar: boolean;
  renderer: boolean;
  message: string;
};

export type DesktopBridge = {
  startServices: () => Promise<{ ok: boolean }>;
  getServiceStatus: () => Promise<ServiceStatus>;
  restartServicesAsAdmin: () => Promise<{ ok: boolean; success?: boolean; message: string }>;
  startContactSyncAdminHelper: () => Promise<{ ok: boolean; success?: boolean; message: string }>;
  getContactSyncAdminResult: () => Promise<AdminContactSyncResult>;
  enterRunMode: () => Promise<Record<string, unknown>>;
  exitRunMode: () => Promise<{ ok: boolean }>;
  pauseTask: () => Promise<Record<string, unknown>>;
  resumeTask: () => Promise<Record<string, unknown>>;
  stopTask: () => Promise<Record<string, unknown>>;
  getTaskStatus: () => Promise<CurrentTaskStatus>;
  onTaskRefresh: (callback: () => void) => () => void;
};

declare global {
  interface Window {
    agentDesktop?: DesktopBridge;
  }
}

export type TaskEvent = {
  id: string;
  task_id: string;
  status: string;
  message: string;
  evidence_path?: string;
  created_at: string;
};

export type AuditLog = {
  id: string;
  action: string;
  target: string;
  result: string;
  evidence_path?: string;
  created_at: string;
};

export type EvidenceFile = {
  id: string;
  task_id?: string;
  target_id: string;
  kind: string;
  path: string;
  created_at: string;
};

export type PromptImportResponse = {
  knowledge_count: number;
  system_prompt_preview: string;
  uploaded_filename?: string;
};

export type TouchPreviewTarget = {
  contact_id: string;
  wxid: string;
  nickname: string;
  allowed: boolean;
  reason: string;
  next_touch_at?: string;
};

export type TouchPreview = {
  plan_id: string;
  count: number;
  send_prefix: string;
  targets: TouchPreviewTarget[];
};

export type TouchQueueTarget = TouchPreviewTarget & {
  id: string;
  plan_id: string;
  status: string;
  remark?: string;
  skip_reason?: string;
  last_touched_at?: string;
};

export type TouchQueueResponse = {
  plan_id: string;
  stats: Record<string, number>;
  targets: TouchQueueTarget[];
  queued?: number;
  ran?: number;
  recovered?: number;
  results?: unknown[];
  message?: string;
};

export type AutoReplyItem = {
  id: string;
  message_key: string;
  wxid: string;
  inbound_text: string;
  status: string;
  reply_text?: string;
  intent_label?: string;
  handoff_required?: boolean;
  handoff_reason?: string;
};

export type MomentsFeedItem = {
  target_id: string;
  owner: string;
  snippet?: string;
  source?: string;
  whitelisted?: boolean;
};

export type MomentsFeedResponse = {
  success: boolean;
  message: string;
  items: MomentsFeedItem[];
  evidence?: Record<string, string>;
};

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8710";
const SIDECAR_URL = import.meta.env.VITE_RPA_SIDECAR_URL || "http://127.0.0.1:8720";
const REQUEST_TIMEOUT_MS = 240000;

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(url, { ...init, signal: controller.signal });
  } catch (error) {
    const message = error instanceof Error && error.name === "AbortError" ? "请求超时" : error instanceof Error ? error.message : "请求失败";
    throw new Error(message);
  } finally {
    window.clearTimeout(timer);
  }
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json() as Promise<T>;
}

async function getJson<T>(url: string): Promise<T> {
  return requestJson<T>(url);
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  return requestJson<T>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
}

async function postForm<T>(url: string, body: FormData): Promise<T> {
  return requestJson<T>(url, {
    method: "POST",
    body
  });
}

export const api = {
  backendHealth: () => getJson<Health>(`${BACKEND_URL}/health`),
  sidecarHealth: () => getJson<Health>(`${SIDECAR_URL}/health`),
  settings: () => getJson<Settings>(`${BACKEND_URL}/settings`),
  setTouchIntervalMode: (mode: "test_ignore" | "production") => postJson<Settings>(`${BACKEND_URL}/settings/touch-interval-mode`, { mode }),
  probe: () => getJson<WindowProbe>(`${BACKEND_URL}/wechat/window/probe`),
  normalizeWindow: () => postJson<Record<string, unknown>>(`${BACKEND_URL}/wechat/window/normalize`, {}),
  prepareDedicatedDesktop: () => postJson<Record<string, unknown>>(`${BACKEND_URL}/wechat/window/prepare-dedicated-desktop`, {}),
  sendDriverProbe: () => getJson<SendDriverProbe>(`${BACKEND_URL}/send/driver/probe`),
  calibrateSendDriver: () => postJson<Record<string, unknown>>(`${BACKEND_URL}/send/driver/calibrate`, {}),
  localAccounts: () => getJson<{ accounts: LocalWechatAccount[] }>(`${BACKEND_URL}/wechat/accounts/local`),
  contacts: () => getJson<Contact[]>(`${BACKEND_URL}/wechat/contacts`),
  syncContacts: () => postJson<ContactSyncResponse>(`${BACKEND_URL}/wechat/contacts/sync`, {
    mode: "local_db_full",
    account_id: "auto",
    auto_confirm: true,
    auto_decrypt: true
  }),
  startSyncWizard: () => postJson<SyncWizardStatus>(`${BACKEND_URL}/wechat/sync-wizard/start`, {
    restart_wechat: true,
    timeout_seconds: 180
  }),
  syncWizardStatus: () => getJson<SyncWizardStatus>(`${BACKEND_URL}/wechat/sync-wizard/status`),
  cancelSyncWizard: () => postJson<SyncWizardStatus>(`${BACKEND_URL}/wechat/sync-wizard/cancel`, {}),
  confirmContact: (contactId: string) => postJson<Contact>(`${BACKEND_URL}/wechat/contacts/${contactId}/confirm-touch`, {}),
  excludeContact: (contactId: string) => postJson<Contact>(`${BACKEND_URL}/wechat/contacts/${contactId}/exclude-touch`, {}),
  importPrompt: () => postJson<PromptImportResponse>(`${BACKEND_URL}/prompts/import-docx`, {}),
  uploadPrompt: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return postForm<PromptImportResponse>(`${BACKEND_URL}/prompts/import-docx/file`, body);
  },
  createTouchPlan: () => postJson<{ id: string }>(`${BACKEND_URL}/touch/plans`, { name: "小批量触达", target_limit: 5 }),
  previewTouchPlan: (planId: string) => postJson<TouchPreview>(`${BACKEND_URL}/touch/plans/${planId}/preview`, { limit: 5, direct_send: true }),
  buildTouchQueue: (planId: string, maxContacts = 1000) => postJson<TouchQueueResponse>(`${BACKEND_URL}/touch/plans/${planId}/queue/build`, { max_contacts: maxContacts }),
  touchQueue: (planId: string) => getJson<TouchQueueResponse>(`${BACKEND_URL}/touch/plans/${planId}/queue`),
  runTouchQueue: (planId: string, limit = 3) => postJson<TouchQueueResponse>(`${BACKEND_URL}/touch/plans/${planId}/queue/run`, { limit, direct_send: true }),
  openConversation: (targetId: string) => postJson<{ task: TaskRun; sidecar: Record<string, unknown> }>(`${BACKEND_URL}/wechat/message/open-conversation`, {
    action_type: "message.open_conversation",
    account_id: "local",
    target_id: targetId,
    payload: {}
  }),
  runTouchPlan: (planId: string, limit = 5) => postJson<{ ran: number; allowed_limit?: number; requested_limit?: number; results: unknown[] }>(`${BACKEND_URL}/touch/plans/${planId}/run`, { limit, direct_send: true }),
  scanAutoReplies: () => postJson<{ scanned: number; queued: number; items: AutoReplyItem[] }>(`${BACKEND_URL}/auto-reply/scan`, { limit: 20 }),
  autoReplyQueue: () => getJson<{ items: AutoReplyItem[] }>(`${BACKEND_URL}/auto-reply/queue`),
  runAutoReplies: (limit = 1) => postJson<{ processed: number; remaining: number; results: unknown[] }>(`${BACKEND_URL}/auto-reply/run`, { limit, direct_send: true }),
  scanMomentsFeed: () => getJson<MomentsFeedResponse>(`${BACKEND_URL}/moments/feed/scan`),
  runMomentsInteraction: (actionType: "moments.like" | "moments.comment", targetId: string, whitelist: string[], comment = "") => postJson<Record<string, unknown>>(`${BACKEND_URL}/moments/interactions/run`, {
    action_type: actionType,
    account_id: "local",
    target_id: targetId,
    payload: { whitelist, comment }
  }),
  tasks: () => getJson<TaskRun[]>(`${BACKEND_URL}/tasks`),
  currentTask: () => getJson<CurrentTaskStatus>(`${BACKEND_URL}/tasks/current`),
  controlTask: (action: "pause" | "resume" | "stop") => postJson<Record<string, unknown>>(`${BACKEND_URL}/tasks/control`, { action }),
  taskEvents: () => getJson<TaskEvent[]>(`${BACKEND_URL}/tasks/events`),
  audits: () => getJson<AuditLog[]>(`${BACKEND_URL}/audit/logs`),
  evidence: () => getJson<EvidenceFile[]>(`${BACKEND_URL}/evidence/files`)
};
