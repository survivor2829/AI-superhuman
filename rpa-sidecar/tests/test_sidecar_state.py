from app.services.automation import DryRunAutomationDriver
from app.services.guardrails import LocalAction


def test_dry_run_driver_reports_message_send_without_touching_wechat():
    driver = DryRunAutomationDriver(account_id="wxid_test_001")
    action = LocalAction(
        action_type="message.send",
        target_id="wxid_contact_001",
        payload={"content": "hello"},
    )

    result = driver.execute(action)

    assert result.success is True
    assert result.dry_run is True
    assert result.evidence["target_id"] == "wxid_contact_001"


def test_dry_run_driver_can_be_stopped():
    driver = DryRunAutomationDriver(account_id="wxid_test_001")

    result = driver.stop()

    assert result.success is True
    assert result.message == "stop signal accepted"
