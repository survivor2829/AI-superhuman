from app.services.automation import WeixinAutomationDriver
from app.services.guardrails import LocalAction
from app.services.weixin_driver import EvidenceRecorder, RealAutomationDriver, WindowProbeDriver


class FakeRealDriver:
    def __init__(self) -> None:
        self.send_attempts = 0
        self.calibrate_attempts = 0
        self.controlled_screen_state = type(
            "State",
            (),
            {
                "calibrated": False,
                "calibrated_at": None,
                "anchors": {},
                "live_gate_verified": False,
                "last_verified_at": None,
                "last_receipt": None,
            },
        )()

    def send_driver_probe(self) -> dict[str, object]:
        return {
            "mode": "controlled_screen",
            "verified": False,
            "calibrated": False,
            "message": "请先校准微信窗口，未执行发送",
            "capabilities": ["contact_sync", "touch_preview", "window_normalize", "controlled_screen_send", "audit_log"],
            "blocked_reason": "window_calibration_required",
            "max_batch_size": 0,
            "candidates": [
                {
                    "id": "controlled_wechat_window_automation",
                    "label": "受控微信窗口自动化",
                    "status": "not_calibrated",
                    "can_send": False,
                    "evidence": "待校准",
                }
            ],
            "last_verified_at": None,
            "last_receipt": None,
        }

    def calibrate_send_driver(self) -> dict[str, object]:
        self.calibrate_attempts += 1
        return {"success": False, "calibrated": False, "message": "window_calibration_failed"}

    def send_message(self, **kwargs):
        self.send_attempts += 1
        raise AssertionError("real UI send must not be called when window calibration fails")


def test_message_send_blocks_when_auto_calibration_fails():
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
    assert result.message == "请先校准微信窗口，未执行发送"
    assert result.failure_reason == "请先校准微信窗口，未执行发送"
    assert real_driver.calibrate_attempts == 1
    assert real_driver.send_attempts == 0


def test_send_driver_probe_exposes_current_controlled_screen_status():
    driver = WeixinAutomationDriver(FakeRealDriver(), dry_run=False)

    result = driver.send_driver_probe()

    assert result["mode"] == "controlled_screen"
    assert result["verified"] is False
    assert result["message"] == "请先校准微信窗口，未执行发送"
    assert result["blocked_reason"] == "window_calibration_required"
    assert result["max_batch_size"] == 0
    assert result["last_verified_at"] is None
    assert result["last_receipt"] is None
    assert result["candidates"][0]["id"] == "controlled_wechat_window_automation"
    assert result["candidates"][0]["can_send"] is False


def test_real_driver_probe_lists_research_candidates(tmp_path):
    driver = RealAutomationDriver(
        probe_driver=WindowProbeDriver(process_provider=lambda: []),
        evidence_recorder=EvidenceRecorder(tmp_path),
    )

    result = driver.send_driver_probe()

    assert result["mode"] == "controlled_screen"
    assert result["verified"] is False
    assert result["blocked_reason"] == "window_calibration_required"
    assert result["max_batch_size"] == 0
    assert result["last_verified_at"] is None
    assert result["last_receipt"] is None
    candidate_ids = {candidate["id"] for candidate in result["candidates"]}
    assert candidate_ids == {
        "controlled_wechat_window_automation",
        "dt_ai_helper_execution_pattern",
    }
    assert all(candidate["can_send"] is False for candidate in result["candidates"])
    assert str(result["research_report_path"]).endswith("docs\\non-screen-send-research.md")
    assert result["research_artifacts"][0]["kind"] == "contract_scan"
    assert str(result["research_artifacts"][0]["path"]).endswith("docs\\research\\dt-ai-helper-contract-scan.json")
