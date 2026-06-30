from __future__ import annotations

import os
import time
import ctypes
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Any
from uuid import uuid4

from app.services.guardrails import LocalActionResult
from app.services.local_contacts import WechatLocalContactExtractor


_DPI_AWARENESS_ATTEMPTED = False


def ensure_process_dpi_awareness() -> None:
    global _DPI_AWARENESS_ATTEMPTED
    if _DPI_AWARENESS_ATTEMPTED:
        return
    _DPI_AWARENESS_ATTEMPTED = True
    if os.name != "nt":
        return
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


@dataclass(frozen=True)
class WindowProbeStatus:
    detected: bool
    process_name: str
    window_title: str
    pid: int | None = None
    path: str = ""
    reason: str = ""
    hwnd: int | None = None
    class_name: str = ""
    rect: tuple[int, int, int, int] | None = None
    foreground_match: bool = False
    activation_status: str = ""
    is_minimized: bool = False
    show_cmd: int | None = None
    foreground_title: str = ""


@dataclass(frozen=True)
class Evidence:
    path: str
    kind: str
    target_id: str
    created_at: str


@dataclass(frozen=True)
class SearchResolution:
    allowed: bool
    reason: str
    matched_target: str = ""


@dataclass
class ControlledScreenState:
    calibrated: bool = False
    calibrated_at: str | None = None
    anchors: dict[str, Any] = field(default_factory=dict)
    live_gate_verified: bool = False
    last_verified_at: str | None = None
    last_receipt: dict[str, Any] | None = None


AGENT_ROOT = Path(__file__).resolve().parents[3]
NON_SCREEN_SEND_MESSAGE = "非屏幕发送通道未验证，未执行发送"
NON_SCREEN_SEND_BLOCKED_REASON = "non_screen_send_driver_not_verified"
CONTROLLED_SCREEN_CALIBRATION_MESSAGE = "请先校准微信窗口，未执行发送"
CONTROLLED_SCREEN_LIVE_GATE_MESSAGE = "微信窗口已校准，可先发送 1 个测试客户完成验证"
CONTROLLED_SCREEN_VERIFIED_MESSAGE = "受控窗口自动化已通过单人验证，可执行 3 人小批量"


def build_non_screen_send_driver_probe(*, mode: str = "non_screen") -> dict[str, object]:
    return {
        "mode": mode,
        "verified": False,
        "message": NON_SCREEN_SEND_MESSAGE,
        "capabilities": ["contact_sync", "touch_preview", "audit_log"],
        "blocked_reason": NON_SCREEN_SEND_BLOCKED_REASON,
        "research_report_path": str(AGENT_ROOT / "docs" / "non-screen-send-research.md"),
        "research_artifacts": [
            {
                "kind": "contract_scan",
                "path": str(AGENT_ROOT / "docs" / "research" / "dt-ai-helper-contract-scan.json"),
                "available": (AGENT_ROOT / "docs" / "research" / "dt-ai-helper-contract-scan.json").exists(),
            }
        ],
        "last_verified_at": None,
        "last_receipt": None,
        "candidates": [
            {
                "id": "dt_ai_helper_local_service",
                "label": "dt-ai-helper 本地服务合同",
                "status": "research_only",
                "can_send": False,
                "requires_login_window": True,
                "evidence": "已解析 Electron API、PyInstaller 模块、本地任务接口和 WS 事件；关键执行模块仍指向 UIA/OCR/截图/点击，尚未发现非屏幕发送回执。",
                "next_step": "把任务 poll/ack/progress/complete 和 task.paused/task.dispatch 这类可靠状态语义 clean-room 复刻进当前任务中心，自动发送继续关闭。",
            },
            {
                "id": "wechat_local_data_ipc",
                "label": "微信本地数据 / IPC / 进程通道",
                "status": "not_verified",
                "can_send": False,
                "requires_login_window": True,
                "evidence": "本地库路线已能服务通讯录同步；尚未证明写库或进程通道可以安全触发消息发送。",
                "next_step": "只研究只读账本、可验证 IPC 和回执来源，不写入微信数据库。",
            },
            {
                "id": "rpaagent_safety_boundary",
                "label": "参考项目安全边界",
                "status": "reference_only",
                "can_send": False,
                "requires_login_window": False,
                "evidence": "可复用限额、白名单、审计、单人 live gate 思路；不复用屏幕点击发送实现。",
                "next_step": "把安全门控保留在当前产品中，等待真正非屏幕通道验证。",
            },
        ],
    }


def build_controlled_screen_send_driver_probe(state: ControlledScreenState, *, mode: str = "controlled_screen") -> dict[str, object]:
    max_batch_size = 3 if state.live_gate_verified else 1 if state.calibrated else 0
    message = (
        CONTROLLED_SCREEN_VERIFIED_MESSAGE
        if state.live_gate_verified
        else CONTROLLED_SCREEN_LIVE_GATE_MESSAGE
        if state.calibrated
        else CONTROLLED_SCREEN_CALIBRATION_MESSAGE
    )
    blocked_reason = "" if state.live_gate_verified else "live_gate_required" if state.calibrated else "window_calibration_required"
    return {
        "mode": mode,
        "verified": state.live_gate_verified,
        "calibrated": state.calibrated,
        "message": message,
        "capabilities": ["contact_sync", "touch_preview", "window_normalize", "controlled_screen_send", "audit_log"],
        "blocked_reason": blocked_reason,
        "max_batch_size": max_batch_size,
        "calibrated_at": state.calibrated_at,
        "anchors": state.anchors,
        "research_report_path": str(AGENT_ROOT / "docs" / "non-screen-send-research.md"),
        "research_artifacts": [
            {
                "kind": "contract_scan",
                "path": str(AGENT_ROOT / "docs" / "research" / "dt-ai-helper-contract-scan.json"),
                "available": (AGENT_ROOT / "docs" / "research" / "dt-ai-helper-contract-scan.json").exists(),
            }
        ],
        "last_verified_at": state.last_verified_at,
        "last_receipt": state.last_receipt,
        "candidates": [
            {
                "id": "controlled_wechat_window_automation",
                "label": "受控微信窗口自动化",
                "status": "verified" if state.live_gate_verified else "calibrated" if state.calibrated else "not_calibrated",
                "can_send": max_batch_size > 0,
                "requires_login_window": True,
                "evidence": "固定微信窗口到左上角，用 UIA/OCR/截图证据做目标校验；未校验目标时不发送。",
                "next_step": "先完成 1 个测试客户 live gate；成功后开放 3 人小批量。",
            },
            {
                "id": "dt_ai_helper_execution_pattern",
                "label": "dt-ai-helper 实际执行模式",
                "status": "reference_only",
                "can_send": False,
                "requires_login_window": True,
                "evidence": "逆向证据显示其执行层依赖 UIA/OCR/截图/点击，而不是纯非屏幕发送接口。",
                "next_step": "只复刻窗口归一化、状态机、失败拦截和证据链，不复用对方二进制或线上服务。",
            },
        ],
    }


class BlockedSend(RuntimeError):
    def __init__(self, reason: str, *, opened_title: str = "", matched_target: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.opened_title = opened_title
        self.matched_target = matched_target


class SearchResultInspector:
    valid_sections = {"聊天", "联系人", "最近聊天", "最近联系人"}
    wrong_surface_markers = {
        "搜索网络结果",
        "AI搜索",
        "搜一搜",
        "文章",
        "视频",
        "账号",
        "直播",
        "表情",
        "新闻",
        "贴图",
        "划线",
    }

    def __init__(self, visible_texts: list[str]) -> None:
        self.visible_texts = [text.strip() for text in visible_texts if text and text.strip()]

    def resolve(self, *, target_id: str, aliases: list[str]) -> SearchResolution:
        normalized_aliases = {self._normalize(alias) for alias in [target_id, *aliases] if alias.strip()}
        matches: list[str] = []
        for index, text in enumerate(self.visible_texts):
            if self._normalize(text) not in normalized_aliases:
                continue
            nearby = {self._normalize(value) for value in self.visible_texts[max(0, index - 3) : index + 1]}
            if nearby & {self._normalize(section) for section in self.valid_sections}:
                matches.append(text)
        if len(matches) == 1:
            return SearchResolution(allowed=True, reason="matched", matched_target=matches[0])
        if len(matches) > 1:
            return SearchResolution(allowed=False, reason="blocked_ambiguous_target")
        if self._has_wrong_surface():
            return SearchResolution(allowed=False, reason="blocked_wrong_search_surface")
        return SearchResolution(allowed=False, reason="blocked_target_not_found")

    def _has_wrong_surface(self) -> bool:
        normalized = [self._normalize(text) for text in self.visible_texts]
        return any(marker in text for marker in self.wrong_surface_markers for text in normalized)

    @staticmethod
    def _normalize(value: str) -> str:
        return "".join(value.split()).strip().lower()


class WindowProbeDriver:
    main_window_classes = {"Qt51514QWindowIcon", "mmui::MainWindow"}
    excluded_titles = {"WxTrayIconMessageWindow", "Default IME", "MSCTFIME UI"}
    excluded_class_markers = (
        "trayicon",
        "ime",
        "powermessagewindow",
        "chrome",
        "displayicc",
    )

    def __init__(
        self,
        *,
        process_name: str = "Weixin",
        window_title: str = "微信",
        process_provider: Callable[[], list[dict[str, Any]]] | None = None,
    ) -> None:
        self.process_name = process_name
        self.window_title = window_title
        self.process_provider = process_provider or self._default_process_provider

    def probe(self) -> WindowProbeStatus:
        process_name_lower = self.process_name.lower()
        matched_process: dict[str, Any] | None = None
        candidates: list[tuple[float, dict[str, Any]]] = []
        for process in self.process_provider():
            name = str(process.get("name") or "")
            title = str(process.get("title") or "")
            if name.lower() != process_name_lower:
                continue
            matched_process = process
            score = self._main_window_score(process)
            if score > 0:
                candidates.append((score, process))
        if candidates:
            _, process = max(candidates, key=lambda item: item[0])
            return WindowProbeStatus(
                detected=True,
                process_name=str(process.get("name") or self.process_name),
                window_title=str(process.get("title") or self.window_title),
                pid=self._optional_int(process.get("pid")),
                path=str(process.get("path") or ""),
                hwnd=self._optional_int(process.get("hwnd")),
                class_name=str(process.get("class_name") or ""),
                rect=self._rect_tuple(process.get("rect")),
                foreground_match=bool(process.get("foreground_match")),
                activation_status="already_foreground" if process.get("foreground_match") else "",
                is_minimized=bool(process.get("is_minimized")),
                show_cmd=self._optional_int(process.get("show_cmd")),
                foreground_title=str(process.get("foreground_title") or ""),
            )
        if matched_process is not None:
            return WindowProbeStatus(
                detected=False,
                process_name=str(matched_process.get("name") or self.process_name),
                window_title=self.window_title,
                pid=self._optional_int(matched_process.get("pid")),
                path=str(matched_process.get("path") or ""),
                hwnd=self._optional_int(matched_process.get("hwnd")),
                class_name=str(matched_process.get("class_name") or ""),
                rect=self._rect_tuple(matched_process.get("rect")),
                foreground_match=bool(matched_process.get("foreground_match")),
                is_minimized=bool(matched_process.get("is_minimized")),
                show_cmd=self._optional_int(matched_process.get("show_cmd")),
                foreground_title=str(matched_process.get("foreground_title") or ""),
                reason="wechat_process_found_but_main_window_hidden",
            )
        return WindowProbeStatus(
            detected=False,
            process_name=self.process_name,
            window_title=self.window_title,
            reason="wechat_window_not_found",
        )

    def _main_window_score(self, process: dict[str, Any]) -> float:
        title = str(process.get("title") or "")
        class_name = str(process.get("class_name") or "")
        if self._is_excluded_window(title=title, class_name=class_name):
            return 0
        title_matches = not self.window_title or self.window_title == title or self.window_title in title
        class_matches = class_name in self.main_window_classes
        if not title_matches and not class_matches:
            return 0
        rect = self._rect_tuple(process.get("rect"))
        area = self._rect_area(rect)
        score = 0.0
        if title == self.window_title:
            score += 1000
        elif title_matches:
            score += 800
        if class_matches:
            score += 500
        if bool(process.get("visible")):
            score += 25
        if bool(process.get("foreground_match")):
            score += 50
        score += min(area / 10000, 100)
        return score

    def _is_excluded_window(self, *, title: str, class_name: str) -> bool:
        if title in self.excluded_titles:
            return True
        lowered = class_name.lower()
        return any(marker in lowered for marker in self.excluded_class_markers)

    @staticmethod
    def _optional_int(value: object) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _rect_tuple(value: object) -> tuple[int, int, int, int] | None:
        if not isinstance(value, (tuple, list)) or len(value) != 4:
            return None
        try:
            left, top, right, bottom = (int(item) for item in value)
            return left, top, right, bottom
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _rect_area(rect: tuple[int, int, int, int] | None) -> int:
        if rect is None:
            return 0
        left, top, right, bottom = rect
        return max(0, right - left) * max(0, bottom - top)

    @staticmethod
    def _default_process_provider() -> list[dict[str, Any]]:
        ensure_process_dpi_awareness()
        try:
            import win32gui
            import win32process
            import psutil
        except Exception:
            return []

        processes: dict[int, dict[str, Any]] = {}
        for proc in psutil.process_iter(["name", "pid", "exe"]):
            info = proc.info
            pid = info.get("pid")
            if pid is None:
                continue
            processes[int(pid)] = {
                "name": Path(info.get("name") or "").stem,
                "pid": int(pid),
                "path": info.get("exe") or "",
            }

        rows: list[dict[str, Any]] = []
        hwnd_pids: set[int] = set()
        foreground_hwnd = 0
        foreground_pid: int | None = None
        try:
            foreground_hwnd = int(win32gui.GetForegroundWindow())
            _, raw_foreground_pid = win32process.GetWindowThreadProcessId(foreground_hwnd)
            foreground_pid = int(raw_foreground_pid)
        except Exception:
            pass
        foreground_title = ""
        try:
            foreground_title = win32gui.GetWindowText(foreground_hwnd) if foreground_hwnd else ""
        except Exception:
            foreground_title = ""

        def collect(hwnd: int, _: int) -> None:
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                pid = int(pid)
                title = win32gui.GetWindowText(hwnd)
                class_name = win32gui.GetClassName(hwnd)
                rect = tuple(int(item) for item in win32gui.GetWindowRect(hwnd))
                placement = win32gui.GetWindowPlacement(hwnd)
                row = {
                    **processes.get(pid, {"name": "", "pid": pid, "path": ""}),
                    "title": title,
                    "class_name": class_name,
                    "hwnd": int(hwnd),
                    "visible": bool(win32gui.IsWindowVisible(hwnd)),
                    "enabled": bool(win32gui.IsWindowEnabled(hwnd)),
                    "rect": rect,
                    "foreground_match": int(hwnd) == foreground_hwnd or pid == foreground_pid,
                    "is_minimized": bool(win32gui.IsIconic(hwnd)),
                    "show_cmd": int(placement[1]) if isinstance(placement, tuple) and len(placement) > 1 else None,
                    "foreground_title": foreground_title,
                }
            except Exception:
                return
            rows.append(row)
            hwnd_pids.add(pid)

        win32gui.EnumWindows(collect, 0)
        for pid, process in processes.items():
            if pid not in hwnd_pids:
                rows.append({**process, "title": "", "class_name": "", "hwnd": None, "visible": False, "rect": None})
        return rows


class EvidenceRecorder:
    def __init__(
        self,
        base_dir: str | Path,
        *,
        screenshot_provider: Callable[[Path], bool] | None = None,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_provider = screenshot_provider or self._default_screenshot_provider

    def capture(self, step: str, *, target_id: str = "") -> Evidence:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        path = self.base_dir / f"{stamp}_{step}_{uuid4().hex[:8]}.png"
        captured = self.screenshot_provider(path)
        if not captured:
            path = path.with_suffix(".txt")
            path.write_text(f"placeholder evidence for {step}, target={target_id}\n", encoding="utf-8")
        return Evidence(
            path=str(path),
            kind="screenshot" if captured else "placeholder",
            target_id=target_id,
            created_at=datetime.now(UTC).isoformat(),
        )

    @staticmethod
    def _default_screenshot_provider(path: Path) -> bool:
        try:
            from PIL import ImageGrab

            image = ImageGrab.grab()
            image.save(path)
            return True
        except Exception:
            return False


class RealAutomationDriver:
    def __init__(
        self,
        *,
        probe_driver: WindowProbeDriver,
        evidence_recorder: EvidenceRecorder,
        local_contact_extractor: WechatLocalContactExtractor | None = None,
        human_pause_seconds: tuple[float, float] = (1.2, 2.8),
        window_activator: Callable[[WindowProbeStatus], tuple[bool, str]] | None = None,
        target_window_size: tuple[int, int] = (1280, 900),
    ) -> None:
        self.probe_driver = probe_driver
        self.evidence_recorder = evidence_recorder
        self.local_contact_extractor = local_contact_extractor or WechatLocalContactExtractor()
        self.human_pause_seconds = human_pause_seconds
        self.window_activator = window_activator or self._default_window_activator
        self.target_window_size = target_window_size
        self.controlled_screen_state = ControlledScreenState()
        self.stopped = False

    def status(self) -> dict[str, object]:
        probe = self.probe_driver.probe()
        return {
            "mode": "real",
            "wechat_status": "ready" if probe.detected else "missing",
            "process_name": probe.process_name,
            "window_title": probe.window_title,
            "pid": probe.pid,
            "path": probe.path,
            "reason": probe.reason,
            "hwnd": probe.hwnd,
            "class_name": probe.class_name,
            "rect": probe.rect,
            "foreground_match": probe.foreground_match,
            "activation_status": probe.activation_status,
            "is_minimized": probe.is_minimized,
            "show_cmd": probe.show_cmd,
            "foreground_title": probe.foreground_title,
        }

    def local_accounts(self) -> list[dict[str, Any]]:
        return self.local_contact_extractor.list_accounts()

    def sync_contacts(self, *, account_id: str = "auto", auto_decrypt: bool = True) -> dict[str, object]:
        return self.local_contact_extractor.sync_contacts(account_id=account_id, auto_decrypt=auto_decrypt)

    def send_driver_probe(self) -> dict[str, object]:
        return build_controlled_screen_send_driver_probe(self.controlled_screen_state)

    def normalize_window(self) -> dict[str, object]:
        probe = self.probe_driver.probe()
        if not probe.detected or not probe.hwnd:
            evidence = self.evidence_recorder.capture("window_normalize_failed")
            return {
                "success": False,
                "message": probe.reason or "wechat_window_not_found",
                "detected": probe.detected,
                "hwnd": probe.hwnd,
                "evidence": {"window_normalize_failed": evidence.path},
            }
        success, reason = self._normalize_window(probe)
        evidence = self.evidence_recorder.capture("window_normalized" if success else "window_normalize_failed")
        refreshed = self.probe_driver.probe()
        return {
            "success": success,
            "message": reason,
            "detected": refreshed.detected,
            "hwnd": refreshed.hwnd,
            "pid": refreshed.pid,
            "rect": refreshed.rect,
            "class_name": refreshed.class_name,
            "foreground_match": refreshed.foreground_match,
            "evidence": {"window_normalized" if success else "window_normalize_failed": evidence.path},
        }

    def prepare_dedicated_desktop(self) -> dict[str, object]:
        probe = self.probe_driver.probe()
        if not probe.detected or not probe.hwnd:
            evidence = self.evidence_recorder.capture("desktop_prepare_failed")
            return {
                "success": False,
                "message": probe.reason or "wechat_window_not_found",
                "probe": self._probe_payload(probe),
                "evidence": {"desktop_prepare_failed": evidence.path},
            }
        normalized = self.normalize_window()
        refreshed = self.probe_driver.probe()
        activated, reason = self.window_activator(refreshed)
        final_probe = self.probe_driver.probe()
        success = activated and final_probe.foreground_match
        evidence = self.evidence_recorder.capture("desktop_prepared" if success else "activation_failed")
        return {
            "success": success,
            "message": "dedicated_desktop_ready" if success else "wechat_window_not_foreground",
            "activation_reason": reason,
            "normalize": normalized,
            "probe": self._probe_payload(final_probe),
            "evidence": {"desktop_prepared" if success else "activation_failed": evidence.path},
        }

    def calibrate_send_driver(self) -> dict[str, object]:
        normalized = self.normalize_window()
        if not bool(normalized.get("success")):
            self.controlled_screen_state.calibrated = False
            return {
                "success": False,
                "calibrated": False,
                "message": str(normalized.get("message") or "window_normalize_failed"),
                "normalize": normalized,
            }
        rect = self._rect_tuple(normalized.get("rect"))
        if rect is None:
            self.controlled_screen_state.calibrated = False
            return {"success": False, "calibrated": False, "message": "window_rect_missing", "normalize": normalized}
        anchors = self._default_relative_anchors(rect)
        evidence = self.evidence_recorder.capture("send_driver_calibrated")
        self.controlled_screen_state.calibrated = True
        self.controlled_screen_state.calibrated_at = datetime.now(UTC).isoformat()
        self.controlled_screen_state.anchors = anchors
        return {
            "success": True,
            "calibrated": True,
            "message": CONTROLLED_SCREEN_LIVE_GATE_MESSAGE,
            "rect": rect,
            "anchors": anchors,
            "evidence": {"send_driver_calibrated": evidence.path},
            "send_driver": self.send_driver_probe(),
        }

    def send_message(self, *, target_id: str, content: str, search_terms: list[str] | None = None) -> LocalActionResult:
        evidence: dict[str, Any] = {}
        probe = self.probe_driver.probe()
        if not probe.detected:
            before_probe = self.evidence_recorder.capture("before_probe", target_id=target_id)
            evidence["before_probe"] = before_probe.path
            return LocalActionResult(
                success=False,
                message="wechat_window_not_found",
                dry_run=False,
                evidence={**evidence, "reason": probe.reason},
                verification_status="failed",
                failure_reason=probe.reason or "wechat_window_not_found",
            )
        if not self.controlled_screen_state.calibrated:
            failure = self.evidence_recorder.capture("calibration_required", target_id=target_id)
            return LocalActionResult(
                success=False,
                message="controlled_screen_calibration_required",
                dry_run=False,
                evidence={"calibration_required": failure.path},
                verification_status="blocked",
                failure_reason="controlled_screen_calibration_required",
            )
        activated, activation_reason = self.window_activator(probe)
        if not activated:
            failure = self.evidence_recorder.capture("activation_failed", target_id=target_id)
            evidence["activation_failed"] = failure.path
            return LocalActionResult(
                success=False,
                message="blocked_window_not_foreground",
                dry_run=False,
                evidence={**evidence, "reason": activation_reason, "hwnd": probe.hwnd, "pid": probe.pid},
                verification_status="blocked",
                opened_conversation_title=probe.window_title,
                failure_reason=activation_reason or "foreground_not_changed",
            )
        window_activated = self.evidence_recorder.capture("window_activated", target_id=target_id)
        before_search = self.evidence_recorder.capture("before_search", target_id=target_id)
        evidence["window_activated"] = window_activated.path
        evidence["before_search"] = before_search.path
        try:
            verification = self._send_via_pywinauto(target_id=target_id, content=content, evidence=evidence, search_terms=search_terms or [])
        except BlockedSend as exc:
            failure = self.evidence_recorder.capture("failure", target_id=target_id)
            evidence["failure"] = failure.path
            return LocalActionResult(
                success=False,
                message=exc.reason,
                dry_run=False,
                evidence=evidence,
                verification_status="blocked",
                opened_conversation_title=exc.opened_title,
                matched_target=exc.matched_target,
                failure_reason=exc.reason,
            )
        except Exception as exc:
            failure = self.evidence_recorder.capture("send_failed", target_id=target_id)
            return LocalActionResult(
                success=False,
                message=f"send_failed:{type(exc).__name__}",
                dry_run=False,
                evidence={**evidence, "failure": failure.path},
                verification_status="failed",
                failure_reason=f"send_failed:{type(exc).__name__}",
            )
        return LocalActionResult(
            success=True,
            message="message_sent",
            dry_run=False,
            evidence=evidence,
            verification_status="verified",
            opened_conversation_title=str(verification.get("opened_conversation_title") or ""),
            matched_target=str(verification.get("matched_target") or target_id),
            search_term_used=str(verification.get("search_term_used") or ""),
            receipt=self._mark_live_gate_verified(target_id=target_id, verification=verification),
        )

    def like_moment(self, *, target_id: str, comment: str = "") -> LocalActionResult:
        evidence = self.evidence_recorder.capture("moments_interaction", target_id=target_id)
        probe = self.probe_driver.probe()
        if not probe.detected:
            return LocalActionResult(success=False, message="wechat_window_not_found", dry_run=False, evidence={"evidence_path": evidence.path})
        return LocalActionResult(success=False, message="moments_driver_needs_visible_feed", dry_run=False, evidence={"evidence_path": evidence.path, "comment": comment})

    def stop(self) -> LocalActionResult:
        self.stopped = True
        return LocalActionResult(success=True, message="stop signal accepted", dry_run=False)

    def _send_via_pywinauto(self, *, target_id: str, content: str, evidence: dict[str, Any], search_terms: list[str] | None = None) -> dict[str, str]:
        import random
        from pywinauto.keyboard import send_keys

        aliases = self._search_aliases(target_id=target_id, search_terms=search_terms or [])
        first_search_term = aliases[0]
        window = self._connect_window()
        window.set_focus()
        time.sleep(random.uniform(*self.human_pause_seconds))
        send_keys("{ESC}")
        time.sleep(0.3)
        send_keys("{ESC}")
        search_box = self._find_chat_search_edit(window)
        if search_box is None and not self._click_calibrated_anchor("search_box"):
            raise BlockedSend("blocked_search_input_missing")
        if search_box is not None:
            search_box.click_input()
        time.sleep(random.uniform(*self.human_pause_seconds))
        send_keys("^a{BACKSPACE}")
        send_keys(first_search_term, with_spaces=True)
        time.sleep(random.uniform(*self.human_pause_seconds))
        evidence["search_results"] = self.evidence_recorder.capture("search_results", target_id=target_id).path
        texts = self._visible_texts(window)
        decision = SearchResultInspector(texts).resolve(target_id=target_id, aliases=aliases)
        if not decision.allowed:
            raise BlockedSend(decision.reason)
        candidate = self._find_exact_text_element(window, decision.matched_target)
        if candidate is None:
            raise BlockedSend("blocked_target_element_missing", matched_target=decision.matched_target)
        candidate.click_input()
        time.sleep(random.uniform(*self.human_pause_seconds))
        opened_title = self._current_conversation_title(window, target_id=target_id, aliases=aliases)
        if not opened_title or not self._title_matches(opened_title, aliases):
            raise BlockedSend("blocked_conversation_mismatch", opened_title=opened_title, matched_target=decision.matched_target)
        evidence["conversation_verified"] = self.evidence_recorder.capture("conversation_verified", target_id=target_id).path
        input_box = self._find_message_input(window)
        if input_box is None and not self._click_calibrated_anchor("message_input"):
            raise BlockedSend("blocked_message_input_missing", opened_title=opened_title, matched_target=decision.matched_target)
        if input_box is not None:
            input_box.click_input()
        time.sleep(random.uniform(*self.human_pause_seconds))
        send_keys(content, with_spaces=True)
        time.sleep(random.uniform(*self.human_pause_seconds))
        evidence["before_send"] = self.evidence_recorder.capture("before_send", target_id=target_id).path
        send_keys("{ENTER}")
        time.sleep(random.uniform(*self.human_pause_seconds))
        evidence["after_send"] = self.evidence_recorder.capture("after_send", target_id=target_id).path
        if not self._message_visible(window, content):
            raise BlockedSend("failed_message_not_verified", opened_title=opened_title, matched_target=decision.matched_target)
        return {"opened_conversation_title": opened_title, "matched_target": decision.matched_target, "search_term_used": first_search_term}

    def _read_visible_text_contacts(self, *, limit: int) -> list[dict[str, str]]:
        try:
            window = self._connect_window()
            try:
                window.child_window(title="通讯录", control_type="Button").click_input()
                time.sleep(1.2)
            except Exception:
                pass
            texts: list[str] = []
            for child in window.descendants()[:300]:
                value = (child.window_text() or "").strip()
                value = value.splitlines()[0].strip() if value else ""
                if self._looks_like_contact(value) and value not in texts:
                    texts.append(value)
            return [{"wxid": text, "nickname": text, "source": "visible_text"} for text in texts[:limit]]
        except Exception:
            return []

    def _connect_window(self):
        import pywinauto

        probe = self.probe_driver.probe()
        if probe.hwnd:
            try:
                return pywinauto.Application(backend="uia").connect(handle=probe.hwnd).window(handle=probe.hwnd)
            except Exception:
                try:
                    return pywinauto.Application(backend="win32").connect(handle=probe.hwnd).window(handle=probe.hwnd)
                except Exception:
                    pass
        if probe.pid:
            app = pywinauto.Application(backend="uia").connect(process=probe.pid)
            windows = app.windows()
            for window in windows:
                try:
                    if window.window_text() == self.probe_driver.window_title:
                        return window
                except Exception:
                    continue
            if windows:
                return max(windows, key=lambda item: item.rectangle().width() * item.rectangle().height())
        app = pywinauto.Application(backend="uia").connect(title_re=".*Weixin.*")
        return app.window(title_re=".*Weixin.*")

    @staticmethod
    def _default_window_activator(status: WindowProbeStatus) -> tuple[bool, str]:
        ensure_process_dpi_awareness()
        if not status.hwnd:
            return False, "wechat_hwnd_missing"
        try:
            import win32con
            import win32gui
            import win32process
            import win32api
        except Exception as exc:
            return False, f"win32_unavailable:{type(exc).__name__}"

        attached_threads: list[int] = []
        try:
            current_thread = win32api.GetCurrentThreadId()
            foreground_hwnd = int(win32gui.GetForegroundWindow())
            foreground_thread = 0
            if foreground_hwnd:
                foreground_thread, _ = win32process.GetWindowThreadProcessId(foreground_hwnd)
            target_thread, _ = win32process.GetWindowThreadProcessId(status.hwnd)
            for thread_id in {int(foreground_thread), int(target_thread)}:
                if thread_id and thread_id != current_thread:
                    try:
                        win32process.AttachThreadInput(current_thread, thread_id, True)
                        attached_threads.append(thread_id)
                    except Exception:
                        pass
            win32gui.ShowWindowAsync(status.hwnd, win32con.SW_RESTORE)
            time.sleep(0.1)
            win32gui.BringWindowToTop(status.hwnd)
            try:
                flags = win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
                win32gui.SetWindowPos(status.hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, flags)
                win32gui.SetWindowPos(status.hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, flags)
            except Exception:
                pass
            time.sleep(0.15)
            win32gui.SetForegroundWindow(status.hwnd)
        except Exception as exc:
            return False, f"foreground_set_failed:{type(exc).__name__}"
        finally:
            try:
                current_thread = win32api.GetCurrentThreadId()
                for thread_id in attached_threads:
                    win32process.AttachThreadInput(current_thread, thread_id, False)
            except Exception:
                pass

        deadline = time.time() + 2.0
        while time.time() < deadline:
            try:
                foreground_hwnd = int(win32gui.GetForegroundWindow())
                _, foreground_pid = win32process.GetWindowThreadProcessId(foreground_hwnd)
                if foreground_hwnd == status.hwnd or (status.pid is not None and int(foreground_pid) == status.pid):
                    return True, "activated"
            except Exception:
                pass
            time.sleep(0.1)
        return False, "foreground_not_changed"

    @staticmethod
    def _probe_payload(probe: WindowProbeStatus) -> dict[str, object]:
        return {
            "detected": probe.detected,
            "process_name": probe.process_name,
            "window_title": probe.window_title,
            "pid": probe.pid,
            "path": probe.path,
            "reason": probe.reason,
            "hwnd": probe.hwnd,
            "class_name": probe.class_name,
            "rect": probe.rect,
            "foreground_match": probe.foreground_match,
            "activation_status": probe.activation_status,
            "is_minimized": probe.is_minimized,
            "show_cmd": probe.show_cmd,
            "foreground_title": probe.foreground_title,
        }

    def _normalize_window(self, status: WindowProbeStatus) -> tuple[bool, str]:
        ensure_process_dpi_awareness()
        if not status.hwnd:
            return False, "wechat_hwnd_missing"
        try:
            import win32con
            import win32gui
        except Exception as exc:
            return False, f"win32_unavailable:{type(exc).__name__}"

        width, height = self.target_window_size
        try:
            win32gui.ShowWindow(status.hwnd, win32con.SW_RESTORE)
            time.sleep(0.2)
            win32gui.MoveWindow(status.hwnd, 0, 0, width, height, True)
            time.sleep(0.2)
            try:
                win32gui.RedrawWindow(
                    status.hwnd,
                    None,
                    None,
                    win32con.RDW_INVALIDATE | win32con.RDW_UPDATENOW | win32con.RDW_ALLCHILDREN | win32con.RDW_FRAME,
                )
            except Exception:
                pass
            foreground_status = "foreground_set"
            try:
                win32gui.SetForegroundWindow(status.hwnd)
            except Exception as exc:
                foreground_status = f"foreground_set_failed:{type(exc).__name__}"
            time.sleep(0.2)
            return True, "window_normalized" if foreground_status == "foreground_set" else f"window_normalized:{foreground_status}"
        except Exception as exc:
            return False, f"window_normalize_failed:{type(exc).__name__}"

    @staticmethod
    def _rect_tuple(value: object) -> tuple[int, int, int, int] | None:
        if isinstance(value, (list, tuple)) and len(value) == 4:
            try:
                return (int(value[0]), int(value[1]), int(value[2]), int(value[3]))
            except (TypeError, ValueError):
                return None
        return None

    @staticmethod
    def _default_relative_anchors(rect: tuple[int, int, int, int]) -> dict[str, dict[str, int]]:
        left, top, right, bottom = rect
        width = max(1, right - left)
        height = max(1, bottom - top)

        def point(x_ratio: float, y_ratio: float) -> dict[str, int]:
            return {
                "x": int(left + width * x_ratio),
                "y": int(top + height * y_ratio),
            }

        return {
            "search_box": point(0.18, 0.09),
            "first_result_area": point(0.18, 0.17),
            "conversation_title": point(0.46, 0.09),
            "message_input": point(0.62, 0.92),
            "send_button_area": point(0.93, 0.94),
        }

    def _click_calibrated_anchor(self, name: str) -> bool:
        anchor = self.controlled_screen_state.anchors.get(name)
        if not isinstance(anchor, dict):
            return False
        try:
            x = int(anchor["x"])
            y = int(anchor["y"])
        except (KeyError, TypeError, ValueError):
            return False
        try:
            from pywinauto import mouse

            mouse.click(button="left", coords=(x, y))
            return True
        except Exception:
            return False

    def _mark_live_gate_verified(self, *, target_id: str, verification: dict[str, str]) -> dict[str, Any]:
        receipt = {
            "receipt_id": uuid4().hex,
            "channel_id": "controlled_screen",
            "target_id": target_id,
            "matched_target": str(verification.get("matched_target") or ""),
            "opened_conversation_title": str(verification.get("opened_conversation_title") or ""),
            "search_term_used": str(verification.get("search_term_used") or ""),
            "verified_at": datetime.now(UTC).isoformat(),
        }
        self.controlled_screen_state.live_gate_verified = True
        self.controlled_screen_state.last_verified_at = str(receipt["verified_at"])
        self.controlled_screen_state.last_receipt = receipt
        return receipt

    @staticmethod
    def _visible_texts(window) -> list[str]:
        texts: list[str] = []
        for child in window.descendants()[:500]:
            value = (child.window_text() or "").strip()
            if value and value not in texts:
                texts.append(value)
        return texts

    def _find_chat_search_edit(self, window):
        try:
            root_rect = window.rectangle()
            candidates = []
            for child in window.descendants(control_type="Edit"):
                rect = child.rectangle()
                if rect.left < root_rect.left + 340 and rect.top < root_rect.top + 140:
                    candidates.append(child)
            return candidates[0] if candidates else None
        except Exception:
            return None

    def _find_exact_text_element(self, window, target: str):
        try:
            root_rect = window.rectangle()
            for child in window.descendants()[:500]:
                if (child.window_text() or "").strip() != target:
                    continue
                rect = child.rectangle()
                if root_rect.left + 60 <= rect.left <= root_rect.left + 430 and rect.top > root_rect.top + 90:
                    return child
        except Exception:
            return None
        return None

    def _current_conversation_title(self, window, *, target_id: str, aliases: list[str] | None = None) -> str:
        expected = self._search_aliases(target_id=target_id, search_terms=aliases or [])
        try:
            root_rect = window.rectangle()
            for child in window.descendants()[:300]:
                text = (child.window_text() or "").strip()
                if not text or not self._title_matches(text, expected):
                    continue
                rect = child.rectangle()
                if rect.left > root_rect.left + 360 and rect.top < root_rect.top + 150:
                    return text
        except Exception:
            return ""
        return ""

    def _find_message_input(self, window):
        try:
            root_rect = window.rectangle()
            candidates = []
            for child in window.descendants(control_type="Edit"):
                rect = child.rectangle()
                if rect.left > root_rect.left + 300 and rect.top > root_rect.bottom - 220:
                    candidates.append((rect.width() * rect.height(), child))
            if candidates:
                return max(candidates, key=lambda item: item[0])[1]
        except Exception:
            return None
        return None

    def _message_visible(self, window, content: str) -> bool:
        snippet = content[: min(len(content), 24)]
        return any(snippet in text for text in self._visible_texts(window))

    @staticmethod
    def _search_aliases(*, target_id: str, search_terms: list[str]) -> list[str]:
        aliases: list[str] = []
        for value in [*search_terms, target_id]:
            cleaned = str(value or "").strip()
            if cleaned and cleaned not in aliases:
                aliases.append(cleaned)
        return aliases or [target_id]

    @staticmethod
    def _title_matches(title: str, aliases: list[str]) -> bool:
        normalized_title = SearchResultInspector._normalize(title)
        return any(SearchResultInspector._normalize(alias) in normalized_title for alias in aliases if alias)

    @staticmethod
    def _looks_like_contact(value: str) -> bool:
        if not value or len(value) > 40:
            return False
        blocked = {
            "微信",
            "通讯录",
            "收藏",
            "朋友圈",
            "视频号",
            "搜一搜",
            "游戏中心",
            "小程序面板",
            "手机",
            "更多",
            "导航",
            "MMUIRenderSubWindowHW",
            "快捷操作",
            "会话",
            "群聊",
            "公众号",
            "标签",
        }
        if value in blocked:
            return False
        if value.startswith("搜索") or value.startswith("新的朋友"):
            return False
        return True


def build_default_driver() -> RealAutomationDriver:
    root = Path(os.environ.get("AGENT_ROOT", Path(__file__).resolve().parents[3]))
    evidence_dir = root / "evidence"
    return RealAutomationDriver(
        probe_driver=WindowProbeDriver(
            process_name=os.environ.get("WECHAT_PROCESS_NAME", "Weixin"),
            window_title=os.environ.get("WECHAT_WINDOW_TITLE", "微信"),
        ),
        evidence_recorder=EvidenceRecorder(evidence_dir),
        local_contact_extractor=WechatLocalContactExtractor(),
    )
