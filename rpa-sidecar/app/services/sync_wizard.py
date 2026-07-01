from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from typing import Any


class SyncWizard:
    def __init__(
        self,
        *,
        restart_wechat: Callable[[], dict[str, object]],
        login_probe: Callable[..., dict[str, object]],
        sync_contacts: Callable[..., dict[str, object]],
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.restart_wechat = restart_wechat
        self.login_probe = login_probe
        self.sync_contacts = sync_contacts
        self.sleep = sleep
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._cancelled = False
        self._status: dict[str, object] = self._base_status("idle", "等待开始", "点击静默同步通讯录开始")

    def start(self, *, restart_wechat: bool = True, timeout_seconds: int = 180, run_async: bool = True) -> dict[str, object]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return self.status()
            self._cancelled = False
            self._status = self._base_status("starting", "准备同步", "正在准备微信登录同步")
        if run_async:
            self._thread = threading.Thread(
                target=self._run,
                kwargs={"restart_wechat": restart_wechat, "timeout_seconds": timeout_seconds},
                daemon=True,
            )
            self._thread.start()
            return self.status()
        self._run(restart_wechat=restart_wechat, timeout_seconds=timeout_seconds)
        return self.status()

    def status(self) -> dict[str, object]:
        with self._lock:
            return dict(self._status)

    def cancel(self) -> dict[str, object]:
        with self._lock:
            self._cancelled = True
            self._set_status("cancelled", "已取消", "已停止本次通讯录同步")
            return dict(self._status)

    def _run(self, *, restart_wechat: bool, timeout_seconds: int) -> None:
        try:
            login_started_at = time.time()
            if restart_wechat:
                self._set_status("restarting_wechat", "正在重启微信", "正在关闭并重新打开微信")
                restart_result = self.restart_wechat()
                if restart_result.get("success") is False:
                    self._fail(str(restart_result.get("reason") or restart_result.get("message") or "wechat_restart_failed"))
                    return

            self._set_status("waiting_login", "等待微信登录", "请在微信里完成扫码或手机确认")
            if not self._wait_for_login(timeout_seconds, started_at=login_started_at):
                self._fail("wechat_login_timeout")
                return

            self._set_status("preparing_contact_db", "正在准备通讯录", "微信已登录，正在等待本地通讯录加载稳定")
            settle_seconds = max(0.0, float(os.environ.get("WECHAT_LOGIN_SETTLE_SECONDS", "12")))
            if settle_seconds:
                self.sleep(settle_seconds)
            if self._cancelled:
                self._fail("sync_cancelled")
                return

            self._set_status("syncing_contacts", "正在读取通讯录", "正在解密并读取本机微信通讯录")
            result = self.sync_contacts(account_id="auto", auto_decrypt=True)
            if result.get("success") is False:
                extra: dict[str, object] = {"sync_result": self._public_sync_result(result)}
                if bool(result.get("needs_admin_helper")):
                    extra.update(
                        {
                            "requires_admin_helper": True,
                            "admin_action": "start_contact_sync_admin_helper",
                            "account_id": str(result.get("account_id") or ""),
                            "account_dir": str(result.get("account_dir") or ""),
                            "diagnostic": result.get("diagnostic") if isinstance(result.get("diagnostic"), dict) else {},
                        }
                    )
                self._fail(
                    self._failure_reason(result),
                    extra=extra,
                )
                return

            self._set_status(
                "completed",
                "同步完成",
                f"同步到 {int(result.get('friend_count') or 0)} 个微信好友",
                extra={
                    "account_id": str(result.get("account_id") or ""),
                    "friend_count": int(result.get("friend_count") or 0),
                    "excluded_count": int(result.get("excluded_count") or len(result.get("excluded") or [])),
                    "sync_result": self._public_sync_result(result),
                },
            )
        except Exception as exc:
            self._fail(f"sync_wizard_error:{type(exc).__name__}")

    def _wait_for_login(self, timeout_seconds: int, *, started_at: float) -> bool:
        deadline = time.monotonic() + max(1, timeout_seconds)
        while time.monotonic() < deadline:
            if self._cancelled:
                self._fail("sync_cancelled")
                return False
            probe = self._login_probe(started_at=started_at)
            if bool(probe.get("logged_in") if "logged_in" in probe else probe.get("detected")):
                return True
            self.sleep(1)
        return False

    def _login_probe(self, *, started_at: float) -> dict[str, object]:
        try:
            return self.login_probe(started_at=started_at)  # type: ignore[misc]
        except TypeError:
            return self.login_probe()

    def _fail(self, reason: str, *, extra: dict[str, object] | None = None) -> None:
        self._set_status("failed", "同步失败", self._human_reason(reason), extra={"error_reason": reason, **(extra or {})})

    def _set_status(self, stage: str, label: str, message: str, *, extra: dict[str, object] | None = None) -> None:
        with self._lock:
            current = {
                **self._status,
                "stage": stage,
                "stage_label": label,
                "message": message,
            }
            if extra:
                current.update(extra)
            self._status = current

    @staticmethod
    def _base_status(stage: str, label: str, message: str) -> dict[str, object]:
        return {
            "stage": stage,
            "stage_label": label,
            "message": message,
            "account_id": "",
            "friend_count": 0,
            "excluded_count": 0,
            "error_reason": "",
            "requires_admin_helper": False,
            "admin_action": "",
            "account_dir": "",
            "diagnostic": {},
            "sync_result": {},
        }

    @staticmethod
    def _public_sync_result(result: dict[str, object]) -> dict[str, object]:
        account = result.get("account") if isinstance(result.get("account"), dict) else {}
        return {
            "success": bool(result.get("success")),
            "reason": str(result.get("reason") or ""),
            "mode": str(result.get("mode") or ""),
            "account_id": str(result.get("account_id") or account.get("account_id") or ""),
            "account_dir": str(result.get("account_dir") or account.get("account_dir") or ""),
            "filter_version": str(result.get("filter_version") or "wechat4_friend_only_v1"),
            "sync_batch_id": str(result.get("sync_batch_id") or ""),
            "friend_count": int(result.get("friend_count") or 0),
            "excluded_count": int(result.get("excluded_count") or len(result.get("excluded") or [])),
            "group_member_excluded": int(result.get("group_member_excluded") or 0),
            "system_excluded": int(result.get("system_excluded") or 0),
            "decrypt": result.get("decrypt") if isinstance(result.get("decrypt"), dict) else {},
            "needs_admin_helper": bool(result.get("needs_admin_helper")),
            "diagnostic": result.get("diagnostic") if isinstance(result.get("diagnostic"), dict) else {},
            "contacts": list(result.get("contacts") or []),
            "excluded": list(result.get("excluded") or []),
        }

    @staticmethod
    def _failure_reason(result: dict[str, object]) -> str:
        reason = str(result.get("reason") or "contact_sync_failed")
        decrypt = result.get("decrypt") if isinstance(result.get("decrypt"), dict) else {}
        if reason == "contact_db_needs_decryption" and isinstance(decrypt, dict):
            decrypt_reason = str(decrypt.get("reason") or "")
            if decrypt_reason == "decrypt_command_failed":
                return "wechat_db_key_extract_failed"
            if decrypt_reason:
                return decrypt_reason
        return reason

    @staticmethod
    def _human_reason(reason: str) -> str:
        labels = {
            "wechat_login_timeout": "没有等到微信登录成功，请重新点击同步并完成登录",
            "contact_db_needs_decryption": "联系人库还没有解密成功",
            "wechat_db_key_extract_failed": "需要管理员确认后读取本机微信通讯录。请在弹窗里点“是”，软件会继续同步。",
            "wechat_local_account_not_found": "没有发现本机微信账号目录",
            "decrypt_tool_not_found": "缺少微信数据库解密工具",
            "sync_cancelled": "同步已取消",
        }
        return labels.get(reason, reason)
