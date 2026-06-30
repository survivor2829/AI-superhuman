from pathlib import Path

from app.services.weixin_driver import EvidenceRecorder, RealAutomationDriver, WindowProbeDriver


class FakeWindow:
    def set_focus(self) -> None:
        return None


def test_moments_feed_scan_captures_visible_window(tmp_path, monkeypatch):
    probe = WindowProbeDriver(
        process_provider=lambda: [
            {
                "name": "Weixin",
                "pid": 34888,
                "title": "wechat",
                "class_name": "Qt51514QWindowIcon",
                "hwnd": 200,
                "rect": (0, 0, 1280, 900),
                "foreground_match": True,
            }
        ]
    )
    driver = RealAutomationDriver(
        probe_driver=probe,
        evidence_recorder=EvidenceRecorder(tmp_path, screenshot_provider=lambda path: False),
        human_pause_seconds=(0, 0),
    )
    monkeypatch.setattr(driver, "_connect_window", lambda: FakeWindow())
    monkeypatch.setattr(driver, "_visible_texts", lambda window: ["Moments", "A Test Customer", "today feedback"])

    result = driver.scan_moments_feed(whitelist=["A Test Customer"])

    assert result["success"] is True
    assert result["message"] == "moments_feed_scanned"
    assert result["items"][0]["owner"] == "A Test Customer"
    assert Path(result["evidence"]["feed"]).exists()


def test_moments_feed_scan_blocks_when_wechat_window_missing(tmp_path):
    probe = WindowProbeDriver(process_name="Weixin", window_title="wechat", process_provider=lambda: [])
    driver = RealAutomationDriver(
        probe_driver=probe,
        evidence_recorder=EvidenceRecorder(tmp_path, screenshot_provider=lambda path: False),
        human_pause_seconds=(0, 0),
    )

    result = driver.scan_moments_feed(whitelist=["A Test Customer"])

    assert result["success"] is False
    assert result["message"] == "wechat_window_not_found"
    assert Path(result["evidence"]["feed"]).exists()
