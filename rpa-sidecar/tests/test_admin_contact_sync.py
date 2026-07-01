from __future__ import annotations

from app.services.admin_contact_sync import public_admin_sync_result


def test_public_admin_sync_result_drops_contact_rows_and_keeps_summary():
    result = public_admin_sync_result(
        {
            "success": True,
            "account_id": "wxid_new",
            "account_dir": "wxid_new_abcd",
            "friend_count": 2,
            "excluded_count": 3,
            "group_member_excluded": 1,
            "system_excluded": 2,
            "filter_version": "wechat4_friend_only_v1",
            "contacts": [{"wxid": "wxid_alice"}],
            "excluded": [{"wxid": "filehelper"}],
            "decrypt": {
                "success": True,
                "returncode": 0,
                "reason": "ok",
                "summary": "结果: 17/17 salts 找到密钥",
            },
        }
    )

    assert result["success"] is True
    assert result["account_id"] == "wxid_new"
    assert result["friend_count"] == 2
    assert "contacts" not in result
    assert "excluded" not in result
    assert result["decrypt"]["reason"] == "ok"
