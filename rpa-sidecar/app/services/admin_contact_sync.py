from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.local_contacts import WechatLocalContactExtractor


def public_admin_sync_result(result: dict[str, Any]) -> dict[str, Any]:
    """Return a UI-safe summary; never expose contact rows or extracted keys."""

    decrypt = result.get("decrypt") if isinstance(result.get("decrypt"), dict) else {}
    diagnostic = result.get("diagnostic") if isinstance(result.get("diagnostic"), dict) else {}
    return {
        "success": bool(result.get("success")),
        "reason": str(result.get("reason") or ("ok" if result.get("success") else "contact_sync_failed")),
        "account_id": str(result.get("account_id") or ""),
        "account_dir": str(result.get("account_dir") or ""),
        "friend_count": int(result.get("friend_count") or 0),
        "excluded_count": int(result.get("excluded_count") or 0),
        "group_member_excluded": int(result.get("group_member_excluded") or 0),
        "system_excluded": int(result.get("system_excluded") or 0),
        "filter_version": str(result.get("filter_version") or "wechat4_friend_only_v1"),
        "needs_admin_helper": bool(result.get("needs_admin_helper")),
        "diagnostic": diagnostic,
        "decrypt": {
            "success": bool(decrypt.get("success")),
            "returncode": decrypt.get("returncode"),
            "reason": str(decrypt.get("reason") or ""),
            "summary": str(decrypt.get("summary") or ""),
        },
        "completed_at": datetime.now(UTC).isoformat(),
    }


def run_admin_contact_sync(*, result_path: Path) -> dict[str, Any]:
    extractor = WechatLocalContactExtractor()
    result = extractor.sync_contacts(account_id="auto", auto_decrypt=True)
    public_result = public_admin_sync_result(result)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(public_result, ensure_ascii=False, indent=2), encoding="utf-8")
    return public_result
