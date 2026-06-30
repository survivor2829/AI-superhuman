from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class InboundWechatMessage:
    message_key: str
    wxid: str
    content: str
    created_at: datetime


class WechatSessionMessageScanner:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    def scan_unread_private_text(self, *, limit: int = 20) -> list[InboundWechatMessage]:
        messages: list[InboundWechatMessage] = []
        for db_path in self._session_databases():
            messages.extend(self._scan_session_db(db_path=db_path, limit=limit - len(messages)))
            if len(messages) >= limit:
                break
        return messages[:limit]

    def _session_databases(self) -> list[Path]:
        return sorted((self.root_dir / "wechat_decrypted").glob("*/session/session.db"))

    def _scan_session_db(self, *, db_path: Path, limit: int) -> list[InboundWechatMessage]:
        if limit <= 0 or not db_path.exists():
            return []
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """
                select username, unread_count, summary, last_timestamp, last_msg_type
                from SessionTable
                where unread_count > 0
                order by last_timestamp desc
                limit ?
                """,
                (limit * 3,),
            ).fetchall()
        finally:
            connection.close()
        messages: list[InboundWechatMessage] = []
        for row in rows:
            wxid = str(row["username"] or "").strip()
            summary = str(row["summary"] or "").strip()
            if not wxid or not summary or not self._is_private_text(wxid=wxid, last_msg_type=row["last_msg_type"]):
                continue
            created_at = datetime.fromtimestamp(int(row["last_timestamp"] or 0), tz=UTC)
            key = f"{wxid}:{int(row['last_timestamp'] or 0)}:{hash(summary)}"
            messages.append(InboundWechatMessage(message_key=key, wxid=wxid, content=summary, created_at=created_at))
            if len(messages) >= limit:
                break
        return messages

    @staticmethod
    def _is_private_text(*, wxid: str, last_msg_type: object) -> bool:
        if wxid.endswith("@chatroom") or wxid.startswith("gh_") or wxid in {"filehelper", "weixin", "fmessage"}:
            return False
        try:
            message_type = int(last_msg_type)
        except (TypeError, ValueError):
            return False
        return message_type == 1
