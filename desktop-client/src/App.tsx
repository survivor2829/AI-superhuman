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
import { api, AuditLog, Contact, CurrentTaskStatus, EvidenceFile, Health, PromptImportResponse, SendDriverProbe, Settings, TaskEvent, TaskRun, TouchPreview, WindowProbe } from "./lib/api";

type ViewId = "home" | "prompt" | "contacts" | "send" | "results" | "settings";
type ServiceState = "online" | "offline" | "checking";

const NAV_ITEMS: Array<{ id: ViewId; label: string; icon: typeof Activity }> = [
  { id: "home", label: "首页", icon: Activity },
  { id: "prompt", label: "话术", icon: FileText },
  { id: "contacts", label: "客户", icon: UsersRound },
  { id: "send", label: "发送", icon: Send },
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
  tag_excluded: "已排除",
  manually_excluded: "手动排除",
  contact_db_needs_decryption: "通讯录库需要解密",
  wechat_local_account_not_found: "未找到本地微信账号",
  touch_interval_active: "15 天内已触达",
  blocked_wrong_search_surface: "搜索进入了非聊天页面",
  blocked_ambiguous_target: "找到多个同名结果",
  blocked_target_not_found: "未找到客户",
  blocked_conversation_mismatch: "打开的会话不匹配",
  blocked_message_input_missing: "没有找到聊天输入框",
  failed_message_not_verified: "发送后未核验到消息",
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
      api.evidence().then(setEvidence).catch(() => setEvidence([]))
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
    setNotice("正在静默同步本机微信通讯录...");
    const result = await api.syncContacts();
    setNotice(`同步到 ${result.friend_count || result.synced} 个微信好友，排除 ${result.group_member_excluded || 0} 个群聊成员、${result.system_excluded || 0} 个系统项`);
    await refresh();
    setActiveView("contacts");
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
  const promptReady = Boolean(promptInfo) || Boolean(settings?.deepseek_api_key_configured);
  const canAutoSend = sendDriverProbe?.verified === true;
  const maxBatchSize = sendDriverProbe?.max_batch_size || 0;
  const canRunControlledSend = maxBatchSize > 0;
  const sendCalibrated = sendDriverProbe?.calibrated === true;
  const sendBlockedMessage = sendDriverProbe?.message || "请先校准微信窗口，未执行发送";
  const sendDriverCandidates = sendDriverProbe?.candidates || [];

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
          <button className="primary-button" onClick={() => void importPrompt()} disabled={busyAction !== null}><FileText size={16} />导入默认话术</button>
          <button className="primary-button" onClick={() => promptFileInput.current?.click()} disabled={busyAction !== null}><FileUp size={16} />选择话术文件</button>
          <input ref={promptFileInput} className="file-input" type="file" accept=".docx" onChange={(event) => void importPromptFile(event)} />
          <button className="primary-button" onClick={() => void syncContacts()} disabled={busyAction !== null}><UsersRound size={16} />静默同步通讯录</button>
          <button className="primary-button" onClick={() => void preparePreview()} disabled={busyAction !== null || touchableContacts.length === 0}><ClipboardList size={16} />生成预览</button>
          <button className="primary-button" onClick={() => void calibrateWechatWindow()} disabled={busyAction !== null || !wechatReady}><Radar size={16} />校准微信窗口</button>
          <button className="primary-button" onClick={() => void openFirstConversation()} disabled={busyAction !== null || touchableContacts.length === 0 || !sendCalibrated}><MessageSquareText size={16} />只打开会话</button>
          <button className="danger-button" onClick={() => void runSmallBatch()} disabled={busyAction !== null || touchableContacts.length === 0 || !canRunControlledSend}><Send size={16} />{canAutoSend ? "开始小批量" : canRunControlledSend ? "开始 1 人验证" : "待校准"}</button>
          <button className="ghost-button" onClick={() => void runTaskControl(currentTask?.paused ? "resume" : "pause")} disabled={busyAction !== null}>
            <PauseCircle size={16} />{currentTask?.paused ? "继续" : "暂停"}
          </button>
          <span className="notice">{notice}</span>
        </section>

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
                <h2>待触达客户</h2>
                <span className="muted">本次将触达 {touchableContacts.length} 人</span>
              </div>
              <table>
                <thead><tr><th>客户</th><th>来源</th><th>操作</th></tr></thead>
                <tbody>
                  {localContacts.length === 0 ? <tr><td colSpan={3} className="empty">先静默同步通讯录。</td></tr> : touchableContacts.length === 0 ? <tr><td colSpan={3} className="empty">当前没有待触达客户。</td></tr> : touchableContacts.map((contact) => (
                    <tr key={contact.id}>
                      <td><strong>{contact.remark || contact.nickname || contact.wxid}</strong><div className="muted">{short(contact.wxid, 34)}</div></td>
                      <td>微信好友</td>
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
              <summary>已排除 / 已移除 <ChevronRight size={16} /></summary>
              <table>
                <thead><tr><th>对象</th><th>原因</th><th>标记</th></tr></thead>
                <tbody>
                  {excludedContacts.length === 0 ? <tr><td colSpan={3} className="empty">暂无排除项。</td></tr> : excludedContacts.map((contact) => (
                    <tr key={contact.id}>
                      <td>{contact.remark || contact.nickname || contact.wxid}</td>
                      <td>{labelReason(contact.excluded_reason || contact.eligibility_reason)}</td>
                      <td>{contact.contact_flag ? `flag=${contact.contact_flag}` : "-"}</td>
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

        {activeView === "results" && (
          <section className="main-grid">
            <div className="panel table-panel">
              <div className="panel-title"><h2>发送结果</h2><span className="muted">{events.length} 条记录</span></div>
              <table>
                <thead><tr><th>结果</th><th>说明</th><th>截图</th></tr></thead>
                <tbody>
                  {events.length === 0 ? <tr><td colSpan={3} className="empty">还没有发送记录。</td></tr> : events.slice(0, 12).map((event) => (
                    <tr key={event.id}><td>{labelStatus(event.status)}</td><td>{labelReason(event.message)}</td><td>{event.evidence_path ? "有" : "-"}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="panel table-panel">
              <div className="panel-title"><h2>截图证据</h2><span className="muted">{evidence.length} 个文件</span></div>
              <table>
                <thead><tr><th>客户</th><th>步骤</th><th>文件</th></tr></thead>
                <tbody>
                  {evidence.length === 0 ? <tr><td colSpan={3} className="empty">暂无截图。</td></tr> : evidence.slice(0, 12).map((item) => (
                    <tr key={item.id}><td>{short(item.target_id, 18)}</td><td>{labelReason(item.kind)}</td><td>{short(item.path, 38)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {activeView === "settings" && (
          <section className="main-grid">
            <div className="panel">
              <div className="panel-title"><h2>护栏设置</h2></div>
              <div className="summary-box">
                <span>触达间隔</span><strong>{settings ? `${settings.contact_touch_interval_days} 天` : "-"}</strong>
                <span>消息前缀</span><strong>{settings?.rpa_send_prefix || "-"}</strong>
                <span>发送策略</span><strong>{canAutoSend ? "受控窗口小批量" : sendCalibrated ? "单人验证" : "未校准不发送"}</strong>
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
            </details>
          </section>
        )}
      </section>
    </main>
  );
}
