from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

from app.models.schemas import AutomationAction


class GuardrailViolation(RuntimeError):
    """Raised when an automation action violates local safety policy."""


@dataclass(frozen=True)
class GuardrailDecision:
    allowed: bool
    reason: str


class GuardrailPolicy:
    def __init__(
        self,
        *,
        account_whitelist: set[str],
        contact_whitelist: set[str],
        max_messages_per_hour: int,
        max_moment_actions_per_day: int,
        time_window: str,
    ) -> None:
        self.account_whitelist = account_whitelist
        self.contact_whitelist = contact_whitelist
        self.max_messages_per_hour = max_messages_per_hour
        self.max_moment_actions_per_day = max_moment_actions_per_day
        self.time_window = time_window

    def evaluate(self, action: AutomationAction, *, now: datetime | None = None) -> GuardrailDecision:
        current = now or datetime.now()
        if action.account_id not in self.account_whitelist:
            return GuardrailDecision(False, "account_not_whitelisted")
        if action.target_id not in self.contact_whitelist:
            return GuardrailDecision(False, "target_not_whitelisted")
        if not self._inside_window(current.time()):
            return GuardrailDecision(False, "outside_time_window")
        if self.max_messages_per_hour <= 0 and action.action_type.startswith("message."):
            return GuardrailDecision(False, "message_quota_exhausted")
        if self.max_moment_actions_per_day <= 0 and action.action_type.startswith("moments."):
            return GuardrailDecision(False, "moment_quota_exhausted")
        return GuardrailDecision(True, "allowed")

    def ensure_allowed(self, action: AutomationAction, *, now: datetime | None = None) -> GuardrailDecision:
        decision = self.evaluate(action, now=now)
        if not decision.allowed:
            raise GuardrailViolation(decision.reason)
        return decision

    def _inside_window(self, current: time) -> bool:
        start_raw, end_raw = self.time_window.split("-", 1)
        start = self._parse_time(start_raw)
        end = self._parse_time(end_raw)
        if start <= end:
            return start <= current <= end
        return current >= start or current <= end

    @staticmethod
    def _parse_time(value: str) -> time:
        hour_raw, minute_raw = value.strip().split(":", 1)
        return time(hour=int(hour_raw), minute=int(minute_raw))
