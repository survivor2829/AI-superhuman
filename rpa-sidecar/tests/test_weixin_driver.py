from pathlib import Path

import pytest

from app.services.automation import WeixinAutomationDriver
from app.services.guardrails import LocalAction, LocalActionResult
from app.services.weixin_driver import (
    BlockedSend,
    EvidenceRecorder,
    RealAutomationDriver,
    SearchResultInspector,
    WindowProbeDriver,
)


def test_open_conversation_retries_next_search_term_after_title_mismatch(tmp_path, monkeypatch):
    import pywinauto.keyboard

    search_terms_used: list[str] = []
    valid_section = next(iter(SearchResultInspector.valid_sections))
    current_term = {"value": ""}
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
        window_activator=lambda status: (True, "activated"),
    )

    def fake_send_keys(keys, **kwargs):
        if keys not in {"^a{BACKSPACE}", "{ENTER}"}:
            current_term["value"] = keys
            search_terms_used.append(keys)

    monkeypatch.setattr(pywinauto.keyboard, "send_keys", fake_send_keys)
    monkeypatch.setattr(driver, "_connect_window", lambda: FakeWindow())
    monkeypatch.setattr(driver, "_find_chat_search_edit", lambda window: FakeControl())
    monkeypatch.setattr(driver, "_visible_texts", lambda window: [valid_section, current_term["value"]])
    monkeypatch.setattr(driver, "_find_exact_text_element", lambda window, target: FakeControl())
    monkeypatch.setattr(
        driver,
        "_current_conversation_title",
        lambda window, **kwargs: "wrong-chat" if current_term["value"] == "primary" else "secondary",
    )

    _, verification = driver._open_conversation_via_pywinauto(
        target_id="wxid_contact",
        evidence={},
        search_terms=["primary", "secondary"],
    )

    assert search_terms_used == ["primary", "secondary"]
    assert verification["opened_conversation_title"] == "secondary"
    assert verification["search_term_used"] == "secondary"


def test_open_conversation_clicks_result_row_when_text_click_does_not_open_chat(tmp_path, monkeypatch):
    import pywinauto.keyboard

    title_checks = {"count": 0}
    clicked_anchors: list[str] = []
    valid_section = next(iter(SearchResultInspector.valid_sections))
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
        window_activator=lambda status: (True, "activated"),
    )

    def fake_title(window, **kwargs):
        title_checks["count"] += 1
        return "" if title_checks["count"] <= 2 else "primary"

    monkeypatch.setattr(pywinauto.keyboard, "send_keys", lambda *args, **kwargs: None)
    monkeypatch.setattr(driver, "_connect_window", lambda: FakeWindow())
    monkeypatch.setattr(driver, "_find_chat_search_edit", lambda window: FakeControl())
    monkeypatch.setattr(driver, "_visible_texts", lambda window: [valid_section, "primary"])
    monkeypatch.setattr(driver, "_find_exact_text_element", lambda window, target: FakeControl())
    monkeypatch.setattr(driver, "_click_calibrated_anchor", lambda name: clicked_anchors.append(name) or True)
    monkeypatch.setattr(driver, "_current_conversation_title", fake_title)
    monkeypatch.setattr(driver, "_search_popup_visible", lambda: True)

    _, verification = driver._open_conversation_via_pywinauto(
        target_id="primary",
        evidence={},
        search_terms=["primary"],
    )

    assert clicked_anchors == ["first_result_area"]
    assert verification["opened_conversation_title"] == "primary"
    assert verification["matched_target"] == "first_result_area"


def test_search_result_inspector_blocks_add_friend_network_surface():
    inspector = SearchResultInspector(["网络查找微信号：wxid_test", "搜索网络结果", "wxid_test"])

    decision = inspector.resolve(target_id="wxid_test", aliases=["wxid_test"])

    assert decision.allowed is False
    assert decision.reason == "blocked_wrong_search_surface"


def test_open_conversation_does_not_click_first_result_for_raw_wxid_not_found(tmp_path, monkeypatch):
    import pywinauto.keyboard

    clicked_anchors: list[str] = []
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
        window_activator=lambda status: (True, "activated"),
    )

    monkeypatch.setattr(pywinauto.keyboard, "send_keys", lambda *args, **kwargs: None)
    monkeypatch.setattr(driver, "_connect_window", lambda: FakeWindow())
    monkeypatch.setattr(driver, "_find_chat_search_edit", lambda window: FakeControl())
    monkeypatch.setattr(driver, "_visible_texts", lambda window: [])
    monkeypatch.setattr(driver, "_click_calibrated_anchor", lambda name: clicked_anchors.append(name) or True)

    with pytest.raises(BlockedSend) as exc:
        driver._open_conversation_via_pywinauto(
            target_id="wxid_contact",
            evidence={},
            search_terms=["wxid_contact"],
        )

    assert exc.value.reason == "blocked_target_not_found"
    assert clicked_anchors == []


def test_open_conversation_accepts_enter_when_search_popup_closes(tmp_path, monkeypatch):
    import pywinauto.keyboard

    sent_keys: list[str] = []
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
        window_activator=lambda status: (True, "activated"),
    )

    monkeypatch.setattr(pywinauto.keyboard, "send_keys", lambda keys, **kwargs: sent_keys.append(keys))
    monkeypatch.setattr(driver, "_connect_window", lambda: FakeWindow())
    monkeypatch.setattr(driver, "_find_chat_search_edit", lambda window: FakeControl())
    monkeypatch.setattr(driver, "_visible_texts", lambda window: [])
    monkeypatch.setattr(driver, "_current_conversation_title", lambda window, **kwargs: "")
    monkeypatch.setattr(driver, "_search_popup_visible", lambda: False)

    _, verification = driver._open_conversation_via_pywinauto(
        target_id="primary",
        evidence={},
        search_terms=["primary"],
    )

    assert "{ENTER}" in sent_keys
    assert verification["opened_conversation_title"] == "primary"
    assert verification["matched_target"] == "keyboard_enter"


def test_send_uses_clipboard_paste_for_chinese_message(tmp_path, monkeypatch):
    import pyperclip
    import pywinauto.keyboard

    copied: list[str] = []
    sent_keys: list[str] = []
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
        window_activator=lambda status: (True, "activated"),
    )
    content = "这是测试说明：完整中文内容"

    monkeypatch.setattr(driver, "_open_conversation_via_pywinauto", lambda **kwargs: (FakeWindow(), {"opened_conversation_title": "primary", "matched_target": "keyboard_enter", "search_term_used": "primary"}))
    monkeypatch.setattr(driver, "_find_message_input", lambda window: FakeControl())
    monkeypatch.setattr(driver, "_message_visible", lambda window, text: True)
    monkeypatch.setattr(pyperclip, "copy", lambda text: copied.append(text))
    monkeypatch.setattr(pywinauto.keyboard, "send_keys", lambda keys, **kwargs: sent_keys.append(keys))

    driver._send_via_pywinauto(target_id="primary", content=content, evidence={}, search_terms=["primary"])

    assert copied == [content]
    assert "^v" in sent_keys
    assert content not in sent_keys


def test_visual_message_receipt_detects_new_green_bubble(tmp_path):
    from PIL import Image, ImageDraw

    before = Image.new("RGB", (1600, 1000), "white")
    after = Image.new("RGB", (1600, 1000), "white")
    draw = ImageDraw.Draw(after)
    draw.rounded_rectangle((760, 620, 1120, 710), radius=12, fill=(149, 236, 105))
    before_path = tmp_path / "before.png"
    after_path = tmp_path / "after.png"
    before.save(before_path)
    after.save(after_path)
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
    driver = RealAutomationDriver(probe_driver=probe, evidence_recorder=EvidenceRecorder(tmp_path, screenshot_provider=lambda path: False))

    assert driver._visual_message_sent(str(before_path), str(after_path)) is True


def test_visual_message_receipt_detects_new_bubble_even_when_chat_scrolls(tmp_path):
    from PIL import Image, ImageDraw

    before = Image.new("RGB", (1600, 1000), "white")
    after = Image.new("RGB", (1600, 1000), "white")
    before_draw = ImageDraw.Draw(before)
    after_draw = ImageDraw.Draw(after)
    before_draw.rounded_rectangle((540, 210, 1180, 390), radius=12, fill=(149, 236, 105))
    after_draw.rounded_rectangle((760, 620, 1120, 710), radius=12, fill=(149, 236, 105))
    before_path = tmp_path / "before_scroll.png"
    after_path = tmp_path / "after_scroll.png"
    before.save(before_path)
    after.save(after_path)
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
    driver = RealAutomationDriver(probe_driver=probe, evidence_recorder=EvidenceRecorder(tmp_path, screenshot_provider=lambda path: False))

    assert driver._visual_message_sent(str(before_path), str(after_path)) is True


class FakeWindow:
    def set_focus(self) -> None:
        return None


class FakeControl:
    def __init__(self) -> None:
        self.clicked = False

    def click_input(self) -> None:
        self.clicked = True


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


def test_window_probe_reports_minimized_window_metadata():
    driver = WindowProbeDriver(
        process_name="Weixin",
        window_title="寰俊",
        process_provider=lambda: [
            {
                "name": "Weixin",
                "pid": 34888,
                "path": r"F:\寰俊\Weixin\Weixin.exe",
                "title": "寰俊",
                "class_name": "Qt51514QWindowIcon",
                "hwnd": 200,
                "visible": True,
                "rect": (-32000, -32000, -31763, -31961),
                "is_minimized": True,
                "show_cmd": 2,
                "foreground_title": "Codex",
            }
        ],
    )

    status = driver.probe()

    assert status.detected is True
    assert status.is_minimized is True
    assert status.show_cmd == 2
    assert status.foreground_title == "Codex"


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


def test_real_driver_blocks_send_before_controlled_screen_calibration(tmp_path):
    probe = WindowProbeDriver(
        process_name="Weixin",
        window_title="微信",
        process_provider=lambda: [
            {
                "name": "Weixin",
                "pid": 34888,
                "title": "微信",
                "class_name": "Qt51514QWindowIcon",
                "hwnd": 200,
                "rect": (0, 0, 1280, 900),
            }
        ],
    )
    driver = RealAutomationDriver(probe_driver=probe, evidence_recorder=EvidenceRecorder(tmp_path, screenshot_provider=lambda path: False))

    result = driver.send_message(target_id="A测试客户", content="这是测试说明：您好")

    assert result.success is False
    assert result.verification_status == "blocked"
    assert result.failure_reason == "controlled_screen_calibration_required"


def test_calibrate_send_driver_records_window_anchors(tmp_path, monkeypatch):
    probe = WindowProbeDriver(
        process_name="Weixin",
        window_title="微信",
        process_provider=lambda: [
            {
                "name": "Weixin",
                "pid": 34888,
                "title": "微信",
                "class_name": "Qt51514QWindowIcon",
                "hwnd": 200,
                "rect": (0, 0, 1280, 900),
            }
        ],
    )
    driver = RealAutomationDriver(probe_driver=probe, evidence_recorder=EvidenceRecorder(tmp_path, screenshot_provider=lambda path: False))
    monkeypatch.setattr(driver, "_normalize_window", lambda status: (True, "window_normalized"))

    result = driver.calibrate_send_driver()

    assert result["success"] is True
    assert result["calibrated"] is True
    assert driver.send_driver_probe()["max_batch_size"] == 1
    assert result["anchors"]["search_box"]["x"] > 0


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
    driver.controlled_screen_state.calibrated = True
    driver.controlled_screen_state.anchors = {"search_box": {"x": 100, "y": 100}}

    result = driver.send_message(target_id="wxid_contact_001", content="这是测试说明：您好")

    assert result.success is False
    assert result.verification_status == "blocked"
    assert result.message == "blocked_window_not_foreground"
    assert result.failure_reason == "foreground_not_changed"
    assert result.evidence["activation_failed"]


def test_prepare_dedicated_desktop_blocks_when_window_cannot_be_activated(tmp_path, monkeypatch):
    probe = WindowProbeDriver(
        process_name="Weixin",
        window_title="寰俊",
        process_provider=lambda: [
            {
                "name": "Weixin",
                "pid": 34888,
                "path": r"F:\寰俊\Weixin\Weixin.exe",
                "title": "寰俊",
                "class_name": "Qt51514QWindowIcon",
                "hwnd": 200,
                "visible": True,
                "rect": (0, 0, 1280, 900),
            }
        ],
    )
    driver = RealAutomationDriver(
        probe_driver=probe,
        evidence_recorder=EvidenceRecorder(tmp_path, screenshot_provider=lambda path: False),
        window_activator=lambda status: (False, "foreground_not_changed"),
    )
    monkeypatch.setattr(driver, "normalize_window", lambda: {"success": True, "rect": (0, 0, 1280, 900)})

    result = driver.prepare_dedicated_desktop()

    assert result["success"] is False
    assert result["message"] == "wechat_window_not_foreground"
    assert result["activation_reason"] == "foreground_not_changed"
    assert result["evidence"]["activation_failed"]


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


def test_real_driver_blocks_when_search_input_missing_without_screen_fallback(tmp_path, monkeypatch):
    import pywinauto.keyboard

    probe = WindowProbeDriver(
        process_provider=lambda: [
            {
                "name": "Weixin",
                "pid": 34888,
                "title": "微信",
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
    monkeypatch.setattr(pywinauto.keyboard, "send_keys", lambda *args, **kwargs: None)
    monkeypatch.setattr(driver, "_connect_window", lambda: FakeWindow())
    monkeypatch.setattr(driver, "_find_chat_search_edit", lambda window: None)

    with pytest.raises(BlockedSend) as exc:
        driver._send_via_pywinauto(target_id="A测试客户", content="这是测试说明：您好", evidence={}, search_terms=["A测试客户"])
    assert exc.value.reason == "blocked_search_input_missing"


def test_send_state_machine_does_not_press_escape_before_search(tmp_path, monkeypatch):
    import pywinauto.keyboard

    sent_keys: list[str] = []
    probe = WindowProbeDriver(
        process_provider=lambda: [
            {
                "name": "Weixin",
                "pid": 34888,
                "title": "微信",
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
        window_activator=lambda status: (True, "activated"),
    )
    search_box = FakeControl()
    message_input = FakeControl()
    matched_contact = FakeControl()

    monkeypatch.setattr(pywinauto.keyboard, "send_keys", lambda keys, **kwargs: sent_keys.append(keys))
    monkeypatch.setattr(driver, "_connect_window", lambda: FakeWindow())
    monkeypatch.setattr(driver, "_find_chat_search_edit", lambda window: search_box)
    monkeypatch.setattr(driver, "_visible_texts", lambda window: ["聊天", "A测试客户"])
    monkeypatch.setattr(driver, "_find_exact_text_element", lambda window, target: matched_contact)
    monkeypatch.setattr(driver, "_current_conversation_title", lambda window, **kwargs: "A测试客户")
    monkeypatch.setattr(driver, "_find_message_input", lambda window: message_input)
    monkeypatch.setattr(driver, "_message_visible", lambda window, content: True)

    result = driver._send_via_pywinauto(target_id="wxid_contact", content="这是测试说明：您好", evidence={}, search_terms=["A测试客户", "若"])

    assert result["search_term_used"] == "A测试客户"
    assert "{ESC}" not in sent_keys


def test_open_conversation_uses_first_result_anchor_when_uia_text_is_missing(tmp_path, monkeypatch):
    import pywinauto.keyboard

    clicked_anchors: list[str] = []
    sent_keys: list[str] = []
    probe = WindowProbeDriver(
        process_provider=lambda: [
            {
                "name": "Weixin",
                "pid": 34888,
                "title": "微信",
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
        window_activator=lambda status: (True, "activated"),
    )

    monkeypatch.setattr(pywinauto.keyboard, "send_keys", lambda keys, **kwargs: sent_keys.append(keys))
    monkeypatch.setattr(driver, "_connect_window", lambda: FakeWindow())
    monkeypatch.setattr(driver, "_find_chat_search_edit", lambda window: FakeControl())
    monkeypatch.setattr(driver, "_visible_texts", lambda window: ["搜索", "常使用"])
    monkeypatch.setattr(driver, "_find_exact_text_element", lambda window, target: None)
    monkeypatch.setattr(driver, "_click_calibrated_anchor", lambda name: clicked_anchors.append(name) or True)
    monkeypatch.setattr(driver, "_current_conversation_title", lambda window, **kwargs: "A测试客户")

    _, verification = driver._open_conversation_via_pywinauto(target_id="wxid_contact", evidence={}, search_terms=["A测试客户"])

    assert clicked_anchors == []
    assert "{ENTER}" in sent_keys
    assert verification["opened_conversation_title"] == "A测试客户"
    assert verification["matched_target"] == "keyboard_enter"


def test_send_state_machine_blocks_when_wechat_lost_before_search(tmp_path, monkeypatch):
    import pywinauto.keyboard

    activations: list[str] = []
    probe = WindowProbeDriver(
        process_provider=lambda: [
            {
                "name": "Weixin",
                "pid": 34888,
                "title": "微信",
                "class_name": "Qt51514QWindowIcon",
                "hwnd": 200,
                "rect": (0, 0, 1280, 900),
                "foreground_match": False,
                "foreground_title": "桌面",
            }
        ]
    )
    driver = RealAutomationDriver(
        probe_driver=probe,
        evidence_recorder=EvidenceRecorder(tmp_path, screenshot_provider=lambda path: False),
        human_pause_seconds=(0, 0),
        window_activator=lambda status: (activations.append(status.window_title) or (False, "foreground_not_changed")),
    )
    monkeypatch.setattr(pywinauto.keyboard, "send_keys", lambda *args, **kwargs: None)
    monkeypatch.setattr(driver, "_connect_window", lambda: FakeWindow())
    monkeypatch.setattr(driver, "_find_chat_search_edit", lambda window: FakeControl())
    monkeypatch.setattr(driver, "_visible_texts", lambda window: ["聊天", "A测试客户"])
    monkeypatch.setattr(driver, "_find_exact_text_element", lambda window, target: FakeControl())
    monkeypatch.setattr(driver, "_current_conversation_title", lambda window, **kwargs: "A测试客户")
    monkeypatch.setattr(driver, "_find_message_input", lambda window: FakeControl())
    monkeypatch.setattr(driver, "_message_visible", lambda window, content: True)

    with pytest.raises(BlockedSend) as exc:
        driver._send_via_pywinauto(target_id="wxid_contact", content="这是测试说明：您好", evidence={}, search_terms=["A测试客户", "若"])

    assert exc.value.reason == "wechat_window_lost_before_search"
    assert activations == ["微信"]


def test_open_conversation_probe_does_not_send_message(tmp_path, monkeypatch):
    import pywinauto.keyboard

    sent_keys: list[str] = []
    probe = WindowProbeDriver(
        process_provider=lambda: [
            {
                "name": "Weixin",
                "pid": 34888,
                "title": "微信",
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
        window_activator=lambda status: (True, "activated"),
    )
    driver.controlled_screen_state.calibrated = True
    matched_contact = FakeControl()

    monkeypatch.setattr(pywinauto.keyboard, "send_keys", lambda keys, **kwargs: sent_keys.append(keys))
    monkeypatch.setattr(driver, "_connect_window", lambda: FakeWindow())
    monkeypatch.setattr(driver, "_find_chat_search_edit", lambda window: FakeControl())
    monkeypatch.setattr(driver, "_visible_texts", lambda window: ["聊天", "A测试客户"])
    monkeypatch.setattr(driver, "_find_exact_text_element", lambda window, target: matched_contact)
    monkeypatch.setattr(driver, "_current_conversation_title", lambda window, **kwargs: "A测试客户")

    result = driver.open_conversation(target_id="wxid_contact", search_terms=["A测试客户", "若"])

    assert result.success is True
    assert result.message == "conversation_opened"
    assert result.opened_conversation_title == "A测试客户"
    assert result.search_term_used == "A测试客户"
    assert "{ENTER}" not in sent_keys
    assert all("这是测试说明" not in keys for keys in sent_keys)
