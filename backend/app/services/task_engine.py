from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from app.models.schemas import AuditLog, AutomationAction, TaskRun, TaskStatus


class TaskEngine:
    def __init__(self) -> None:
        self.task_runs: list[TaskRun] = []
        self.audit_logs: list[AuditLog] = []

    def run(self, action: AutomationAction, *, dry_run: bool = True) -> TaskRun:
        task = TaskRun(action_type=action.action_type, status=TaskStatus.running, step="dispatching", progress=10)
        result = "dry_run" if dry_run else "queued"
        task.status = TaskStatus.succeeded
        task.step = "completed"
        task.progress = 100
        task.finished_at = datetime.now(UTC)
        self.task_runs.append(task)
        self.audit_logs.append(
            AuditLog(
                action=action.action_type,
                target=action.target_id,
                payload_hash=self._payload_hash(action.payload),
                result=result,
            )
        )
        return task

    @staticmethod
    def _payload_hash(payload: dict) -> str:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
