from __future__ import annotations

from app.services.sync_wizard import SyncWizard


def test_sync_wizard_restarts_wechat_waits_for_login_and_syncs_contacts():
    events: list[str] = []
    logged_in = {"value": False}

    def restart_wechat() -> dict[str, object]:
        events.append("restart")
        logged_in["value"] = True
        return {"success": True, "message": "wechat_restarted"}

    def login_probe() -> dict[str, object]:
        events.append("probe")
        return {"detected": logged_in["value"]}

    def sync_contacts(account_id: str = "auto", auto_decrypt: bool = True) -> dict[str, object]:
        events.append(f"sync:{account_id}:{auto_decrypt}")
        return {
            "success": True,
            "account_id": "wxid_new",
            "friend_count": 2,
            "excluded_count": 1,
            "contacts": [{"wxid": "wxid_a"}, {"wxid": "wxid_b"}],
            "excluded": [{"wxid": "filehelper", "reason": "system_contact"}],
        }

    wizard = SyncWizard(
        restart_wechat=restart_wechat,
        login_probe=login_probe,
        sync_contacts=sync_contacts,
        sleep=lambda _seconds: None,
    )

    start = wizard.start(restart_wechat=True, timeout_seconds=3, run_async=False)
    status = wizard.status()

    assert start["stage"] == "completed"
    assert status["stage"] == "completed"
    assert status["account_id"] == "wxid_new"
    assert status["friend_count"] == 2
    assert status["excluded_count"] == 1
    assert events == ["restart", "probe", "sync:auto:True"]


def test_sync_wizard_reports_login_timeout_without_fake_zero_contacts():
    wizard = SyncWizard(
        restart_wechat=lambda: {"success": True},
        login_probe=lambda: {"detected": False},
        sync_contacts=lambda account_id="auto", auto_decrypt=True: {"success": True, "friend_count": 0},
        sleep=lambda _seconds: None,
    )

    status = wizard.start(restart_wechat=True, timeout_seconds=1, run_async=False)

    assert status["stage"] == "failed"
    assert status["error_reason"] == "wechat_login_timeout"
    assert status["friend_count"] == 0
