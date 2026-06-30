from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.core.config import AgentSettings
from app.models.schemas import AIReplyRequest, AIReplyResponse, AutomationAction, AutomationPlan, TaskStatus
from app.services.llm import LLMRouter
from app.services.message_cleaner import clean_outbound_message
from app.services.prompt_loader import PromptLoader
from app.services.store import AgentStore
from app.services.task_engine import TaskEngine
from app.services.touch import TouchPlanner

settings = AgentSettings.load()
app = FastAPI(title="Agent Production Backend", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)
store = AgentStore(settings.database_url)
store.create_schema()
llm = LLMRouter(settings)
legacy_engine = TaskEngine()
prompt_loader = PromptLoader()


class ImportPromptRequest(BaseModel):
    path: str | None = None
    name: str = "玺联惠创客合伙人"


class TouchPlanCreateRequest(BaseModel):
    name: str = "小批量触达"
    target_limit: int = Field(default=5, ge=1, le=20)
    message_goal: str = "引导客户留下需求或预约上海展厅看实机"


class TouchRunRequest(BaseModel):
    limit: int = Field(default=5, ge=1, le=20)
    message_goal: str = "引导客户留下需求或预约上海展厅看实机"
    direct_send: bool = True


class ContactSyncRequest(BaseModel):
    mode: str = "local_db_full"
    account_id: str = "auto"
    auto_confirm: bool = True
    auto_decrypt: bool = True


class TaskControlRequest(BaseModel):
    action: str


runtime_control_state: dict[str, Any] = {
    "paused": False,
    "stopped": False,
    "last_action": "",
    "updated_at": None,
}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "backend"}


@app.get("/settings")
def public_settings() -> dict[str, object]:
    return settings.public_dict()


@app.post("/auth/login")
def login() -> dict[str, str]:
    return {"token": "local-dev-token", "operator": "local"}


@app.post("/prompts/import-docx")
def import_prompt(request: ImportPromptRequest) -> dict[str, Any]:
    source = Path(request.path) if request.path else settings.prompt_docx_path
    imported = prompt_loader.load(source)
    profile = store.save_ai_profile(name=request.name, imported=imported)
    return _prompt_profile_response(profile)


@app.post("/prompts/import-docx/file")
async def import_prompt_file(file: UploadFile = File(...), name: str = "玺联惠创客合伙人") -> dict[str, Any]:
    if not file.filename or Path(file.filename).suffix.lower() != ".docx":
        raise HTTPException(status_code=400, detail="please_upload_docx_file")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty_docx_file")

    upload_dir = Path(__file__).resolve().parents[2] / "prompts" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    source = upload_dir / f"{uuid4().hex}.docx"
    source.write_bytes(content)

    imported = prompt_loader.load(source)
    profile = store.save_ai_profile(name=name, imported=imported)
    response = _prompt_profile_response(profile)
    response["uploaded_filename"] = file.filename
    return response


def _prompt_profile_response(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "profile_id": profile["id"],
        "source_path": profile["source_path"],
        "knowledge_count": len(profile["knowledge_base"]),
        "handoff_rules": profile["handoff_rules"],
        "system_prompt_preview": profile["system_prompt"][:120],
    }


@app.post("/ai/reply", response_model=AIReplyResponse)
@app.post("/chat/ai-reply", response_model=AIReplyResponse)
def ai_reply(request: AIReplyRequest) -> AIReplyResponse:
    profile = store.latest_ai_profile()
    if profile is None and settings.prompt_docx_path.exists():
        imported = prompt_loader.load(settings.prompt_docx_path)
        profile = store.save_ai_profile(name="default", imported=imported)
    system_prompt = profile["system_prompt"] if profile else "你是专业销售顾问，回复要简洁自然。"
    knowledge = "\n".join(f"问题：{item['question']}\n答案：{item['answer']}" for item in (profile or {}).get("knowledge_base", []))
    draft = llm.draft_reply(system_prompt=system_prompt, knowledge_base=knowledge, message=request.message)
    return AIReplyResponse(
        reply=draft.reply_text,
        provider=llm.provider,
        intent_label=draft.intent_label,
        handoff_required=draft.handoff_required,
        handoff_reason=draft.handoff_reason,
        risk_flags=draft.risk_flags,
        recommended_next_action=draft.recommended_next_action,
    )


@app.get("/wechat/status")
def wechat_status() -> dict[str, object]:
    return _sidecar_get("/wechat/status")


@app.get("/wechat/window/probe")
def window_probe() -> dict[str, object]:
    return _sidecar_get("/wechat/window/probe")


@app.post("/wechat/window/normalize")
def normalize_wechat_window() -> dict[str, object]:
    return _sidecar_post("/wechat/window/normalize", {})


@app.post("/wechat/window/prepare-dedicated-desktop")
def prepare_dedicated_desktop() -> dict[str, object]:
    return _sidecar_post("/wechat/window/prepare-dedicated-desktop", {})


@app.get("/send/driver/probe")
def send_driver_probe() -> dict[str, object]:
    return _sidecar_get("/send/driver/probe")


@app.post("/send/driver/calibrate")
def calibrate_send_driver() -> dict[str, object]:
    return _sidecar_post("/send/driver/calibrate", {})


@app.get("/wechat/accounts/local")
def local_wechat_accounts() -> dict[str, object]:
    return _sidecar_get("/wechat/accounts/local")


@app.post("/wechat/contacts/sync")
def sync_contacts(request: ContactSyncRequest = ContactSyncRequest()) -> dict[str, object]:
    if request.mode != "local_db_full":
        raise HTTPException(status_code=400, detail="contact_sync_only_supports_local_db_full")
    result = _sidecar_post(
        "/wechat/contacts/sync",
        {
            "mode": request.mode,
            "account_id": request.account_id,
            "auto_decrypt": request.auto_decrypt,
        },
    )
    contacts = result.get("contacts") or []
    excluded = result.get("excluded") or []
    account_id = str(result.get("account_id") or request.account_id or "auto")
    saved = store.upsert_synced_contacts(
        account_id=account_id,
        contacts=list(contacts),
        auto_confirm=request.auto_confirm,
        excluded=list(excluded),
    )
    return {
        "synced": len(saved),
        "excluded": len(excluded),
        "friend_count": int(result.get("friend_count") or len(saved)),
        "excluded_count": int(result.get("excluded_count") or len(excluded)),
        "group_member_excluded": int(result.get("group_member_excluded") or 0),
        "system_excluded": int(result.get("system_excluded") or 0),
        "filter_version": str(result.get("filter_version") or "wechat4_friend_only_v1"),
        "contacts": [contact.model_dump(mode="json") for contact in saved],
        "mode": request.mode,
        "account_id": account_id,
        "sidecar": result,
    }


@app.get("/wechat/contacts")
def contacts() -> list[dict[str, object]]:
    return [contact.model_dump(mode="json") for contact in store.list_contacts()]


@app.post("/wechat/contacts/{contact_id}/confirm-touch")
def confirm_contact_for_touch(contact_id: str) -> dict[str, object]:
    return store.set_contact_touch_confirmation(contact_id, confirmed=True).model_dump(mode="json")


@app.post("/wechat/contacts/{contact_id}/exclude-touch")
def exclude_contact_for_touch(contact_id: str) -> dict[str, object]:
    return store.exclude_contact_from_touch(contact_id).model_dump(mode="json")


@app.get("/chat/sessions")
def chat_sessions() -> list[dict[str, str]]:
    return []


@app.get("/chat/history")
def chat_history(contact_id: str | None = None) -> dict[str, object]:
    return {"contact_id": contact_id, "messages": []}


@app.post("/wechat/message/open-conversation")
def open_wechat_conversation(action: AutomationAction):
    task = store.create_task(action_type="message.open_conversation", target_id=action.target_id, status=TaskStatus.preflight)
    store.add_task_event(task_id=task.id, status=TaskStatus.preflight, message="preflight")
    payload = {**action.payload}
    payload["search_terms"] = _search_terms_for_target(action.target_id, payload)
    result = _sidecar_post(
        "/wechat/message/open-conversation",
        {
            "action_type": "message.open_conversation",
            "target_id": action.target_id,
            "payload": payload,
        },
    )
    evidence = result.get("evidence") or {}
    evidence_path = _first_evidence_path(evidence)
    for kind, path in evidence.items():
        if isinstance(path, str) and (path.endswith(".png") or path.endswith(".txt")):
            store.add_evidence_file(path=path, task_id=task.id, target_id=action.target_id, kind=str(kind))
    verification_status = str(result.get("verification_status") or "")
    success = bool(result.get("success")) and verification_status == "verified"
    if success:
        status = TaskStatus.succeeded
    elif verification_status == "blocked":
        status = TaskStatus.blocked
    else:
        status = TaskStatus.failed
    message = str(result.get("message") or result.get("failure_reason") or "open_conversation_failed")
    updated = store.update_task(
        task.id,
        status=status,
        step="completed" if success else status.value,
        progress=100,
        error=None if success else message,
    )
    store.add_task_event(task_id=task.id, status=status, message=message, evidence_path=evidence_path)
    store.add_audit_log(action="message.open_conversation", target=action.target_id, payload={"search_terms": payload["search_terms"]}, result=message, evidence_path=evidence_path)
    return {"task": updated.model_dump(mode="json"), "sidecar": result}


@app.post("/wechat/message/send")
@app.post("/chat/send")
def send_message(action: AutomationAction):
    content = str(action.payload.get("content") or "")
    content = clean_outbound_message(content, prefix=settings.rpa_send_prefix)
    task = store.create_task(action_type="message.send", target_id=action.target_id, status=TaskStatus.preflight)
    store.add_task_event(task_id=task.id, status=TaskStatus.preflight, message="preflight")
    result = _sidecar_post(
        "/wechat/message/send",
        {
            "action_type": "message.send",
            "target_id": action.target_id,
            "payload": {**action.payload, "content": content},
        },
    )
    evidence = result.get("evidence") or {}
    evidence_path = _first_evidence_path(evidence)
    for kind, path in evidence.items():
        if isinstance(path, str) and (path.endswith(".png") or path.endswith(".txt")):
            store.add_evidence_file(path=path, task_id=task.id, target_id=action.target_id, kind=str(kind))
    verification_status = str(result.get("verification_status") or "")
    success = bool(result.get("success")) and verification_status == "verified"
    if success:
        status = TaskStatus.succeeded
    elif verification_status == "blocked":
        status = TaskStatus.blocked
    else:
        status = TaskStatus.failed
    message = str(result.get("message") or result.get("failure_reason") or "send_failed")
    updated = store.update_task(
        task.id,
        status=status,
        step="completed" if success else status.value,
        progress=100,
        error=None if success else message,
    )
    store.add_task_event(task_id=task.id, status=status, message=message, evidence_path=evidence_path)
    store.add_audit_log(action="message.send", target=action.target_id, payload={"content": content}, result=message, evidence_path=evidence_path)
    return {"task": updated.model_dump(mode="json"), "sidecar": result}


@app.get("/mass-send/plans")
def list_mass_send_plans() -> list[AutomationPlan]:
    return store.list_plans("mass_send")


@app.post("/mass-send/plans")
def create_mass_send_plan(plan: AutomationPlan) -> AutomationPlan:
    return store.upsert_plan(plan_type="mass_send", name=plan.name, status=plan.status, payload=plan.payload)


@app.get("/touch/plans")
def list_touch_plans() -> list[AutomationPlan]:
    return store.list_plans("touch")


@app.post("/touch/plans")
def create_touch_plan(request: TouchPlanCreateRequest) -> AutomationPlan:
    return store.upsert_plan(
        plan_type="touch",
        name=request.name,
        status="ready",
        payload={"target_limit": request.target_limit, "message_goal": request.message_goal},
    )


@app.post("/touch/plans/{plan_id}/run")
def run_touch_plan(plan_id: str, request: TouchRunRequest) -> dict[str, object]:
    send_probe = send_driver_probe()
    max_batch_size = int(send_probe.get("max_batch_size") or (3 if bool(send_probe.get("verified")) else 0))
    if max_batch_size < 1:
        return {
            "plan_id": plan_id,
            "ran": 0,
            "results": [],
            "message": str(send_probe.get("message") or "请先校准微信窗口，未执行发送"),
            "send_driver": send_probe,
        }
    effective_limit = min(request.limit, max_batch_size)

    planner = TouchPlanner(store, touch_interval_days=settings.contact_touch_interval_days)
    contacts = store.list_contacts(
        limit=effective_limit,
        eligible_for_touch=True,
        confirmed_for_touch=True,
        source="wechat_local_contact_db",
    )
    if not contacts:
        return {"plan_id": plan_id, "ran": 0, "results": [], "message": "请先确认客户"}

    results: list[dict[str, object]] = []
    profile = store.latest_ai_profile()
    if profile is None and settings.prompt_docx_path.exists():
        profile = store.save_ai_profile(name="default", imported=prompt_loader.load(settings.prompt_docx_path))
    system_prompt = profile["system_prompt"] if profile else "你是专业销售顾问，回复要简洁自然。"
    knowledge = "\n".join(f"问题：{item['question']}\n答案：{item['answer']}" for item in (profile or {}).get("knowledge_base", []))

    for contact in contacts[:effective_limit]:
        decision = planner.evaluate(plan_id=plan_id, contact_id=contact.id)
        if not decision.allowed:
            results.append({"contact_id": contact.id, "wxid": contact.wxid, "status": "skipped", "reason": decision.reason, "next_touch_at": decision.next_touch_at})
            continue
        draft = llm.draft_reply(
            system_prompt=system_prompt,
            knowledge_base=knowledge,
            message=f"请生成一条给 {contact.nickname or contact.wxid} 的首次触达微信短句，目标：{request.message_goal}",
        )
        message_result = send_message(
            AutomationAction(
                action_type="message.send",
                account_id=contact.account_id,
                target_id=contact.wxid,
                payload={
                    "content": draft.reply_text,
                    "intent_label": draft.intent_label,
                    "handoff_required": draft.handoff_required,
                    "search_terms": _search_terms_for_contact(contact),
                },
            )
        )
        sidecar_result = message_result.get("sidecar") or {}
        success = bool(sidecar_result.get("success"))
        verification_status = str(sidecar_result.get("verification_status") or "")
        success = success and verification_status == "verified"
        if success:
            store.mark_contact_touched(plan_id=plan_id, contact_id=contact.id, touched_at=datetime.now(UTC))
        status = "sent" if success else "blocked" if verification_status == "blocked" else "failed"
        results.append({"contact_id": contact.id, "wxid": contact.wxid, "status": status, "reply": draft.reply_text, "result": message_result})
        if _should_stop_touch_batch(sidecar_result):
            break
    return {"plan_id": plan_id, "ran": len(results), "allowed_limit": max_batch_size, "requested_limit": request.limit, "results": results}


@app.post("/touch/plans/{plan_id}/preview")
def preview_touch_plan(plan_id: str, request: TouchRunRequest) -> dict[str, object]:
    planner = TouchPlanner(store, touch_interval_days=settings.contact_touch_interval_days)
    contacts = store.list_contacts(
        limit=request.limit,
        eligible_for_touch=True,
        confirmed_for_touch=True,
        source="wechat_local_contact_db",
    )
    preview: list[dict[str, object]] = []
    for contact in contacts[: request.limit]:
        decision = planner.evaluate(plan_id=plan_id, contact_id=contact.id)
        preview.append(
            {
                "contact_id": contact.id,
                "wxid": contact.wxid,
                "nickname": contact.nickname,
                "search_terms": _search_terms_for_contact(contact),
                "allowed": decision.allowed,
                "reason": decision.reason,
                "next_touch_at": decision.next_touch_at,
            }
        )
    return {
        "plan_id": plan_id,
        "count": len(preview),
        "send_prefix": settings.rpa_send_prefix,
        "targets": preview,
    }


@app.post("/moments/publish-plans")
def create_moments_publish_plan(plan: AutomationPlan) -> AutomationPlan:
    return store.upsert_plan(plan_type="moments_publish", name=plan.name, status=plan.status, payload=plan.payload)


@app.post("/moments/marketing-plans")
def create_moments_marketing_plan(plan: AutomationPlan) -> AutomationPlan:
    return store.upsert_plan(plan_type="moments_marketing", name=plan.name, status=plan.status, payload=plan.payload)


@app.get("/moments/feed/scan")
def scan_moments_feed() -> dict[str, object]:
    return {"items": [], "message": "moments_feed_scan_requires_visible_feed"}


@app.post("/moments/interactions/run")
def run_moments_interactions(action: AutomationAction):
    result = _sidecar_post(
        "/wechat/moments/comment" if action.action_type == "moments.comment" else "/wechat/moments/like",
        {"action_type": action.action_type, "target_id": action.target_id, "payload": action.payload},
    )
    store.add_audit_log(action=action.action_type, target=action.target_id, payload=action.payload, result=str(result.get("message")))
    return result


@app.get("/tasks")
def list_tasks():
    return [task.model_dump(mode="json") for task in store.list_tasks()]


@app.get("/tasks/events")
def list_task_events():
    return [event.model_dump(mode="json") for event in store.list_task_events()]


@app.get("/tasks/current")
def current_task() -> dict[str, object]:
    tasks = store.list_tasks(limit=1)
    if not tasks:
        return {
            "active": False,
            "stage": "idle",
            "stage_label": "空闲中",
            "customer": "",
            "progress": 0,
            "message": "还没有运行中的任务",
            "can_pause": False,
            "paused": bool(runtime_control_state["paused"]),
            "stopped": bool(runtime_control_state["stopped"]),
        }
    task = tasks[0]
    events = store.list_task_events(task_id=task.id, limit=20)
    last_event = events[-1] if events else None
    message = last_event.message if last_event else task.error or task.step
    return {
        "active": task.status not in {TaskStatus.succeeded, TaskStatus.failed, TaskStatus.blocked, TaskStatus.stopped},
        "task": task.model_dump(mode="json"),
        "stage": _runtime_stage(task.status, message),
        "stage_label": _runtime_stage_label(task.status, message),
        "customer": task.target_id,
        "progress": task.progress,
        "message": _friendly_runtime_message(message),
        "can_pause": task.status in {TaskStatus.preflight, TaskStatus.running, TaskStatus.verifying},
        "paused": bool(runtime_control_state["paused"]) or task.status == TaskStatus.paused,
        "stopped": bool(runtime_control_state["stopped"]) or task.status == TaskStatus.stopped,
        "last_event": last_event.model_dump(mode="json") if last_event else None,
    }


@app.post("/tasks/control")
def control_task(request: TaskControlRequest) -> dict[str, object]:
    action = request.action.strip().lower()
    if action not in {"pause", "resume", "stop"}:
        raise HTTPException(status_code=400, detail="unsupported_task_control_action")
    runtime_control_state["last_action"] = action
    runtime_control_state["updated_at"] = datetime.now(UTC).isoformat()
    tasks = store.list_tasks(limit=1)
    task = tasks[0] if tasks else None

    if action == "pause":
        runtime_control_state["paused"] = True
        if task and task.status in {TaskStatus.preflight, TaskStatus.running, TaskStatus.verifying}:
            store.update_task(task.id, status=TaskStatus.paused, step="paused", progress=task.progress, error="operator_paused")
            store.add_task_event(task_id=task.id, status=TaskStatus.paused, message="operator_paused")
    elif action == "resume":
        runtime_control_state["paused"] = False
        runtime_control_state["stopped"] = False
        if task and task.status == TaskStatus.paused:
            store.update_task(task.id, status=TaskStatus.running, step="running", progress=task.progress, error=None)
            store.add_task_event(task_id=task.id, status=TaskStatus.running, message="operator_resumed")
    else:
        runtime_control_state["stopped"] = True
        runtime_control_state["paused"] = False
        sidecar_result = _sidecar_post("/rpa/stop", {})
        if task and task.status not in {TaskStatus.succeeded, TaskStatus.failed, TaskStatus.blocked, TaskStatus.stopped}:
            store.update_task(task.id, status=TaskStatus.stopped, step="stopped", progress=task.progress, error="operator_stopped")
            store.add_task_event(task_id=task.id, status=TaskStatus.stopped, message="operator_stopped")
        return {"ok": True, "action": action, "sidecar": sidecar_result, "current": current_task()}
    return {"ok": True, "action": action, "current": current_task()}


@app.get("/tasks/{task_id}")
def get_task(task_id: str):
    return next((task.model_dump(mode="json") for task in store.list_tasks() if task.id == task_id), {"error": "not_found"})


@app.get("/evidence/files")
def evidence_files():
    return store.list_evidence_files()


@app.get("/audit/logs")
def audit_logs():
    return store.list_audit_logs()


@app.websocket("/ws/tasks")
async def ws_tasks(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"type": "snapshot", "events": [event.model_dump(mode="json") for event in store.list_task_events(limit=50)]})
    await websocket.close()


def _sidecar_get(path: str) -> dict[str, object]:
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{settings.rpa_sidecar_url}{path}")
            response.raise_for_status()
            return response.json()
    except Exception as exc:
        return {"success": False, "message": f"sidecar_unavailable:{type(exc).__name__}"}


def _sidecar_post(path: str, payload: dict) -> dict[str, object]:
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(f"{settings.rpa_sidecar_url}{path}", json=payload)
            response.raise_for_status()
            return response.json()
    except Exception as exc:
        return {"success": False, "message": f"sidecar_unavailable:{type(exc).__name__}", "evidence": {}}


def _first_evidence_path(evidence: dict[str, object]) -> str | None:
    for value in evidence.values():
        if isinstance(value, str) and (value.endswith(".png") or value.endswith(".txt")):
            return value
    return None


def _search_terms_for_contact(contact: Any) -> list[str]:
    terms: list[str] = []
    for value in [
        getattr(contact, "remark", ""),
        getattr(contact, "nickname", ""),
        getattr(contact, "alias", ""),
        getattr(contact, "wxid", ""),
    ]:
        cleaned = str(value or "").strip()
        if cleaned and cleaned not in terms:
            terms.append(cleaned)
    return terms


def _search_terms_for_target(target_id: str, payload: dict[str, Any]) -> list[str]:
    payload_terms = [str(term).strip() for term in payload.get("search_terms") or [] if str(term).strip()]
    if payload_terms:
        return payload_terms
    for contact in store.list_contacts(limit=1000):
        if target_id in {contact.id, contact.wxid, contact.raw_wxid}:
            return _search_terms_for_contact(contact)
    return [target_id]


def _should_stop_touch_batch(sidecar_result: dict[str, object]) -> bool:
    reason = str(sidecar_result.get("message") or sidecar_result.get("failure_reason") or "")
    infrastructure_failures = {
        "blocked_window_not_foreground",
        "blocked_search_input_missing",
        "wechat_window_not_found",
        "wechat_hwnd_missing",
        "foreground_not_changed",
    }
    return reason in infrastructure_failures or reason.startswith("wechat_window_lost_") or reason.startswith("sidecar_unavailable:")


def _runtime_stage(status: TaskStatus, message: str = "") -> str:
    if status in {TaskStatus.pending, TaskStatus.preflight}:
        return "preparing"
    if status in {TaskStatus.running, TaskStatus.verifying}:
        return "auto_touch"
    if status == TaskStatus.paused:
        return "paused"
    if status == TaskStatus.succeeded:
        return "completed"
    if status == TaskStatus.blocked:
        return "blocked"
    if status == TaskStatus.stopped:
        return "stopped"
    if status == TaskStatus.failed:
        return "failed"
    return "auto_touch" if "send" in message else "idle"


def _runtime_stage_label(status: TaskStatus, message: str = "") -> str:
    labels = {
        "preparing": "准备中",
        "auto_touch": "自动触达中",
        "paused": "已暂停",
        "completed": "已完成",
        "blocked": "已拦截",
        "stopped": "已停止",
        "failed": "失败",
        "idle": "空闲中",
    }
    return labels[_runtime_stage(status, message)]


def _friendly_runtime_message(message: str) -> str:
    labels = {
        "preflight": "正在做发送前检查",
        "blocked_window_not_foreground": "微信没有切到前台，已停止发送",
        "foreground_not_changed": "微信没有切到前台，已停止发送",
        "wechat_window_not_found": "没有找到微信主窗口",
        "blocked_search_input_missing": "没有找到微信搜索框，已停止发送",
        "blocked_target_not_found": "没有找到客户，已停止发送",
        "blocked_target_element_missing": "没有找到客户搜索结果，已停止发送",
        "blocked_wrong_search_surface": "搜索结果不是微信联系人，已停止发送",
        "blocked_ambiguous_target": "找到多个相似客户，已停止发送",
        "blocked_conversation_mismatch": "没有进入正确会话，已停止发送",
        "blocked_message_input_missing": "没有找到聊天输入框，已停止发送",
        "failed_message_not_verified": "发送后没有校验到消息，已停止",
        "conversation_opened": "客户会话已打开，未发送消息",
        "message_sent": "消息已发送并记录",
        "operator_paused": "已暂停",
        "operator_resumed": "已继续",
        "operator_stopped": "已停止",
    }
    if message.startswith("wechat_window_lost_"):
        return "微信窗口被切走，已停止发送"
    return labels.get(message, message or "等待中")
