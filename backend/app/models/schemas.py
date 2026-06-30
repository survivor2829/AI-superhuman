from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskStatus(StrEnum):
    pending = "pending"
    preflight = "preflight"
    running = "running"
    verifying = "verifying"
    succeeded = "succeeded"
    failed = "failed"
    blocked = "blocked"
    stopped = "stopped"
    paused = "paused"


class AutomationAction(BaseModel):
    action_type: str
    account_id: str
    target_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class WechatAccount(BaseModel):
    id: str
    wxid: str
    nickname: str
    status: str = "unknown"
    last_seen_at: datetime | None = None


class Contact(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    account_id: str
    wxid: str
    nickname: str = ""
    remark: str = ""
    alias: str = ""
    raw_wxid: str = ""
    wechat_account_dir: str = ""
    sync_batch_id: str = ""
    last_synced_at: datetime | None = None
    local_type: int | None = None
    contact_flag: int | None = None
    delete_flag: int | None = None
    verify_flag: int | None = None
    is_chatroom_member: bool = False
    excluded_reason: str = ""
    tags: list[str] = Field(default_factory=list)
    source: str = "sidecar"
    eligible_for_touch: bool = True
    eligibility_reason: str = "eligible"
    confirmed_for_touch: bool = False


class Conversation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    contact_id: str
    last_message_at: datetime | None = None
    unread_count: int = 0


class AutomationPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    plan_type: str
    name: str
    status: str = "draft"
    schedule: dict[str, Any] = Field(default_factory=dict)
    quota: dict[str, Any] = Field(default_factory=dict)
    whitelist: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class TaskRun(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    action_type: str
    status: TaskStatus = TaskStatus.pending
    step: str = "created"
    progress: int = 0
    error: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None


class AuditLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    actor: str = "system"
    action: str
    target: str
    payload_hash: str
    result: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AIReplyRequest(BaseModel):
    account_id: str
    contact_id: str
    message: str
    tone: str = "professional"


class AIReplyResponse(BaseModel):
    reply: str
    provider: str
    intent_label: str = "unknown"
    handoff_required: bool = False
    handoff_reason: str = ""
    risk_flags: list[str] = Field(default_factory=list)
    recommended_next_action: str = ""


class TaskEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    status: TaskStatus
    message: str
    evidence_path: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
