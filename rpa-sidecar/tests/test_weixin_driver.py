from pathlib import Path

from app.services.weixin_driver import (
    EvidenceRecorder,
    RealAutomationDriver,
    SearchResultInspector,
    WindowProbeDriver,
)


def test_window_probe_driver_detects_weixin_process_from_provider():
    driver = WindowProbeDriver(
        process_name="Weixin",
        window_title="微信",
        process_provider=lambda: [
            {"name": "Weixin", "pid": 34888, "path": r"F:\微信\Weixin\Weixin.exe", "title": "微信"}
        ],
    )

    status = driver.probe()

    assert status.detected is True
    assert status.process_name == "Weixin"
    assert status.window_title == "微信"
    assert status.pid == 34888


def test_window_probe_reports_hidden_main_window_when_process_exists_without_title():
    driver = WindowProbeDriver(
        process_name="Weixin",
        window_title="微信",
        process_provider=lambda: [
            {"name": "Weixin", "pid": 34888, "path": r"F:\微信\Weixin\Weixin.exe", "title": ""}
        ],
    )

    status = driver.probe()

    assert status.detected is False
    assert status.pid == 34888
    assert status.reason == "wechat_process_found_but_main_window_hidden"


def test_window_probe_detects_wechat_qt_main_window_even_when_win32_visibility_is_false():
    driver = WindowProbeDriver(
        process_name="Weixin",
        window_title="微信",
        process_provider=lambda: [
            {
                "name": "Weixin",
                "pid": 34888,
                "path": r"F:\微信\Weixin\Weixin.exe",
                "title": "WxTrayIconMessageWindow",
                "class_name": "Qt51514WxTrayIconMessageWindowClass",
                "hwnd": 100,
                "visible": False,
                "rect": (76, 76, 1356, 741),
            },
            {
                "name": "Weixin",
                "pid": 34888,
                "path": r"F:\微信\Weixin\Weixin.exe",
                "title": "微信",
                "class_name": "Qt51514QWindowIcon",
                "hwnd": 200,
                "visible": False,
                "rect": (14, 23, 1356, 994),
            },
        ],
    )

    status = driver.probe()

    assert status.detected is True
    assert status.hwnd == 200
    assert status.class_name == "Qt51514QWindowIcon"
    assert status.rect == (14, 23, 1356, 994)


def test_evidence_recorder_writes_placeholder_when_capture_unavailable(tmp_path):
    recorder = EvidenceRecorder(tmp_path, screenshot_provider=lambda path: False)

    evidence = recorder.capture("before_send", target_id="wxid_contact_001")

    assert Path(evidence.path).exists()
    assert evidence.kind == "placeholder"
    assert evidence.target_id == "wxid_contact_001"


def test_real_driver_blocks_send_when_weixin_window_missing(tmp_path):
    probe = WindowProbeDriver(
        process_name="Weixin",
        window_title="微信",
        process_provider=lambda: [],
    )
    driver = RealAutomationDriver(probe_driver=probe, evidence_recorder=EvidenceRecorder(tmp_path, screenshot_provider=lambda path: False))

    result = driver.send_message(target_id="wxid_contact_001", content="这是测试说明：您好")

    assert result.success is False
    assert result.message == "wechat_window_not_found"
    assert result.evidence["before_probe"]


def test_real_driver_blocks_send_when_wechat_window_cannot_be_activated(tmp_path):
    probe = WindowProbeDriver(
        process_name="Weixin",
        window_title="微信",
        process_provider=lambda: [
            {
                "name": "Weixin",
                "pid": 34888,
                "path": r"F:\微信\Weixin\Weixin.exe",
                "title": "微信",
                "class_name": "Qt51514QWindowIcon",
                "hwnd": 200,
                "visible": False,
                "rect": (14, 23, 1356, 994),
            }
        ],
    )
    driver = RealAutomationDriver(
        probe_driver=probe,
        evidence_recorder=EvidenceRecorder(tmp_path, screenshot_provider=lambda path: False),
        window_activator=lambda status: (False, "foreground_not_changed"),
    )

    result = driver.send_message(target_id="wxid_contact_001", content="这是测试说明：您好")

    assert result.success is False
    assert result.verification_status == "blocked"
    assert result.message == "blocked_window_not_foreground"
    assert result.failure_reason == "foreground_not_changed"
    assert result.evidence["activation_failed"]


def test_search_result_inspector_blocks_wrong_search_surface():
    inspector = SearchResultInspector(
        [
            "搜索网络结果",
            "文件传输助手",
            "文件传输助手已读功能",
            "文件传输助手打开",
            "功能",
        ]
    )

    decision = inspector.resolve(target_id="文件传输助手", aliases=["文件传输助手"])

    assert decision.allowed is False
    assert decision.reason == "blocked_wrong_search_surface"


def test_search_result_inspector_blocks_ambiguous_exact_matches():
    inspector = SearchResultInspector(["聊天", "A测试客户", "联系人", "A测试客户"])

    decision = inspector.resolve(target_id="A测试客户", aliases=["A测试客户"])

    assert decision.allowed is False
    assert decision.reason == "blocked_ambiguous_target"


def test_search_result_inspector_accepts_single_chat_or_contact_match():
    inspector = SearchResultInspector(["聊天", "A测试客户", "最近消息"])

    decision = inspector.resolve(target_id="A测试客户", aliases=["A测试客户"])

    assert decision.allowed is True
    assert decision.matched_target == "A测试客户"
