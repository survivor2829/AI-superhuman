from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.services.store import AgentStore


@dataclass(frozen=True)
class TouchDecision:
    allowed: bool
    reason: str
    next_touch_at: datetime | None = None


class TouchPlanner:
    def __init__(self, store: AgentStore, *, touch_interval_days: int) -> None:
        self.store = store
        self.touch_interval_days = touch_interval_days

    def evaluate(self, *, plan_id: str, contact_id: str, now: datetime | None = None) -> TouchDecision:
        current = now or datetime.now(UTC)
        target = self.store.get_plan_target(plan_id=plan_id, contact_id=contact_id)
        if target is None or target["last_touched_at"] is None:
            return TouchDecision(allowed=True, reason="allowed")
        last_touched_at = target["last_touched_at"]
        if last_touched_at.tzinfo is None:
            last_touched_at = last_touched_at.replace(tzinfo=UTC)
        next_touch_at = last_touched_at + timedelta(days=self.touch_interval_days)
        if current < next_touch_at:
            return TouchDecision(allowed=False, reason="touch_interval_active", next_touch_at=next_touch_at)
        return TouchDecision(allowed=True, reason="allowed")
