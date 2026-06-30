from app.services.automation import WeixinAutomationDriver
from app.services.guardrails import LocalAction
from app.services.weixin_driver import EvidenceRecorder, RealAutomationDriver, WindowProbeDriver


class FakeRealDriver:
    def __init__(self) -> None:
        self.send_attempts = 0

    def send_driver_probe(self) -> dict[str, object]:
        return {
            "mode": "non_screen",
            "verified": False,
            "message": "非屏幕发送通道未验证，未执行发送",
            "capabilities": ["contact_sync", "touch_preview", "audit_log"],
            "blocked_reason": "non_screen_send_driver_not_verified",
            "candidates": [
                {
                    "id": "dt_ai_helper_local_service",
                    "label": "dt-ai-helper 本地服务合同",
                    "status": "research_only",
                    "can_send": False,
                    "evidence": "静态分析未验证可用非屏幕发送回执",
                }
            ],
            "last_verified_at": None,
            "last_receipt": None,
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
    assert result["blocked_reason"] == "non_screen_send_driver_not_verified"
    assert result["last_verified_at"] is None
    assert result["last_receipt"] is None
    assert result["candidates"][0]["id"] == "dt_ai_helper_local_service"
    assert result["candidates"][0]["can_send"] is False


def test_real_driver_probe_lists_research_candidates(tmp_path):
    driver = RealAutomationDriver(
        probe_driver=WindowProbeDriver(process_provider=lambda: []),
        evidence_recorder=EvidenceRecorder(tmp_path),
    )

    result = driver.send_driver_probe()

    assert result["mode"] == "non_screen"
    assert result["verified"] is False
    assert result["blocked_reason"] == "non_screen_send_driver_not_verified"
    assert result["last_verified_at"] is None
    assert result["last_receipt"] is None
    candidate_ids = {candidate["id"] for candidate in result["candidates"]}
    assert candidate_ids == {
        "dt_ai_helper_local_service",
        "wechat_local_data_ipc",
        "rpaagent_safety_boundary",
    }
    assert all(candidate["can_send"] is False for candidate in result["candidates"])
    assert str(result["research_report_path"]).endswith("docs\\non-screen-send-research.md")
