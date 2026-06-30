from datetime import UTC, datetime, timedelta

from app.models.schemas import TaskStatus
from app.services.store import AgentStore
from app.services.touch import TouchPlanner


def test_store_creates_required_tables_and_records_task_event(tmp_path):
    store = AgentStore(f"sqlite:///{tmp_path / 'agent.db'}")
    store.create_schema()

    tables = set(store.table_names())

    assert {
        "wechat_accounts",
        "contacts",
        "conversations",
        "messages",
        "automation_plans",
        "plan_targets",
        "task_runs",
        "task_events",
        "audit_logs",
        "ai_profiles",
        "moment_posts",
        "moment_interactions",
        "evidence_files",
    }.issubset(tables)

    task = store.create_task(action_type="message.send", target_id="wxid_1")
    event = store.add_task_event(task_id=task.id, status=TaskStatus.running, message="preflight")

    assert event.task_id == task.id
    assert store.list_task_events(task.id)[0].message == "preflight"


def test_touch_planner_skips_contact_touched_within_interval(tmp_path):
    store = AgentStore(f"sqlite:///{tmp_path / 'agent.db'}")
    store.create_schema()
    plan = store.upsert_plan(plan_type="touch", name="小批量触达")
    contact = store.upsert_contact(account_id="wxid_test_001", wxid="wxid_contact_001", nickname="测试客户")
    now = datetime(2026, 6, 29, 12, 0, tzinfo=UTC)
    store.mark_contact_touched(plan_id=plan.id, contact_id=contact.id, touched_at=now - timedelta(days=2))

    decision = TouchPlanner(store, touch_interval_days=15).evaluate(plan_id=plan.id, contact_id=contact.id, now=now)

    assert decision.allowed is False
    assert decision.reason == "touch_interval_active"
    assert decision.next_touch_at == now - timedelta(days=2) + timedelta(days=15)


def test_touch_planner_allows_contact_outside_interval(tmp_path):
    store = AgentStore(f"sqlite:///{tmp_path / 'agent.db'}")
    store.create_schema()
    plan = store.upsert_plan(plan_type="touch", name="小批量触达")
    contact = store.upsert_contact(account_id="wxid_test_001", wxid="wxid_contact_002", nickname="测试客户2")
    now = datetime(2026, 6, 29, 12, 0, tzinfo=UTC)
    store.mark_contact_touched(plan_id=plan.id, contact_id=contact.id, touched_at=now - timedelta(days=20))

    decision = TouchPlanner(store, touch_interval_days=15).evaluate(plan_id=plan.id, contact_id=contact.id, now=now)

    assert decision.allowed is True
    assert decision.reason == "allowed"
