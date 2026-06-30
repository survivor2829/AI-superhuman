from app.services.automation import WeixinAutomationDriver
from app.services.guardrails import LocalAction, LocalActionResult


def test_open_conversation_delegates_to_real_driver_without_sending():
    class FakeRealDriver:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def open_conversation(self, *, target_id: str, search_terms: list[str] | None = None) -> LocalActionResult:
            self.calls.append({"target_id": target_id, "search_terms": search_terms})
            return LocalActionResult(
                success=True,
                message="conversation_opened",
                dry_run=False,
                verification_status="verified",
                opened_conversation_title="A test customer",
                matched_target="A test customer",
                search_term_used="A test remark",
            )

    fake_real = FakeRealDriver()
    driver = WeixinAutomationDriver(fake_real, dry_run=False)  # type: ignore[arg-type]

    result = driver.open_conversation(
        LocalAction(
            action_type="message.open_conversation",
            target_id="wxid_contact",
            payload={"search_terms": ["A test remark", "A test customer"]},
        )
    )

    assert result.success is True
    assert result.message == "conversation_opened"
    assert fake_real.calls == [{"target_id": "wxid_contact", "search_terms": ["A test remark", "A test customer"]}]


def test_message_send_auto_calibrates_when_window_calibration_is_missing():
    class FakeRealDriver:
        def __init__(self) -> None:
            self.probe_calls = 0
            self.calibrate_calls = 0
            self.sent: list[dict[str, object]] = []

        def send_driver_probe(self) -> dict[str, object]:
            self.probe_calls += 1
            if self.calibrate_calls == 0:
                return {
                    "mode": "controlled_screen",
                    "max_batch_size": 0,
                    "blocked_reason": "window_calibration_required",
                    "message": "请先校准微信窗口，未执行发送",
                }
            return {
                "mode": "controlled_screen",
                "max_batch_size": 1,
                "blocked_reason": "live_gate_required",
                "message": "已校准微信窗口，可执行 1 人验证",
            }

        def calibrate_send_driver(self) -> dict[str, object]:
            self.calibrate_calls += 1
            return {"success": True, "calibrated": True, "message": "calibrated"}

        def send_message(self, *, target_id: str, content: str, search_terms: list[str] | None = None) -> LocalActionResult:
            self.sent.append({"target_id": target_id, "content": content, "search_terms": search_terms})
            return LocalActionResult(success=True, message="message_sent", verification_status="verified")

    fake_real = FakeRealDriver()
    driver = WeixinAutomationDriver(fake_real, dry_run=False)  # type: ignore[arg-type]

    result = driver.execute(
        LocalAction(
            action_type="message.send",
            target_id="wxid_contact",
            payload={"content": "hello", "search_terms": ["A test customer"]},
        )
    )

    assert result.success is True
    assert fake_real.calibrate_calls == 1
    assert fake_real.sent == [{"target_id": "wxid_contact", "content": "hello", "search_terms": ["A test customer"]}]
