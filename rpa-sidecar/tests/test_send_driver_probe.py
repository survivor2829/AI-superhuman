from app.services.automation import WeixinAutomationDriver
from app.services.guardrails import LocalAction


class FakeRealDriver:
    def __init__(self) -> None:
        self.send_attempts = 0

    def send_driver_probe(self) -> dict[str, object]:
        return {
            "mode": "non_screen",
            "verified": False,
            "message": "非屏幕发送通道未验证，未执行发送",
            "capabilities": ["contact_sync", "touch_preview", "audit_log"],
        }

    def send_message(self, **kwargs):
        self.send_attempts += 1
        raise AssertionError("real UI send must not be called before non-screen driver verification")


def test_message_send_blocks_before_non_screen_driver_is_verified():
    real_driver = FakeRealDriver()
    driver = WeixinAutomationDriver(real_driver, dry_run=False)

    result = driver.execute(
        LocalAction(
            action_type="message.send",
            target_id="A测试客户",
            payload={"content": "这是测试说明：您好", "search_terms": ["A测试客户"]},
        )
    )

    assert result.success is False
    assert result.verification_status == "blocked"
    assert result.message == "非屏幕发送通道未验证，未执行发送"
    assert result.failure_reason == "非屏幕发送通道未验证，未执行发送"
    assert real_driver.send_attempts == 0


def test_send_driver_probe_exposes_current_non_screen_status():
    driver = WeixinAutomationDriver(FakeRealDriver(), dry_run=False)

    result = driver.send_driver_probe()

    assert result["mode"] == "non_screen"
    assert result["verified"] is False
    assert result["message"] == "非屏幕发送通道未验证，未执行发送"
