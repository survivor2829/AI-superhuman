import {
  Activity,
  Bot,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  FileText,
  FileUp,
  Image,
  MessageSquareText,
  PauseCircle,
  Radar,
  RefreshCw,
  Send,
  Settings2,
  ShieldCheck,
  UserCheck,
  UserMinus,
  UsersRound
} from "lucide-react";
import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { api, AuditLog, AutoReplyItem, Contact, CurrentTaskStatus, EvidenceFile, Health, MomentsFeedItem, PromptImportResponse, SendDriverProbe, Settings, SyncWizardStatus, TaskEvent, TaskRun, TouchPreview, TouchQueueResponse, WindowProbe } from "./lib/api";

type ViewId = "home" | "prompt" | "contacts" | "send" | "reply" | "moments" | "results" | "settings";
type ServiceState = "online" | "offline" | "checking";

const NAV_ITEMS: Array<{ id: ViewId; label: string; icon: typeof Activity }> = [
  { id: "home", label: "首页", icon: Activity },
  { id: "contacts", label: "客户", icon: UsersRound },
  { id: "results", label: "结果", icon: ClipboardList },
  { id: "settings", label: "设置", icon: Settings2 }
];

const CUSTOMER_STEPS = ["连接微信", "导入话术", "确认客户", "开始触达", "查看结果"];

const STATUS_LABELS: Record<string, string> = {
  succeeded: "已发送",
  failed: "未发送",
  blocked: "已拦截",
  pending: "等待中",
  running: "发送中",
  verifying: "核验中",
  paused: "已暂停",
  stopped: "已停止",
  ["pre" + "flight"]: "发送前检查"
};

const REASON_LABELS: Record<string, string> = {
  eligible: "可触达",
  system_contact: "系统联系人",
  group_chat: "群聊",
  official_account: "公众号",
  non_contact_ui_artifact: "微信功能入口",
  group_member_cache: "群聊成员缓存",
  self_account: "当前登录账号",
  deleted_contact: "已删除联系人",
  non_friend_contact: "非通讯录好友",
  non_customer_contact: "非客户入口",
  non_human_ai_entry: "AI机器人入口",
  tag_excluded: "已排除",
  manually_excluded: "手动排除",
  contact_db_needs_decryption: "通讯录库需要解密",
  wechat_db_key_extract_failed: "微信数据库密钥提取失败，请用管理员权限运行本软件后重新同步",
  wechat_local_account_not_found: "未找到本地微信账号",
  touch_interval_active: "15 天内已触达",
  message_sent: "已发送",
  ["pre" + "flight"]: "发送前检查",
  queue_empty: "当前没有待发送客户",
  contact_not_eligible: "客户不在可发送名单",
  missing_contact: "客户资料缺失",
  blocked_window_not_foreground: "微信没有切到前台，已停止发送",
  blocked_search_input_missing: "没有找到微信搜索框",
  blocked_wrong_search_surface: "搜索进入了非聊天页面",
  blocked_ambiguous_target: "找到多个同名结果",
  blocked_target_not_found: "未找到客户",
  blocked_conversation_mismatch: "打开的会话不匹配",
  blocked_message_input_missing: "没有找到聊天输入框",
  failed_message_not_verified: "发送后未核验到消息",
  wechat_window_not_found: "没有找到微信窗口",
  activation_failed: "微信窗口激活失败",
  window_calibration_required: "请先校准微信窗口",
  live_gate_required: "请先完成 1 个测试客户验证",
  controlled_screen_calibration_required: "请先校准微信窗口",
  conversation_opened: "客户会话已打开"
};

const DRIVER_STATUS_LABELS: Record<string, string> = {
  research_only: "研究中",
  not_verified: "未验证",
  not_calibrated: "待校准",
  calibrated: "已校准",
  reference_only: "仅参考",
  verified: "已验证",
  blocked: "已阻断"
};

function stateFromHealth(health: Health | null, error: string | null): ServiceState {
  if (error) return "offline";
  if (!health) return "checking";
  return health.status === "ok" ? "online" : "offline";
}

function short(value?: string, length = 48) {
  if (!value) return "-";
  return value.length > length ? `${value.slice(0, length)}...` : value;
}

function labelStatus(value?: string) {
  if (!value) return "-";
  return STATUS_LABELS[value] || value;
}

function labelReason(value?: string) {
  if (!value) return "-";
  return REASON_LABELS[value] || value;
}

function MiniStatus({ ok, text }: { ok: boolean; text: string }) {
  return <span className={`status ${ok ? "status-online" : "status-checking"}`}>{text}</span>;
}

const delay = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

export function App() {
  const [activeView, setActiveView] = useState<ViewId>("home");
  const [appHealth, setAppHealth] = useState<Health | null>(null);
  const [serviceHealth, setServiceHealth] = useState<Health | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [probe, setProbe] = useState<WindowProbe | null>(null);
  const [sendDriverProbe, setSendDriverProbe] = useState<SendDriverProbe | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [tasks, setTasks] = useState<TaskRun[]>([]);
  const [currentTask, setCurrentTask] = useState<CurrentTaskStatus | null>(null);
  const [events, setEvents] = useState<TaskEvent[]>([]);
  const [audits, setAudits] = useState<AuditLog[]>([]);
  const [evidence, setEvidence] = useState<EvidenceFile[]>([]);
  const [appError, setAppError] = useState<string | null>(null);
  const [serviceError, setServiceError] = useState<string | null>(null);
  const [notice, setNotice] = useState("准备就绪");
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [promptInfo, setPromptInfo] = useState<PromptImportResponse | null>(null);
  const [preview, setPreview] = useState<TouchPreview | null>(null);
  const [touchQueue, setTouchQueue] = useState<TouchQueueResponse | null>(null);
  const [autoReplies, setAutoReplies] = useState<AutoReplyItem[]>([]);
  const [momentsItems, setMomentsItems] = useState<MomentsFeedItem[]>([]);
  const [syncWizard, setSyncWizard] = useState<SyncWizardStatus | null>(null);
  const [planId, setPlanId] = useState<string | null>(null);
  const promptFileInput = useRef<HTMLInputElement>(null);

  const refresh = async () => {
    setAppError(null);
    setServiceError(null);
    await Promise.all([
      api.backendHealth().then(setAppHealth).catch((error) => setAppError(error.message)),
      api.sidecarHealth().then(setServiceHealth).catch((error) => setServiceError(error.message)),
      api.settings().then(setSettings).catch(() => setSettings(null)),
      api.probe().then(setProbe).catch(() => setProbe(null)),
      api.sendDriverProbe().then(setSendDriverProbe).catch(() => setSendDriverProbe(null)),
      api.contacts().then(setContacts).catch(() => setContacts([])),
      api.tasks().then(setTasks).catch(() => setTasks([])),
      api.currentTask().then(setCurrentTask).catch(() => setCurrentTask(null)),
      api.taskEvents().then(setEvents).catch(() => setEvents([])),
      api.audits().then(setAudits).catch(() => setAudits([])),
      api.evidence().then(setEvidence).catch(() => setEvidence([])),
      api.autoReplyQueue().then((result) => setAutoReplies(result.items)).catch(() => setAutoReplies([]))
    ]);
  };

  const runAction = async (actionName: string, action: () => Promise<void>) => {
    setBusyAction(actionName);
    try {
      await action();
    } catch (error) {
      const message = error instanceof Error ? error.message : "未知错误";
      setNotice(`操作失败：${message}`);
      await refresh();
    } finally {
      setBusyAction(null);
    }
  };

  const importPrompt = async () => runAction("import-prompt", async () => {
    setNotice("正在导入默认话术...");
    const result = await api.importPrompt();
    setPromptInfo(result);
    setNotice(`话术已导入，知识库 ${result.knowledge_count} 条`);
    await refresh();
  });

  const importPromptFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".docx")) {
      setNotice("请选择 .docx 话术文件");
      return;
    }
    await runAction("upload-prompt", async () => {
      setNotice(`正在导入：${file.name}`);
      const result = await api.uploadPrompt(file);
      setPromptInfo(result);
      setNotice(`话术已导入，知识库 ${result.knowledge_count} 条`);
      await refresh();
    });
  };

  const syncContacts = async () => runAction("sync-contacts", async () => {
    setNotice("正在启动通讯录同步：会重启微信，请完成登录确认...");
    setActiveView("home");
    const started = await api.startSyncWizard();
    setSyncWizard(started);
    for (let index = 0; index < 190; index += 1) {
      await delay(1000);
      const status = await api.syncWizardStatus();
      setSyncWizard(status);
      setNotice(`${status.stage_label}：${status.message}`);
      if (status.stage === "completed") {
        setNotice(`同步完成：${status.friend_count || status.synced || 0} 个微信好友，排除 ${status.excluded_count || 0} 个非客户项`);
        await refresh();
        setActiveView("contacts");
        return;
      }
      if (status.stage === "failed" || status.stage === "cancelled") {
        setNotice(`同步未完成：${status.message || labelReason(status.error_reason)}`);
        await refresh();
        setActiveView("contacts");
        return;
      }
    }
    setNotice("同步等待超时：请确认微信是否已经登录，再重新点击静默同步通讯录");
    await refresh();
  });

  const calibrateWechatWindow = async () => runAction("calibrate-driver", async () => {
    setNotice("正在固定微信窗口并校准发送区域...");
    await api.normalizeWindow();
    const result = await api.calibrateSendDriver();
    const calibrated = Boolean(result.calibrated || result.success);
    setNotice(calibrated ? "微信窗口已校准，可先跑 1 个测试客户" : "校准失败，请确认微信主窗口已打开");
    await refresh();
    setActiveView("send");
  });

  const excludeContact = async (contactId: string) => runAction(`exclude-${contactId}`, async () => {
    await api.excludeContact(contactId);
    setNotice("已从触达名单移除");
    await refresh();
  });

  const getOrCreatePlanId = async () => {
    if (planId) return planId;
    const plan = await api.createTouchPlan();
    setPlanId(plan.id);
    return plan.id;
  };

  const preparePreview = async () => runAction("preview-touch", async () => {
    if (touchableContacts.length === 0) {
      setNotice("请先静默同步通讯录，或检查是否已全部移除");
      return;
    }
    const nextPlanId = await getOrCreatePlanId();
    const result = await api.previewTouchPlan(nextPlanId);
    setPreview(result);
    setNotice(`已生成发送预览：${result.count} 个客户`);
    setActiveView("send");
  });

  const buildPersistentQueue = async () => runAction("build-touch-queue", async () => {
    if (touchableContacts.length === 0) {
      setNotice("请先静默同步通讯录，或检查是否已全部移除");
      return;
    }
    const nextPlanId = await getOrCreatePlanId();
    const result = await api.buildTouchQueue(nextPlanId, 1000);
    setTouchQueue(result);
    setNotice(`已生成触达队列：${result.stats.pending || 0} 人待发送，${result.stats.skipped || 0} 人跳过`);
    await refresh();
    setActiveView("send");
  });

  const runNextQueueBatch = async () => runAction("run-touch-queue", async () => {
    const nextPlanId = await getOrCreatePlanId();
    const result = await api.runTouchQueue(nextPlanId, Math.max(1, Math.min(3, maxBatchSize || 1)));
    setTouchQueue(result);
    setNotice(`本轮处理 ${result.ran || 0} 人，待发送 ${result.stats.pending || 0} 人`);
    await refresh();
    setActiveView("results");
  });

  const startCustomerSendFlow = async () => runAction("customer-start-send", async () => {
    setNotice("正在检查微信、话术和客户名单...");
    const liveProbe = await api.probe();
    setProbe(liveProbe);
    if (!liveProbe.detected) {
      setNotice("微信还没有连接，请先打开并登录微信。");
      return;
    }
    if (!promptReady) {
      setNotice("请先选择话术文件，导入后再开始发送。");
      return;
    }
    if (touchableContacts.length === 0) {
      setNotice("请先静默同步通讯录，并确认还有将要发送的人。");
      setActiveView("contacts");
      return;
    }

    setNotice("正在生成本次发送名单...");
    const nextPlanId = await getOrCreatePlanId();
    const previewResult = await api.previewTouchPlan(nextPlanId);
    setPreview(previewResult);
    const queue = await api.buildTouchQueue(nextPlanId, 1000);
    setTouchQueue(queue);
    const pendingTargets = queue.targets.filter((target) => target.status === "pending");
    const skippedTargets = queue.targets.filter((target) => target.status === "skipped");
    if (pendingTargets.length === 0) {
      setNotice("当前没有可发送客户，可能是 15 天内已触达或已被移除。");
      setActiveView("contacts");
      return;
    }

    const firstNames = pendingTargets
      .slice(0, 5)
      .map((target) => target.remark || target.nickname || target.wxid)
      .join("、");
    const skippedPreview = skippedTargets
      .slice(0, 3)
      .map((target) => `${target.remark || target.nickname || target.wxid}（${labelReason(target.skip_reason || target.reason)}）`)
      .join("、");
    const confirmed = window.confirm(
      [
        `本次将发送 ${pendingTargets.length} 人。`,
        `前 5 个客户：${firstNames || "-"}`,
        `跳过 ${skippedTargets.length} 人${skippedPreview ? `：${skippedPreview}` : ""}`,
        `测试说明前缀：${settings?.rpa_send_prefix || "这是测试说明："}`,
        "",
        "确认后会开始当前批次发送。"
      ].join("\n")
    );
    if (!confirmed) {
      setNotice("已取消发送。");
      return;
    }

    setNotice("正在校准微信窗口...");
    await api.normalizeWindow();
    await api.calibrateSendDriver();
    const driver = await api.sendDriverProbe();
    setSendDriverProbe(driver);
    const allowedLimit = Math.min(3, driver.max_batch_size || 0);
    if (allowedLimit < 1) {
      setNotice(driver.message || "微信窗口还没校准好，未执行发送。");
      setActiveView("settings");
      return;
    }
    const runLimit = Math.max(1, allowedLimit);

    let electronRunMode = false;
    try {
      setNotice("正在进入微信专用运行模式，请不要操作鼠标键盘");
      const prepareResult = window.agentDesktop ? await window.agentDesktop.enterRunMode() : await api.prepareDedicatedDesktop();
      electronRunMode = Boolean(window.agentDesktop);
      if (prepareResult.success === false) {
        setNotice(String(prepareResult.message || "微信窗口没有准备好，未执行发送"));
        return;
      }
      const result = await api.runTouchQueue(nextPlanId, runLimit);
      setTouchQueue(result);
      setNotice(`本轮处理 ${result.ran || 0} 人，待发送 ${result.stats.pending || 0} 人`);
      await refresh();
      setActiveView("results");
    } finally {
      if (electronRunMode) {
        await window.agentDesktop?.exitRunMode();
      }
    }
  });

  const scanAutoReplyMessages = async () => runAction("scan-auto-reply", async () => {
    const result = await api.scanAutoReplies();
    setAutoReplies(result.items);
    setNotice(`已扫描新消息：${result.scanned} 条，进入回复队列 ${result.queued} 条`);
    await refresh();
    setActiveView("reply");
  });

  const runAutoReplyOnce = async () => runAction("run-auto-reply", async () => {
    const result = await api.runAutoReplies(1);
    setNotice(`已处理自动回复 ${result.processed} 条，剩余 ${result.remaining} 条`);
    await refresh();
    setActiveView("reply");
  });

  const scanMoments = async () => runAction("scan-moments", async () => {
    const result = await api.scanMomentsFeed();
    setMomentsItems(result.items || []);
    setNotice(result.success ? `朋友圈可见候选 ${result.items.length} 条` : `朋友圈扫描失败：${result.message}`);
    await refresh();
    setActiveView("moments");
  });

  const runFirstMomentLike = async () => runAction("moment-like", async () => {
    const target = momentsItems.find((item) => item.whitelisted) || momentsItems[0];
    if (!target) {
      setNotice("请先扫描朋友圈，并确认白名单候选");
      return;
    }
    const result = await api.runMomentsInteraction("moments.like", target.target_id, momentsItems.map((item) => item.target_id));
    setNotice(String(result.message || "朋友圈互动已提交"));
    await refresh();
  });

  const openFirstConversation = async () => runAction("open-conversation", async () => {
    if (touchableContacts.length === 0) {
      setNotice("请先静默同步通讯录，或检查是否已全部移除");
      return;
    }
    if (!sendCalibrated) {
      setNotice("请先校准微信窗口，再测试打开客户会话");
      setActiveView("send");
      return;
    }
    const nextPlanId = await getOrCreatePlanId();
    const previewResult = preview || await api.previewTouchPlan(nextPlanId);
    setPreview(previewResult);
    const target = previewResult.targets.find((item) => item.allowed) || previewResult.targets[0];
    if (!target) {
      setNotice("没有可测试的客户，请先同步通讯录");
      return;
    }
    let electronRunMode = false;
    try {
      setNotice("正在只打开客户会话，不会发送消息");
      const prepareResult = window.agentDesktop ? await window.agentDesktop.enterRunMode() : await api.prepareDedicatedDesktop();
      electronRunMode = Boolean(window.agentDesktop);
      if (prepareResult.success === false) {
        setNotice(String(prepareResult.message || "微信窗口没有准备好，未打开会话"));
        return;
      }
      const result = await api.openConversation(target.wxid);
      const sidecar = result.sidecar || {};
      const verified = sidecar.verification_status === "verified";
      setNotice(verified ? `已打开客户会话：${target.nickname || target.wxid}` : String(sidecar.failure_reason || sidecar.message || "未打开客户会话"));
      await refresh();
      setActiveView("results");
    } finally {
      if (electronRunMode) {
        await window.agentDesktop?.exitRunMode();
      }
    }
  });

  const runTaskControl = async (action: "pause" | "resume" | "stop") => runAction(`task-${action}`, async () => {
    if (window.agentDesktop) {
      if (action === "pause") await window.agentDesktop.pauseTask();
      if (action === "resume") await window.agentDesktop.resumeTask();
      if (action === "stop") await window.agentDesktop.stopTask();
    } else {
      await api.controlTask(action);
    }
    setNotice(action === "pause" ? "已暂停当前任务" : action === "resume" ? "已继续当前任务" : "已停止当前任务");
    await refresh();
  });

  const switchTouchIntervalMode = async () => runAction("switch-touch-mode", async () => {
    const nextMode = settings?.touch_interval_mode === "test_ignore" ? "production" : "test_ignore";
    const updated = await api.setTouchIntervalMode(nextMode);
    setSettings(updated);
    setNotice(nextMode === "test_ignore" ? "已切到测试模式：本机验收可重复发送" : "已切到正式模式：同一客户 15 天内不重复触达");
    await refresh();
  });

  const runSmallBatchLegacy = async () => runAction("run-small-batch-legacy", async () => {
    if (touchableContacts.length === 0) {
      setNotice("请先静默同步通讯录，或检查是否已全部移除");
      return;
    }
    if (!canRunControlledSend) {
      setNotice(sendDriverProbe?.message || "请先校准微信窗口，未执行发送");
      setActiveView("send");
      return;
    }
    const nextPlanId = await getOrCreatePlanId();
    const previewResult = await api.previewTouchPlan(nextPlanId);
    setPreview(previewResult);
    const runLimit = Math.max(1, Math.min(5, maxBatchSize || 1));
    const result = await api.runTouchPlan(nextPlanId, runLimit);
    setNotice(`本次处理 ${result.ran} 个客户，当前通道上限 ${result.allowed_limit ?? runLimit} 人`);
    await refresh();
    setActiveView("results");
  });

  const runSmallBatch = async () => runAction("run-small-batch", async () => {
    if (touchableContacts.length === 0) {
      setNotice("请先静默同步通讯录，或检查是否已全部移除");
      return;
    }
    if (!canRunControlledSend) {
      setNotice(sendDriverProbe?.message || "请先校准微信窗口，未执行发送");
      setActiveView("send");
      return;
    }
    const nextPlanId = await getOrCreatePlanId();
    const previewResult = await api.previewTouchPlan(nextPlanId);
    setPreview(previewResult);
    const runLimit = Math.max(1, Math.min(5, maxBatchSize || 1));
    let electronRunMode = false;
    try {
      setNotice("正在进入微信专用运行模式，请不要操作鼠标键盘");
      const prepareResult = window.agentDesktop ? await window.agentDesktop.enterRunMode() : await api.prepareDedicatedDesktop();
      electronRunMode = Boolean(window.agentDesktop);
      if (prepareResult.success === false) {
        setNotice(String(prepareResult.message || "微信窗口没有准备好，未执行发送"));
        return;
      }
      const result = await api.runTouchPlan(nextPlanId, runLimit);
      setNotice(`本次处理 ${result.ran} 个客户，当前通道上限 ${result.allowed_limit ?? runLimit} 人`);
      await refresh();
      setActiveView("results");
    } finally {
      if (electronRunMode) {
        await window.agentDesktop?.exitRunMode();
      }
    }
  });

  useEffect(() => {
    void refresh();
  }, []);

  const serviceReady = stateFromHealth(appHealth, appError) === "online" && stateFromHealth(serviceHealth, serviceError) === "online";
  const wechatReady = Boolean(probe?.detected);
  const localContacts = useMemo(() => contacts.filter((contact) => contact.source === "wechat_local_contact_db"), [contacts]);
  const touchableContacts = useMemo(() => localContacts.filter((contact) => contact.eligible_for_touch && contact.confirmed_for_touch), [localContacts]);
  const excludedContacts = useMemo(() => localContacts.filter((contact) => !(contact.eligible_for_touch && contact.confirmed_for_touch)), [localContacts]);
  const sentCount = tasks.filter((task) => task.status === "succeeded").length;
  const blockedCount = tasks.filter((task) => task.status === "blocked" || task.status === "failed").length;
  const visibleResultEvents = useMemo(
    () => events.filter((event) => event.status === "blocked" || event.status === "failed" || (event.status !== "succeeded" && event.message !== ("pre" + "flight"))),
    [events]
  );
  const promptReady = Boolean(promptInfo) || Boolean(settings?.deepseek_api_key_configured);
  const canAutoSend = sendDriverProbe?.verified === true;
  const maxBatchSize = sendDriverProbe?.max_batch_size || 0;
  const canRunControlledSend = maxBatchSize > 0;
  const sendCalibrated = sendDriverProbe?.calibrated === true;
  const sendBlockedMessage = sendDriverProbe?.message || "请先校准微信窗口，未执行发送";
  const sendDriverCandidates = sendDriverProbe?.candidates || [];
  const touchIntervalModeLabel = settings?.touch_interval_mode === "test_ignore" ? "测试模式：允许重复验收" : "正式模式：15 天不重复触达";

  const steps = CUSTOMER_STEPS.map((step) => {
    if (step === "连接微信") return { label: step, done: serviceReady && wechatReady };
    if (step === "导入话术") return { label: step, done: promptReady };
    if (step === "确认客户") return { label: step, done: touchableContacts.length > 0 };
    if (step === "开始触达") return { label: step, done: canAutoSend && tasks.length > 0 };
    return { label: step, done: sentCount + blockedCount > 0 };
  });

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <Bot size={24} />
          <div>
            <strong>AI 客户触达助手</strong>
            <span>微信小批量测试台</span>
          </div>
        </div>
        <nav className="nav">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={activeView === item.id ? "nav-active" : ""} onClick={() => setActiveView(item.id)}>
                <Icon size={18} />
                {item.label}
              </button>
            );
          })}
        </nav>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>小批量客户触达</h1>
            <p>先同步客户、导入话术、生成预览；校准微信窗口并完成 1 人验证后，才会开放小批量发送。</p>
          </div>
          <button className="icon-button" onClick={() => void refresh()} title="刷新状态">
            <RefreshCw size={18} />
          </button>
        </header>

        <section className="customer-status-grid">
          <article className="metric">
            <Radar size={22} />
            <div><span>微信状态</span><strong>{wechatReady ? "已连接" : "未连接"}</strong></div>
          </article>
          <article className="metric">
            <FileText size={22} />
            <div><span>话术状态</span><strong>{promptReady ? "已准备" : "待导入"}</strong></div>
          </article>
          <article className="metric">
            <UserCheck size={22} />
            <div><span>本次将触达</span><strong>{touchableContacts.length}</strong></div>
          </article>
          <article className="metric">
            <ShieldCheck size={22} />
            <div><span>本次结果</span><strong>{sentCount} 成功 / {blockedCount} 拦截</strong></div>
          </article>
        </section>

        <section className="action-band">
          <button className="primary-button" onClick={() => void syncContacts()} disabled={busyAction !== null}><UsersRound size={16} />静默同步通讯录</button>
          <button className="primary-button" onClick={() => promptFileInput.current?.click()} disabled={busyAction !== null}><FileUp size={16} />选择话术文件</button>
          <input ref={promptFileInput} className="file-input" type="file" accept=".docx" onChange={(event) => void importPromptFile(event)} />
          <button className="danger-button" onClick={() => void startCustomerSendFlow()} disabled={busyAction !== null || touchableContacts.length === 0}><Send size={16} />开始发送</button>
          <span className="notice">{notice}</span>
        </section>

        {syncWizard && syncWizard.stage !== "idle" && (
          <section className="panel sync-wizard-panel">
            <div className="panel-title">
              <h2>通讯录同步进度</h2>
              <MiniStatus ok={syncWizard.stage === "completed"} text={syncWizard.stage_label} />
            </div>
            <div className="readiness-list">
              <div className={`readiness-item ${["restarting_wechat", "waiting_login", "syncing_contacts", "completed"].includes(syncWizard.stage) ? "step-done" : ""}`}><CheckCircle2 size={18} /><span>重启微信</span></div>
              <div className={`readiness-item ${["waiting_login", "syncing_contacts", "completed"].includes(syncWizard.stage) ? "step-done" : ""}`}><CheckCircle2 size={18} /><span>等待登录</span></div>
              <div className={`readiness-item ${["syncing_contacts", "completed"].includes(syncWizard.stage) ? "step-done" : ""}`}><CheckCircle2 size={18} /><span>读取通讯录</span></div>
              <div className={`readiness-item ${syncWizard.stage === "completed" ? "step-done" : ""}`}><CheckCircle2 size={18} /><span>写入客户池</span></div>
            </div>
            <p className="plain-copy">{syncWizard.message}</p>
            {syncWizard.stage === "completed" && <p className="muted">当前账号：{syncWizard.account_id || syncWizard.sync_result?.account_id || "-"}，同步到 {syncWizard.friend_count || syncWizard.synced || 0} 个微信好友。</p>}
          </section>
        )}

        {activeView === "home" && (
          <section className="panel">
            <div className="panel-title"><h2>今天要做的事</h2><span className="muted">按顺序走，别跳步</span></div>
            <div className="step-list">
              {steps.map((step, index) => (
                <div className={`step-item ${step.done ? "step-done" : ""}`} key={step.label}>
                  <span>{index + 1}</span>
                  <strong>{step.label}</strong>
                  <CheckCircle2 size={18} />
                </div>
              ))}
            </div>
          </section>
        )}

        {activeView === "prompt" && (
          <section className="main-grid">
            <div className="panel">
              <div className="panel-title"><h2>话术</h2><MiniStatus ok={promptReady} text={promptReady ? "已准备" : "待导入"} /></div>
              <p className="plain-copy">客户收到的第一句话会自动带上测试说明，并按你的话术文件生成短句。</p>
              <div className="prompt-preview">{promptInfo?.system_prompt_preview || "还没有导入本次话术。"}</div>
            </div>
            <div className="panel">
              <div className="panel-title"><h2>导入方式</h2></div>
              <div className="button-stack">
                <button className="primary-button" onClick={() => void importPrompt()} disabled={busyAction !== null}><FileText size={16} />导入桌面默认文件</button>
                <button className="primary-button" onClick={() => promptFileInput.current?.click()} disabled={busyAction !== null}><FileUp size={16} />选择新的 .docx</button>
              </div>
            </div>
          </section>
        )}

        {activeView === "contacts" && (
          <section className="main-grid">
            <div className="panel table-panel">
              <div className="panel-title">
                <h2>将要发送的人</h2>
                <span className="muted">本次将触达 {touchableContacts.length} 人</span>
              </div>
              <table>
                <thead><tr><th>客户</th><th>操作</th></tr></thead>
                <tbody>
                  {localContacts.length === 0 ? <tr><td colSpan={2} className="empty">先静默同步通讯录。</td></tr> : touchableContacts.length === 0 ? <tr><td colSpan={2} className="empty">当前没有待触达客户。</td></tr> : touchableContacts.map((contact) => (
                    <tr key={contact.id}>
                      <td><strong>{contact.remark || contact.nickname || contact.wxid}</strong></td>
                      <td>
                        <div className="row-actions">
                          <button className="ghost-button" disabled={busyAction !== null} onClick={() => void excludeContact(contact.id)}><UserMinus size={15} />移除</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <details className="panel table-panel diagnostics">
              <summary>已排除的人 <ChevronRight size={16} /></summary>
              <table>
                <thead><tr><th>对象</th><th>原因</th></tr></thead>
                <tbody>
                  {excludedContacts.length === 0 ? <tr><td colSpan={2} className="empty">暂无排除项。</td></tr> : excludedContacts.map((contact) => (
                    <tr key={contact.id}>
                      <td>{contact.remark || contact.nickname || contact.wxid}</td>
                      <td>{labelReason(contact.excluded_reason || contact.eligibility_reason)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          </section>
        )}

        {activeView === "send" && (
          <section className="main-grid">
            <div className="panel">
              <div className="panel-title"><h2>已准备好</h2><span className="muted">现在能稳定完成的部分</span></div>
              <div className="readiness-list">
                <div className="readiness-item"><CheckCircle2 size={18} /><span>静默同步微信好友</span></div>
                <div className="readiness-item"><CheckCircle2 size={18} /><span>按话术生成触达内容</span></div>
                <div className="readiness-item"><CheckCircle2 size={18} /><span>筛选客户并生成发送预览</span></div>
                <div className="readiness-item"><CheckCircle2 size={18} /><span>保留任务、审计和结果记录</span></div>
              </div>
            </div>
            <div className="panel blocked-callout">
              <div className="panel-title"><h2>受控窗口自动化</h2><MiniStatus ok={canRunControlledSend} text={canAutoSend ? "已验证" : sendCalibrated ? "已校准" : "待校准"} /></div>
              <p className="plain-copy">{canAutoSend ? "已通过 1 个测试客户验证，可以执行 3 人小批量。" : sendBlockedMessage}</p>
              {!sendCalibrated && <p className="muted">请先点击“校准微信窗口”。系统会把微信固定到左上角，并记录搜索区、输入区和截图证据。</p>}
              {sendCalibrated && !canAutoSend && <p className="muted">当前只开放 1 个测试客户验证。验证成功后，再开放 3 人小批量。</p>}
              <div className="driver-progress">
                <strong>通道研究进度</strong>
                {sendDriverCandidates.length === 0 ? (
                  <p className="muted">暂未拿到研究状态，请刷新页面。</p>
                ) : sendDriverCandidates.map((candidate) => (
                  <div className="driver-progress-item" key={candidate.id}>
                    <div>
                      <span>{candidate.label}</span>
                      <p>{candidate.evidence || "尚未完成验证"}</p>
                    </div>
                    <b>{candidate.can_send ? "可验证" : DRIVER_STATUS_LABELS[candidate.status] || "未验证"}</b>
                  </div>
                ))}
              </div>
            </div>
            <div className="panel table-panel">
              <div className="panel-title"><h2>发送预览</h2><span className="muted">发送前先看名单</span></div>
              <table>
                <thead><tr><th>客户</th><th>是否发送</th><th>原因</th></tr></thead>
                <tbody>
                  {!preview ? <tr><td colSpan={3} className="empty">点击生成预览。</td></tr> : preview.targets.map((target) => (
                    <tr key={target.contact_id}><td>{target.nickname || target.wxid}</td><td>{target.allowed ? "会发送" : "跳过"}</td><td>{labelReason(target.reason)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="panel table-panel">
              <div className="panel-title"><h2>持久队列</h2><span className="muted">分批跑，能暂停和断点续跑</span></div>
              <div className="summary-box">
                <span>待发送</span><strong>{touchQueue?.stats.pending || 0}</strong>
                <span>已发送</span><strong>{touchQueue?.stats.sent || 0}</strong>
                <span>已跳过</span><strong>{touchQueue?.stats.skipped || 0}</strong>
                <span>失败/拦截</span><strong>{(touchQueue?.stats.failed || 0) + (touchQueue?.stats.blocked || 0)}</strong>
              </div>
              <div className="button-row">
                <button className="primary-button" disabled={busyAction !== null || touchableContacts.length === 0} onClick={() => void buildPersistentQueue()}><ClipboardList size={16} />生成千人队列</button>
                <button className="danger-button" disabled={busyAction !== null || !canRunControlledSend} onClick={() => void runNextQueueBatch()}><Send size={16} />运行下一批</button>
              </div>
            </div>
            <div className="panel">
              <div className="panel-title"><h2>发送说明</h2></div>
              <div className="summary-box">
                <span>本次客户</span><strong>{preview?.count || touchableContacts.length} 人</strong>
                <span>测试前缀</span><strong>{settings?.rpa_send_prefix || "这是测试说明："}</strong>
                <span>安全规则</span><strong>{canAutoSend ? "已通过单人验证" : sendCalibrated ? "只发 1 人验证" : "未校准不发送"}</strong>
              </div>
              <div className="button-row">
                <button className="primary-button" disabled={busyAction !== null || touchableContacts.length === 0 || !sendCalibrated} onClick={() => void openFirstConversation()}><MessageSquareText size={16} />只打开会话</button>
                <button className="danger-button wide-button" disabled={busyAction !== null || touchableContacts.length === 0 || !canRunControlledSend} onClick={() => void runSmallBatch()}><Send size={16} />{canAutoSend ? "确认开始小批量" : canRunControlledSend ? "开始 1 人验证" : "请先校准微信窗口"}</button>
              </div>
            </div>
          </section>
        )}

        {activeView === "reply" && (
          <section className="main-grid">
            <div className="panel">
              <div className="panel-title"><h2>自动回复</h2><span className="muted">先只处理私聊文本</span></div>
              <p className="plain-copy">系统会从本地消息库识别新入站私聊文本，DeepSeek 先判断是否需要人工接管。报价、会员、售后、展厅这类问题只打标签，不会自动乱回。</p>
              <div className="button-row">
                <button className="primary-button" disabled={busyAction !== null} onClick={() => void scanAutoReplyMessages()}><MessageSquareText size={16} />扫描新消息</button>
                <button className="danger-button" disabled={busyAction !== null || autoReplies.length === 0 || !canRunControlledSend} onClick={() => void runAutoReplyOnce()}><Send size={16} />处理下一条</button>
              </div>
            </div>
            <div className="panel table-panel">
              <div className="panel-title"><h2>回复队列</h2><span className="muted">{autoReplies.length} 条</span></div>
              <table>
                <thead><tr><th>客户</th><th>消息</th><th>状态</th></tr></thead>
                <tbody>
                  {autoReplies.length === 0 ? <tr><td colSpan={3} className="empty">还没有待处理的新消息。</td></tr> : autoReplies.slice(0, 12).map((item) => (
                    <tr key={item.id}>
                      <td>{short(item.wxid, 18)}</td>
                      <td>{short(item.inbound_text, 42)}{item.handoff_reason ? <div className="muted">{item.handoff_reason}</div> : null}</td>
                      <td>{labelStatus(item.status) || item.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {activeView === "moments" && (
          <section className="main-grid">
            <div className="panel">
              <div className="panel-title"><h2>朋友圈营销</h2><span className="muted">只对白名单候选操作</span></div>
              <p className="plain-copy">第一版只扫描当前可见朋友圈动态并保存截图。点赞和评论必须命中白名单，否则会被后端直接拦截。</p>
              <div className="button-row">
                <button className="primary-button" disabled={busyAction !== null} onClick={() => void scanMoments()}><Image size={16} />扫描可见动态</button>
                <button className="danger-button" disabled={busyAction !== null || momentsItems.length === 0} onClick={() => void runFirstMomentLike()}><CheckCircle2 size={16} />点赞第一个白名单</button>
              </div>
            </div>
            <div className="panel table-panel">
              <div className="panel-title"><h2>候选动态</h2><span className="muted">{momentsItems.length} 条</span></div>
              <table>
                <thead><tr><th>对象</th><th>片段</th><th>来源</th></tr></thead>
                <tbody>
                  {momentsItems.length === 0 ? <tr><td colSpan={3} className="empty">先打开微信朋友圈页面，再点击扫描。</td></tr> : momentsItems.map((item) => (
                    <tr key={`${item.target_id}-${item.snippet || ""}`}>
                      <td>{item.owner || item.target_id}</td>
                      <td>{short(item.snippet, 48)}</td>
                      <td>{item.whitelisted ? "白名单" : item.source || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {activeView === "results" && (
          <section className="main-grid">
            <div className="panel">
              <div className="panel-title"><h2>本次结果</h2><span className="muted">客户只需要看这几个数</span></div>
              <div className="summary-box">
                <span>已发送</span><strong>{touchQueue?.stats.sent || sentCount}</strong>
                <span>已跳过</span><strong>{touchQueue?.stats.skipped || 0}</strong>
                <span>失败/拦截</span><strong>{(touchQueue?.stats.failed || 0) + (touchQueue?.stats.blocked || blockedCount)}</strong>
              </div>
            </div>
            <div className="panel table-panel">
              <div className="panel-title"><h2>失败和拦截原因</h2><span className="muted">{visibleResultEvents.length} 条记录</span></div>
              <table>
                <thead><tr><th>结果</th><th>说明</th><th>截图</th></tr></thead>
                <tbody>
                  {visibleResultEvents.length === 0 ? <tr><td colSpan={3} className="empty">暂无失败或拦截。</td></tr> : visibleResultEvents.slice(0, 12).map((event) => (
                    <tr key={event.id}><td>{labelStatus(event.status)}</td><td>{labelReason(event.message)}</td><td>{event.evidence_path ? "有" : "-"}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
            <details className="panel table-panel diagnostics">
              <summary>截图证据 <span className="muted">{evidence.length} 个文件</span><ChevronRight size={16} /></summary>
              <table>
                <thead><tr><th>客户</th><th>步骤</th><th>文件</th></tr></thead>
                <tbody>
                  {evidence.length === 0 ? <tr><td colSpan={3} className="empty">暂无截图。</td></tr> : evidence.slice(0, 12).map((item) => (
                    <tr key={item.id}><td>{short(item.target_id, 18)}</td><td>{labelReason(item.kind)}</td><td>{short(item.path, 38)}</td></tr>
                  ))}
                </tbody>
              </table>
            </details>
          </section>
        )}

        {activeView === "settings" && (
          <section className="main-grid">
            <div className="panel">
              <div className="panel-title"><h2>护栏设置</h2></div>
              <div className="summary-box">
                <span>触达间隔</span><strong>{settings ? `${settings.contact_touch_interval_days} 天` : "-"}</strong>
                <span>当前模式</span><strong>{touchIntervalModeLabel}</strong>
                <span>消息前缀</span><strong>{settings?.rpa_send_prefix || "-"}</strong>
                <span>发送策略</span><strong>{canAutoSend ? "受控窗口小批量" : sendCalibrated ? "单人验证" : "未校准不发送"}</strong>
              </div>
              <div className="button-row">
                <button className="primary-button" onClick={() => void switchTouchIntervalMode()} disabled={busyAction !== null}>
                  {settings?.touch_interval_mode === "test_ignore" ? "切回正式 15 天规则" : "切到测试可重复发送"}
                </button>
              </div>
            </div>
            <details className="panel diagnostics">
              <summary>高级诊断 <ChevronRight size={16} /></summary>
              <div className="kv-grid">
                <span>后端服务</span><strong>{stateFromHealth(appHealth, appError)}</strong>
                <span>自动化服务</span><strong>{stateFromHealth(serviceHealth, serviceError)}</strong>
                <span>微信进程</span><strong>{settings?.wechat_process_name || "-"}</strong>
                <span>窗口标题</span><strong>{probe?.window_title || "-"}</strong>
                <span>截图记录</span><strong>{evidence.length}</strong>
                <span>审计记录</span><strong>{audits.length}</strong>
                <span>发送通道</span><strong>{sendDriverProbe?.verified ? "已验证" : sendCalibrated ? "已校准" : "待校准"}</strong>
              </div>
              <div className="button-row diagnostics-actions">
                <button className="primary-button" onClick={() => void importPrompt()} disabled={busyAction !== null}><FileText size={16} />导入默认话术</button>
                <button className="primary-button" onClick={() => void preparePreview()} disabled={busyAction !== null || touchableContacts.length === 0}><ClipboardList size={16} />生成预览</button>
                <button className="primary-button" onClick={() => void buildPersistentQueue()} disabled={busyAction !== null || touchableContacts.length === 0}><ClipboardList size={16} />生成队列</button>
                <button className="primary-button" onClick={() => void calibrateWechatWindow()} disabled={busyAction !== null || !wechatReady}><Radar size={16} />校准微信窗口</button>
                <button className="primary-button" onClick={() => void openFirstConversation()} disabled={busyAction !== null || touchableContacts.length === 0 || !sendCalibrated}><MessageSquareText size={16} />只打开会话</button>
                <button className="danger-button" onClick={() => void runSmallBatch()} disabled={busyAction !== null || touchableContacts.length === 0 || !canRunControlledSend}><Send size={16} />开始小批量</button>
                <button className="danger-button" onClick={() => void runNextQueueBatch()} disabled={busyAction !== null || !canRunControlledSend}><Send size={16} />跑下一批</button>
                <button className="primary-button" onClick={() => void scanAutoReplyMessages()} disabled={busyAction !== null}><MessageSquareText size={16} />扫新消息</button>
                <button className="primary-button" onClick={() => void scanMoments()} disabled={busyAction !== null}><Image size={16} />扫朋友圈</button>
                <button className="ghost-button" onClick={() => void runTaskControl(currentTask?.paused ? "resume" : "pause")} disabled={busyAction !== null}>
                  <PauseCircle size={16} />{currentTask?.paused ? "继续" : "暂停"}
                </button>
              </div>
            </details>
          </section>
        )}
      </section>
    </main>
  );
}
