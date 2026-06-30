from datetime import datetime

import pytest

from app.core.guardrails import GuardrailDecision, GuardrailPolicy, GuardrailViolation
from app.models.schemas import AutomationAction


def test_policy_allows_whitelisted_contact_inside_quota_and_window():
    policy = GuardrailPolicy(
        account_whitelist={"wxid_test_001"},
        contact_whitelist={"wxid_contact_001"},
        max_messages_per_hour=2,
        max_moment_actions_per_day=2,
        time_window="09:00-21:00",
    )
    action = AutomationAction(
        action_type="message.send",
        account_id="wxid_test_001",
        target_id="wxid_contact_001",
        payload={"content": "hello"},
    )

    decision = policy.evaluate(action, now=datetime(2026, 6, 29, 10, 0, 0))

    assert decision == GuardrailDecision(allowed=True, reason="allowed")


def test_policy_blocks_non_whitelisted_contact():
    policy = GuardrailPolicy(
        account_whitelist={"wxid_test_001"},
        contact_whitelist={"wxid_contact_001"},
        max_messages_per_hour=2,
        max_moment_actions_per_day=2,
        time_window="09:00-21:00",
    )
    action = AutomationAction(
        action_type="message.send",
        account_id="wxid_test_001",
        target_id="wxid_unknown",
        payload={"content": "hello"},
    )

    with pytest.raises(GuardrailViolation, match="target_not_whitelisted"):
        policy.ensure_allowed(action, now=datetime(2026, 6, 29, 10, 0, 0))


def test_policy_blocks_outside_time_window():
    policy = GuardrailPolicy(
        account_whitelist={"wxid_test_001"},
        contact_whitelist={"wxid_contact_001"},
        max_messages_per_hour=2,
        max_moment_actions_per_day=2,
        time_window="09:00-21:00",
    )
    action = AutomationAction(
        action_type="moments.comment",
        account_id="wxid_test_001",
        target_id="wxid_contact_001",
        payload={"comment": "nice"},
    )

    decision = policy.evaluate(action, now=datetime(2026, 6, 29, 22, 0, 0))

    assert decision.allowed is False
    assert decision.reason == "outside_time_window"
