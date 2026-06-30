from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text, create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.models.schemas import AutomationPlan, Contact, TaskEvent, TaskRun, TaskStatus
from app.services.prompt_loader import ImportedPrompt


class Base(DeclarativeBase):
    pass


class WechatAccountRow(Base):
    __tablename__ = "wechat_accounts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    wxid: Mapped[str] = mapped_column(String, unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="unknown")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ContactRow(Base):
    __tablename__ = "contacts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(String, index=True)
    wxid: Mapped[str] = mapped_column(String, index=True)
    nickname: Mapped[str] = mapped_column(String, default="")
    remark: Mapped[str] = mapped_column(String, default="")
    alias: Mapped[str] = mapped_column(String, default="")
    raw_wxid: Mapped[str] = mapped_column(String, default="")
    wechat_account_dir: Mapped[str] = mapped_column(String, default="")
    sync_batch_id: Mapped[str] = mapped_column(String, default="")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    local_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contact_flag: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delete_flag: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verify_flag: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_chatroom_member: Mapped[int] = mapped_column(Integer, default=0)
    excluded_reason: Mapped[str] = mapped_column(String, default="")
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    source: Mapped[str] = mapped_column(String, default="sidecar")
    eligible_for_touch: Mapped[int] = mapped_column(Integer, default=1)
    eligibility_reason: Mapped[str] = mapped_column(String, default="eligible")
    confirmed_for_touch: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class ConversationRow(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    contact_id: Mapped[str] = mapped_column(String, index=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unread_count: Mapped[int] = mapped_column(Integer, default=0)


class MessageRow(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String, index=True)
    sender: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class AutomationPlanRow(Base):
    __tablename__ = "automation_plans"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    plan_type: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="draft")
    schedule_json: Mapped[str] = mapped_column(Text, default="{}")
    quota_json: Mapped[str] = mapped_column(Text, default="{}")
    whitelist_json: Mapped[str] = mapped_column(Text, default="[]")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")


class PlanTargetRow(Base):
    __tablename__ = "plan_targets"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    plan_id: Mapped[str] = mapped_column(String, index=True)
    contact_id: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    last_touched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_touch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    skip_reason: Mapped[str] = mapped_column(String, default="")


class TaskRunRow(Base):
    __tablename__ = "task_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    action_type: Mapped[str] = mapped_column(String)
    target_id: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default=TaskStatus.pending.value)
    step: Mapped[str] = mapped_column(String, default="created")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TaskEventRow(Base):
    __tablename__ = "task_events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    evidence_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class AuditLogRow(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    actor: Mapped[str] = mapped_column(String, default="system")
    action: Mapped[str] = mapped_column(String)
    target: Mapped[str] = mapped_column(String)
    payload_hash: Mapped[str] = mapped_column(String)
    result: Mapped[str] = mapped_column(String)
    evidence_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class AIProfileRow(Base):
    __tablename__ = "ai_profiles"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    source_path: Mapped[str] = mapped_column(Text, default="")
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    sales_flow: Mapped[str] = mapped_column(Text, default="")
    constraints: Mapped[str] = mapped_column(Text, default="")
    handoff_rules: Mapped[str] = mapped_column(Text, default="")
    knowledge_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class MomentPostRow(Base):
    __tablename__ = "moment_posts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(String, index=True)
    content: Mapped[str] = mapped_column(Text)
    evidence_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class MomentInteractionRow(Base):
    __tablename__ = "moment_interactions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    contact_id: Mapped[str] = mapped_column(String, index=True)
    action_type: Mapped[str] = mapped_column(String)
    comment: Mapped[str] = mapped_column(Text, default="")
    evidence_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class EvidenceFileRow(Base):
    __tablename__ = "evidence_files"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    target_id: Mapped[str] = mapped_column(String, default="")
    kind: Mapped[str] = mapped_column(String, default="screenshot")
    path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class AgentStore:
    def __init__(self, database_url: str = "sqlite:///./agent.db") -> None:
        self.engine = create_engine(database_url, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)
        self._ensure_contact_columns()
        self.refresh_contact_eligibility()
        self.cleanup_corrupt_plan_names()

    def table_names(self) -> list[str]:
        return inspect(self.engine).get_table_names()

    def upsert_contact(
        self,
        *,
        account_id: str,
        wxid: str,
        nickname: str = "",
        remark: str = "",
        alias: str = "",
        raw_wxid: str = "",
        source: str = "sidecar",
        wechat_account_dir: str = "",
        sync_batch_id: str = "",
        last_synced_at: datetime | None = None,
        local_type: int | None = None,
        contact_flag: int | None = None,
        delete_flag: int | None = None,
        verify_flag: int | None = None,
        is_chatroom_member: bool = False,
        tags: list[str] | None = None,
    ) -> Contact:
        eligibility = self.classify_contact_eligibility(
            wxid=wxid,
            nickname=nickname,
            tags=tags or [],
            local_type=local_type,
            contact_flag=contact_flag,
            delete_flag=delete_flag,
        )
        with self.SessionLocal() as session:
            row = session.scalar(select(ContactRow).where(ContactRow.account_id == account_id, ContactRow.wxid == wxid))
            if row is None:
                row = ContactRow(id=str(uuid4()), account_id=account_id, wxid=wxid)
                session.add(row)
            row.nickname = nickname or row.nickname
            row.remark = remark or row.remark
            row.alias = alias or row.alias
            row.raw_wxid = raw_wxid or row.raw_wxid or wxid
            row.source = source or row.source
            row.wechat_account_dir = wechat_account_dir or row.wechat_account_dir
            row.sync_batch_id = sync_batch_id or row.sync_batch_id
            row.last_synced_at = last_synced_at or row.last_synced_at
            row.local_type = local_type if local_type is not None else row.local_type
            row.contact_flag = contact_flag if contact_flag is not None else row.contact_flag
            row.delete_flag = delete_flag if delete_flag is not None else row.delete_flag
            row.verify_flag = verify_flag if verify_flag is not None else row.verify_flag
            row.is_chatroom_member = 1 if is_chatroom_member else row.is_chatroom_member
            row.tags_json = json.dumps(tags or json.loads(row.tags_json or "[]"), ensure_ascii=False)
            row.eligible_for_touch = 1 if eligibility["eligible"] else 0
            row.eligibility_reason = eligibility["reason"]
            row.excluded_reason = "" if eligibility["eligible"] else str(eligibility["reason"])
            if not eligibility["eligible"]:
                row.confirmed_for_touch = 0
            session.commit()
            return self._contact(row)

    def upsert_synced_contacts(
        self,
        *,
        account_id: str,
        contacts: list[dict],
        auto_confirm: bool = True,
        excluded: list[dict] | None = None,
    ) -> list[Contact]:
        synced_at = datetime.now(UTC)
        saved_rows: list[ContactRow] = []
        with self.SessionLocal() as session:
            for item in excluded or []:
                wxid = str(item.get("wxid") or item.get("nickname") or "").strip()
                if not wxid:
                    continue
                reason = str(item.get("reason") or "non_contact_ui_artifact")
                rows = session.scalars(
                    select(ContactRow).where((ContactRow.wxid == wxid) | (ContactRow.nickname == wxid))
                ).all()
                if not rows:
                    row = ContactRow(id=str(uuid4()), account_id=account_id, wxid=wxid, nickname=wxid)
                    session.add(row)
                    rows = [row]
                for row in rows:
                    row.nickname = str(item.get("nickname") or row.nickname or wxid)
                    row.raw_wxid = str(item.get("raw_wxid") or row.raw_wxid or wxid)
                    row.source = str(item.get("source") or row.source or "wechat_local_contact_db")
                    row.wechat_account_dir = str(item.get("wechat_account_dir") or row.wechat_account_dir or "")
                    row.local_type = self._optional_int(item.get("local_type"), row.local_type)
                    row.contact_flag = self._optional_int(item.get("contact_flag"), row.contact_flag)
                    row.delete_flag = self._optional_int(item.get("delete_flag"), row.delete_flag)
                    row.verify_flag = self._optional_int(item.get("verify_flag"), row.verify_flag)
                    row.is_chatroom_member = 1 if bool(item.get("is_chatroom_member")) else row.is_chatroom_member
                    row.eligible_for_touch = 0
                    row.eligibility_reason = reason
                    row.excluded_reason = reason
                    row.confirmed_for_touch = 0

            for item in contacts:
                wxid = str(item.get("wxid") or item.get("raw_wxid") or item.get("nickname") or "").strip()
                if not wxid:
                    continue
                nickname = str(item.get("nickname") or item.get("remark") or item.get("alias") or wxid)
                tags = list(item.get("tags") or ["synced", "local_db"])
                row = session.scalar(select(ContactRow).where(ContactRow.account_id == account_id, ContactRow.wxid == wxid))
                if row is None:
                    row = ContactRow(id=str(uuid4()), account_id=account_id, wxid=wxid)
                    session.add(row)
                row.nickname = nickname or row.nickname
                row.remark = str(item.get("remark") or row.remark or "")
                row.alias = str(item.get("alias") or row.alias or "")
                row.raw_wxid = str(item.get("raw_wxid") or row.raw_wxid or wxid)
                row.source = str(item.get("source") or "wechat_local_contact_db")
                row.wechat_account_dir = str(item.get("wechat_account_dir") or row.wechat_account_dir or "")
                row.sync_batch_id = str(item.get("sync_batch_id") or row.sync_batch_id or "")
                row.last_synced_at = synced_at
                row.local_type = self._optional_int(item.get("local_type"), row.local_type)
                row.contact_flag = self._optional_int(item.get("contact_flag"), row.contact_flag)
                row.delete_flag = self._optional_int(item.get("delete_flag"), row.delete_flag)
                row.verify_flag = self._optional_int(item.get("verify_flag"), row.verify_flag)
                row.is_chatroom_member = 1 if bool(item.get("is_chatroom_member")) else 0
                row.tags_json = json.dumps(tags, ensure_ascii=False)
                eligibility = self.classify_contact_eligibility(
                    wxid=wxid,
                    nickname=nickname,
                    tags=tags,
                    local_type=row.local_type,
                    contact_flag=row.contact_flag,
                    delete_flag=row.delete_flag,
                )
                row.eligible_for_touch = 1 if eligibility["eligible"] else 0
                row.eligibility_reason = str(eligibility["reason"])
                row.excluded_reason = "" if eligibility["eligible"] else str(eligibility["reason"])
                row.confirmed_for_touch = 1 if auto_confirm and eligibility["eligible"] else 0
                saved_rows.append(row)
            session.commit()
            return [self._contact(row) for row in saved_rows]

    def list_contacts(
        self,
        limit: int = 100,
        *,
        eligible_for_touch: bool | None = None,
        confirmed_for_touch: bool | None = None,
        source: str | None = None,
    ) -> list[Contact]:
        with self.SessionLocal() as session:
            query = select(ContactRow).order_by(ContactRow.created_at.asc()).limit(limit)
            if eligible_for_touch is not None:
                query = query.where(ContactRow.eligible_for_touch == (1 if eligible_for_touch else 0))
            if confirmed_for_touch is not None:
                query = query.where(ContactRow.confirmed_for_touch == (1 if confirmed_for_touch else 0))
            if source is not None:
                query = query.where(ContactRow.source == source)
            rows = session.scalars(query).all()
            return [self._contact(row) for row in rows]

    def set_contact_touch_confirmation(self, contact_id: str, *, confirmed: bool) -> Contact:
        with self.SessionLocal() as session:
            row = session.get(ContactRow, contact_id)
            if row is None:
                raise KeyError(contact_id)
            if confirmed and not row.eligible_for_touch:
                row.confirmed_for_touch = 0
                row.eligibility_reason = row.eligibility_reason or "not_eligible"
            else:
                row.confirmed_for_touch = 1 if confirmed else 0
            session.commit()
            return self._contact(row)

    def exclude_contact_from_touch(self, contact_id: str, *, reason: str = "manually_excluded") -> Contact:
        with self.SessionLocal() as session:
            row = session.get(ContactRow, contact_id)
            if row is None:
                raise KeyError(contact_id)
            row.eligible_for_touch = 0
            row.eligibility_reason = reason
            row.excluded_reason = reason
            row.confirmed_for_touch = 0
            session.commit()
            return self._contact(row)

    def upsert_plan(self, *, plan_type: str, name: str, status: str = "draft", payload: dict | None = None) -> AutomationPlan:
        with self.SessionLocal() as session:
            row = session.scalar(select(AutomationPlanRow).where(AutomationPlanRow.plan_type == plan_type, AutomationPlanRow.name == name))
            if row is None:
                row = AutomationPlanRow(id=str(uuid4()), plan_type=plan_type, name=name)
                session.add(row)
            row.status = status
            row.payload_json = json.dumps(payload or json.loads(row.payload_json or "{}"), ensure_ascii=False)
            session.commit()
            return self._plan(row)

    def list_plans(self, plan_type: str | None = None) -> list[AutomationPlan]:
        with self.SessionLocal() as session:
            query = select(AutomationPlanRow)
            if plan_type:
                query = query.where(AutomationPlanRow.plan_type == plan_type)
            return [self._plan(row) for row in session.scalars(query).all()]

    def save_ai_profile(self, *, name: str, imported: ImportedPrompt) -> dict:
        with self.SessionLocal() as session:
            row = AIProfileRow(
                id=str(uuid4()),
                name=name,
                source_path=imported.source_path,
                system_prompt=imported.system_prompt,
                sales_flow=imported.sales_flow,
                constraints=imported.constraints,
                handoff_rules=imported.handoff_rules.raw_text,
                knowledge_json=json.dumps(
                    [{"question": item.question, "answer": item.answer} for item in imported.knowledge_base],
                    ensure_ascii=False,
                ),
            )
            session.add(row)
            session.commit()
            return self._profile(row)

    def latest_ai_profile(self) -> dict | None:
        with self.SessionLocal() as session:
            row = session.scalar(select(AIProfileRow).order_by(AIProfileRow.created_at.desc()).limit(1))
            return self._profile(row) if row else None

    def create_task(self, *, action_type: str, target_id: str = "", status: TaskStatus = TaskStatus.pending) -> TaskRun:
        with self.SessionLocal() as session:
            row = TaskRunRow(id=str(uuid4()), action_type=action_type, target_id=target_id, status=status.value)
            session.add(row)
            session.commit()
            return self._task(row)

    def update_task(self, task_id: str, *, status: TaskStatus, step: str, progress: int, error: str | None = None) -> TaskRun:
        with self.SessionLocal() as session:
            row = session.get(TaskRunRow, task_id)
            if row is None:
                raise KeyError(task_id)
            row.status = status.value
            row.step = step
            row.progress = progress
            row.error = error
            if status in {TaskStatus.succeeded, TaskStatus.failed, TaskStatus.blocked, TaskStatus.stopped}:
                row.finished_at = datetime.now(UTC)
            session.commit()
            return self._task(row)

    def list_tasks(self, limit: int = 100) -> list[TaskRun]:
        with self.SessionLocal() as session:
            rows = session.scalars(select(TaskRunRow).order_by(TaskRunRow.started_at.desc()).limit(limit)).all()
            return [self._task(row) for row in rows]

    def add_task_event(self, *, task_id: str, status: TaskStatus, message: str, evidence_path: str | None = None) -> TaskEvent:
        with self.SessionLocal() as session:
            row = TaskEventRow(id=str(uuid4()), task_id=task_id, status=status.value, message=message, evidence_path=evidence_path)
            session.add(row)
            session.commit()
            return self._event(row)

    def list_task_events(self, task_id: str | None = None, limit: int = 100) -> list[TaskEvent]:
        with self.SessionLocal() as session:
            query = select(TaskEventRow).order_by(TaskEventRow.created_at.desc()).limit(limit)
            if task_id:
                query = select(TaskEventRow).where(TaskEventRow.task_id == task_id).order_by(TaskEventRow.created_at.asc()).limit(limit)
            return [self._event(row) for row in session.scalars(query).all()]

    def add_audit_log(self, *, action: str, target: str, payload: dict, result: str, evidence_path: str | None = None) -> None:
        with self.SessionLocal() as session:
            session.add(
                AuditLogRow(
                    id=str(uuid4()),
                    action=action,
                    target=target,
                    payload_hash=self._hash(payload),
                    result=result,
                    evidence_path=evidence_path,
                )
            )
            session.commit()

    def list_audit_logs(self, limit: int = 100) -> list[dict]:
        with self.SessionLocal() as session:
            rows = session.scalars(select(AuditLogRow).order_by(AuditLogRow.created_at.desc()).limit(limit)).all()
            return [
                {
                    "id": row.id,
                    "actor": row.actor,
                    "action": row.action,
                    "target": row.target,
                    "payload_hash": row.payload_hash,
                    "result": row.result,
                    "evidence_path": row.evidence_path,
                    "created_at": row.created_at,
                }
                for row in rows
            ]

    def add_evidence_file(self, *, path: str, task_id: str | None = None, target_id: str = "", kind: str = "screenshot") -> None:
        with self.SessionLocal() as session:
            session.add(EvidenceFileRow(id=str(uuid4()), task_id=task_id, target_id=target_id, kind=kind, path=path))
            session.commit()

    def list_evidence_files(self, limit: int = 100) -> list[dict]:
        with self.SessionLocal() as session:
            rows = session.scalars(select(EvidenceFileRow).order_by(EvidenceFileRow.created_at.desc()).limit(limit)).all()
            return [
                {
                    "id": row.id,
                    "task_id": row.task_id,
                    "target_id": row.target_id,
                    "kind": row.kind,
                    "path": row.path,
                    "created_at": row.created_at,
                }
                for row in rows
            ]

    def mark_contact_touched(self, *, plan_id: str, contact_id: str, touched_at: datetime) -> None:
        with self.SessionLocal() as session:
            row = session.scalar(select(PlanTargetRow).where(PlanTargetRow.plan_id == plan_id, PlanTargetRow.contact_id == contact_id))
            if row is None:
                row = PlanTargetRow(id=str(uuid4()), plan_id=plan_id, contact_id=contact_id)
                session.add(row)
            row.status = "touched"
            row.last_touched_at = touched_at
            session.commit()

    def cleanup_corrupt_plan_names(self) -> None:
        with self.SessionLocal() as session:
            rows = session.scalars(select(AutomationPlanRow).where(AutomationPlanRow.name == "?" * 5)).all()
            for row in rows:
                row.name = "小批量触达"
            if rows:
                session.commit()

    def refresh_contact_eligibility(self) -> None:
        with self.SessionLocal() as session:
            rows = session.scalars(select(ContactRow)).all()
            for row in rows:
                if row.eligibility_reason == "manually_excluded":
                    row.eligible_for_touch = 0
                    row.confirmed_for_touch = 0
                    row.excluded_reason = "manually_excluded"
                    continue
                tags = json.loads(row.tags_json or "[]")
                eligibility = self.classify_contact_eligibility(
                    wxid=row.wxid,
                    nickname=row.nickname,
                    tags=tags,
                    local_type=row.local_type,
                    contact_flag=row.contact_flag,
                    delete_flag=row.delete_flag,
                )
                row.eligible_for_touch = 1 if eligibility["eligible"] else 0
                row.eligibility_reason = str(eligibility["reason"])
                row.excluded_reason = "" if eligibility["eligible"] else str(eligibility["reason"])
                if not eligibility["eligible"]:
                    row.confirmed_for_touch = 0
            if rows:
                session.commit()

    def get_plan_target(self, *, plan_id: str, contact_id: str) -> dict | None:
        with self.SessionLocal() as session:
            row = session.scalar(select(PlanTargetRow).where(PlanTargetRow.plan_id == plan_id, PlanTargetRow.contact_id == contact_id))
            if row is None:
                return None
            return {
                "id": row.id,
                "plan_id": row.plan_id,
                "contact_id": row.contact_id,
                "status": row.status,
                "last_touched_at": row.last_touched_at,
                "next_touch_at": row.next_touch_at,
                "skip_reason": row.skip_reason,
            }

    @staticmethod
    def _contact(row: ContactRow) -> Contact:
        return Contact(
            id=row.id,
            account_id=row.account_id,
            wxid=row.wxid,
            nickname=row.nickname,
            remark=row.remark,
            alias=row.alias,
            raw_wxid=row.raw_wxid,
            wechat_account_dir=row.wechat_account_dir,
            sync_batch_id=row.sync_batch_id,
            last_synced_at=row.last_synced_at,
            local_type=row.local_type,
            contact_flag=row.contact_flag,
            delete_flag=row.delete_flag,
            verify_flag=row.verify_flag,
            is_chatroom_member=bool(row.is_chatroom_member),
            excluded_reason=row.excluded_reason,
            tags=json.loads(row.tags_json or "[]"),
            source=row.source,
            eligible_for_touch=bool(row.eligible_for_touch),
            eligibility_reason=row.eligibility_reason or "eligible",
            confirmed_for_touch=bool(row.confirmed_for_touch),
        )

    @staticmethod
    def _plan(row: AutomationPlanRow) -> AutomationPlan:
        return AutomationPlan(
            id=row.id,
            plan_type=row.plan_type,
            name=row.name,
            status=row.status,
            schedule=json.loads(row.schedule_json or "{}"),
            quota=json.loads(row.quota_json or "{}"),
            whitelist=json.loads(row.whitelist_json or "[]"),
            payload=json.loads(row.payload_json or "{}"),
        )

    @staticmethod
    def _task(row: TaskRunRow) -> TaskRun:
        return TaskRun(
            id=row.id,
            action_type=row.action_type,
            target_id=row.target_id,
            status=TaskStatus(row.status),
            step=row.step,
            progress=row.progress,
            error=row.error,
            started_at=row.started_at,
            finished_at=row.finished_at,
        )

    @staticmethod
    def _event(row: TaskEventRow) -> TaskEvent:
        return TaskEvent(
            id=row.id,
            task_id=row.task_id,
            status=TaskStatus(row.status),
            message=row.message,
            evidence_path=row.evidence_path,
            created_at=row.created_at,
        )

    @staticmethod
    def _profile(row: AIProfileRow) -> dict:
        return {
            "id": row.id,
            "name": row.name,
            "source_path": row.source_path,
            "system_prompt": row.system_prompt,
            "sales_flow": row.sales_flow,
            "constraints": row.constraints,
            "handoff_rules": row.handoff_rules,
            "knowledge_base": json.loads(row.knowledge_json or "[]"),
            "created_at": row.created_at,
        }

    @staticmethod
    def _hash(payload: dict) -> str:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _ensure_contact_columns(self) -> None:
        inspector = inspect(self.engine)
        if "contacts" not in inspector.get_table_names():
            return
        existing = {column["name"] for column in inspector.get_columns("contacts")}
        statements = []
        if "eligible_for_touch" not in existing:
            statements.append("ALTER TABLE contacts ADD COLUMN eligible_for_touch INTEGER DEFAULT 1")
        if "eligibility_reason" not in existing:
            statements.append("ALTER TABLE contacts ADD COLUMN eligibility_reason VARCHAR DEFAULT 'eligible'")
        if "confirmed_for_touch" not in existing:
            statements.append("ALTER TABLE contacts ADD COLUMN confirmed_for_touch INTEGER DEFAULT 0")
        if "alias" not in existing:
            statements.append("ALTER TABLE contacts ADD COLUMN alias VARCHAR DEFAULT ''")
        if "raw_wxid" not in existing:
            statements.append("ALTER TABLE contacts ADD COLUMN raw_wxid VARCHAR DEFAULT ''")
        if "wechat_account_dir" not in existing:
            statements.append("ALTER TABLE contacts ADD COLUMN wechat_account_dir VARCHAR DEFAULT ''")
        if "sync_batch_id" not in existing:
            statements.append("ALTER TABLE contacts ADD COLUMN sync_batch_id VARCHAR DEFAULT ''")
        if "last_synced_at" not in existing:
            statements.append("ALTER TABLE contacts ADD COLUMN last_synced_at DATETIME")
        if "local_type" not in existing:
            statements.append("ALTER TABLE contacts ADD COLUMN local_type INTEGER")
        if "contact_flag" not in existing:
            statements.append("ALTER TABLE contacts ADD COLUMN contact_flag INTEGER")
        if "delete_flag" not in existing:
            statements.append("ALTER TABLE contacts ADD COLUMN delete_flag INTEGER")
        if "verify_flag" not in existing:
            statements.append("ALTER TABLE contacts ADD COLUMN verify_flag INTEGER")
        if "is_chatroom_member" not in existing:
            statements.append("ALTER TABLE contacts ADD COLUMN is_chatroom_member INTEGER DEFAULT 0")
        if "excluded_reason" not in existing:
            statements.append("ALTER TABLE contacts ADD COLUMN excluded_reason VARCHAR DEFAULT ''")
        if not statements:
            return
        with self.engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))

    @staticmethod
    def classify_contact_eligibility(
        *,
        wxid: str,
        nickname: str = "",
        tags: list[str] | None = None,
        local_type: int | None = None,
        contact_flag: int | None = None,
        delete_flag: int | None = None,
    ) -> dict[str, object]:
        value = f"{wxid} {nickname}".strip()
        ui_artifacts = {"聊天记录", "从手机导入聊天记录", "语音通话", "聊天信息"}
        system_ids = {"filehelper", "weixin", "fmessage", "medianote", "floatbottle", "notifymessage"}
        blocked_exact = {"文件传输助手", "微信团队", "腾讯新闻", *ui_artifacts}
        blocked_contains = ["公众号", "服务通知", "订阅号", "群聊", "搜一搜", "功能", "搜索网络结果"]
        if wxid in ui_artifacts or nickname in ui_artifacts:
            return {"eligible": False, "reason": "non_contact_ui_artifact"}
        if wxid in system_ids:
            return {"eligible": False, "reason": "system_contact"}
        if wxid.endswith("@chatroom"):
            return {"eligible": False, "reason": "group_chat"}
        if wxid.startswith("gh_"):
            return {"eligible": False, "reason": "official_account"}
        if delete_flag not in {None, 0}:
            return {"eligible": False, "reason": "deleted_contact"}
        if contact_flag == 4:
            return {"eligible": False, "reason": "group_member_cache"}
        if local_type is not None and local_type not in {1, 5}:
            return {"eligible": False, "reason": "non_friend_contact"}
        if contact_flag is not None and contact_flag not in {1, 3}:
            return {"eligible": False, "reason": "non_friend_contact"}
        if value in blocked_exact or wxid in blocked_exact or nickname in blocked_exact:
            return {"eligible": False, "reason": "system_contact"}
        if any(marker in value for marker in blocked_contains):
            return {"eligible": False, "reason": "non_customer_contact"}
        if tags and any(tag in {"excluded", "system", "公众号", "non_contact_ui_artifact", "group_member_cache"} for tag in tags):
            return {"eligible": False, "reason": "tag_excluded"}
        return {"eligible": True, "reason": "eligible"}

    @staticmethod
    def _optional_int(value: object, default: int | None = None) -> int | None:
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
