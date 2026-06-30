from __future__ import annotations

from datetime import UTC, datetime

from app.services.guardrails import LocalAction, LocalActionResult
from app.services.weixin_driver import RealAutomationDriver


class DryRunAutomationDriver:
    def __init__(self, *, account_id: str) -> None:
        self.account_id = account_id
        self.stopped = False

    def status(self) -> dict[str, str]:
        return {
            "mode": "dry_run",
            "account_id": self.account_id,
            "wechat_status": "simulated_ready",
        }

    def execute(self, action: LocalAction) -> LocalActionResult:
        if self.stopped:
            return LocalActionResult(success=False, message="driver stopped", evidence={"action_type": action.action_type})
        return LocalActionResult(
            success=True,
            message=f"{action.action_type} accepted in dry-run mode",
            dry_run=True,
            verification_status="verified",
            matched_target=action.target_id,
            evidence={
                "account_id": self.account_id,
                "target_id": action.target_id,
                "action_type": action.action_type,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    def stop(self) -> LocalActionResult:
        self.stopped = True
        return LocalActionResult(success=True, message="stop signal accepted", dry_run=True)


class WeixinAutomationDriver:
    def __init__(self, real_driver: RealAutomationDriver, *, dry_run: bool) -> None:
        self.real_driver = real_driver
        self.dry_run = dry_run
        self.dry_driver = DryRunAutomationDriver(account_id="wxid_test_001")

    def status(self) -> dict[str, object]:
        if self.dry_run:
            return self.dry_driver.status()
        return self.real_driver.status()

    def probe(self) -> dict[str, object]:
        status = self.real_driver.probe_driver.probe()
        return {
            "detected": status.detected,
            "process_name": status.process_name,
            "window_title": status.window_title,
            "pid": status.pid,
            "path": status.path,
            "reason": status.reason,
            "hwnd": status.hwnd,
            "class_name": status.class_name,
            "rect": status.rect,
            "foreground_match": status.foreground_match,
            "activation_status": status.activation_status,
        }

    def local_accounts(self) -> list[dict[str, object]]:
        if self.dry_run:
            return []
        return self.real_driver.local_accounts()

    def sync_contacts(self, *, account_id: str = "auto", auto_decrypt: bool = True) -> dict[str, object]:
        if self.dry_run:
            return {
                "success": True,
                "dry_run": True,
                "mode": "local_db_full",
                "account_id": account_id,
                "contacts": [],
                "excluded": [],
                "counts": {"contacts": 0, "excluded": 0},
            }
        return self.real_driver.sync_contacts(account_id=account_id, auto_decrypt=auto_decrypt)

    def execute(self, action: LocalAction) -> LocalActionResult:
        if self.dry_run:
            return self.dry_driver.execute(action)
        if action.action_type == "message.send":
            return self.real_driver.send_message(
                target_id=action.target_id,
                content=str(action.payload.get("content") or ""),
                search_terms=list(action.payload.get("search_terms") or []),
            )
        if action.action_type in {"moments.like", "moments.comment"}:
            return self.real_driver.like_moment(
                target_id=action.target_id,
                comment=str(action.payload.get("comment") or ""),
            )
        return LocalActionResult(success=False, message=f"unsupported_action:{action.action_type}", dry_run=False)

    def stop(self) -> LocalActionResult:
        if self.dry_run:
            return self.dry_driver.stop()
        return self.real_driver.stop()
