from app.models.schemas import AutomationAction, TaskStatus
from app.services.task_engine import TaskEngine


def test_task_engine_records_audit_log_for_successful_dry_run_action():
    engine = TaskEngine()
    action = AutomationAction(
        action_type="message.send",
        account_id="wxid_test_001",
        target_id="wxid_contact_001",
        payload={"content": "hello"},
    )

    task = engine.run(action, dry_run=True)

    assert task.status == TaskStatus.succeeded
    assert task.progress == 100
    assert engine.audit_logs[-1].action == "message.send"
    assert engine.audit_logs[-1].result == "dry_run"
