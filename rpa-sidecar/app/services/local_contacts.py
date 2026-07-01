from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


SQLITE_HEADER = b"SQLite format 3\x00"
ACCOUNT_DIR_RE = re.compile(r"^(wxid_.+)_([0-9a-fA-F]{4})$")


class WechatLocalContactExtractor:
    """Read WeChat 4.x contacts from local database files, never from UI/OCR."""

    def __init__(
        self,
        *,
        root: str | Path | None = None,
        decrypt_tool_dir: str | Path | None = None,
        decrypted_root: str | Path | None = None,
        runtime_dir: str | Path | None = None,
    ) -> None:
        agent_root = Path(__file__).resolve().parents[3]
        self.root = Path(root or os.environ.get("WECHAT_DATA_ROOT") or (Path.home() / "Documents" / "xwechat_files"))
        self.decrypt_tool_dir = Path(
            decrypt_tool_dir
            or os.environ.get("WECHAT_DECRYPT_TOOL_DIR")
            or (agent_root / "tools" / "wechat-decrypt")
        )
        self.decrypted_root = Path(
            decrypted_root
            or os.environ.get("WECHAT_DECRYPTED_ROOT")
            or (agent_root / "wechat_decrypted")
        )
        self.runtime_dir = Path(runtime_dir or (agent_root / ".runtime"))

    def list_accounts(self) -> list[dict[str, Any]]:
        accounts: list[dict[str, Any]] = []
        if not self.root.exists():
            return []

        for account_dir in self.root.iterdir():
            if not account_dir.is_dir():
                continue
            match = ACCOUNT_DIR_RE.match(account_dir.name)
            if not match:
                continue
            account_id = match.group(1)
            db_storage = account_dir / "db_storage"
            contact_db = db_storage / "contact" / "contact.db"
            key_info_db = self.root / "all_users" / "login" / account_id / "key_info.db"
            decrypted_contact_db = self._find_decrypted_contact_db(account_dir)
            accounts.append(
                {
                    "account_id": account_id,
                    "account_dir": account_dir.name,
                    "account_path": str(account_dir),
                    "db_storage_path": str(db_storage),
                    "contact_db_path": str(contact_db),
                    "key_info_db_path": str(key_info_db),
                    "decrypted_contact_db_path": str(decrypted_contact_db) if decrypted_contact_db else "",
                    "contact_db_found": contact_db.exists(),
                    "key_info_db_found": key_info_db.exists(),
                    "contact_db_encrypted": contact_db.exists() and not self._is_sqlite_db(contact_db),
                    "decrypted_contact_db_found": bool(decrypted_contact_db),
                    "last_active_at": self._last_active_at(account_dir),
                }
            )

        accounts.sort(key=lambda item: str(item["last_active_at"] or ""), reverse=True)
        return accounts

    def sync_contacts(self, *, account_id: str = "auto", auto_decrypt: bool = True) -> dict[str, Any]:
        account = self._select_account(account_id)
        if account is None:
            return {
                "success": False,
                "mode": "local_db_full",
                "reason": "wechat_local_account_not_found",
                "contacts": [],
                "excluded": [],
                "accounts": self.list_accounts(),
            }

        db_path = self._readable_contact_db(account)
        decrypt_result: dict[str, Any] | None = None
        if db_path is None and auto_decrypt:
            decrypt_result = self._run_decrypt(account)
            account = self._select_account(str(account["account_id"]))
            db_path = self._readable_contact_db(account) if account else None

        if db_path is None:
            return {
                "success": False,
                "mode": "local_db_full",
                "reason": "contact_db_needs_decryption",
                "contacts": [],
                "excluded": [],
                "account": account,
                "decrypt": self._safe_decrypt_result(decrypt_result),
            }

        try:
            contacts, excluded = self._read_contacts_from_db(db_path, account)
        except Exception as exc:
            return {
                "success": False,
                "mode": "local_db_full",
                "reason": f"contact_db_read_failed:{type(exc).__name__}",
                "contacts": [],
                "excluded": [],
                "account": account,
                "decrypt": self._safe_decrypt_result(decrypt_result),
            }

        sync_batch_id = f"sync_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"
        for item in contacts:
            item["sync_batch_id"] = sync_batch_id
        group_member_excluded = sum(1 for item in excluded if item.get("reason") == "group_member_cache")
        system_excluded = len(excluded) - group_member_excluded
        return {
            "success": True,
            "mode": "local_db_full",
            "filter_version": "wechat4_friend_only_v1",
            "account_id": account["account_id"],
            "account_dir": account["account_dir"],
            "sync_batch_id": sync_batch_id,
            "contacts": contacts,
            "excluded": excluded,
            "friend_count": len(contacts),
            "excluded_count": len(excluded),
            "group_member_excluded": group_member_excluded,
            "system_excluded": system_excluded,
            "counts": {
                "contacts": len(contacts),
                "excluded": len(excluded),
                "friend_count": len(contacts),
                "group_member_excluded": group_member_excluded,
                "system_excluded": system_excluded,
            },
            "decrypt": self._safe_decrypt_result(decrypt_result),
        }

    def _select_account(self, account_id: str) -> dict[str, Any] | None:
        accounts = self.list_accounts()
        if not accounts:
            return None
        if account_id in {"", "auto", None}:  # type: ignore[comparison-overlap]
            return accounts[0]
        for account in accounts:
            if account["account_id"] == account_id or account["account_dir"] == account_id:
                return account
        return None

    def _readable_contact_db(self, account: dict[str, Any] | None) -> Path | None:
        if not account:
            return None
        decrypted = Path(str(account.get("decrypted_contact_db_path") or ""))
        if decrypted.exists() and self._is_sqlite_db(decrypted):
            return decrypted
        raw = Path(str(account.get("contact_db_path") or ""))
        if raw.exists() and self._is_sqlite_db(raw):
            return raw
        return None

    def _run_decrypt(self, account: dict[str, Any]) -> dict[str, Any]:
        if not self.decrypt_tool_dir.exists():
            return {"success": False, "reason": "decrypt_tool_not_found"}

        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.decrypted_root.mkdir(parents=True, exist_ok=True)
        keys_file = self.runtime_dir / f"wechat_keys_{account['account_id']}.json"
        decrypted_dir = self.decrypted_root / str(account["account_dir"])
        config_path = self.decrypt_tool_dir / "config.json"
        config = {
            "db_dir": str(Path(str(account["db_storage_path"]))),
            "keys_file": str(keys_file),
            "decrypted_dir": str(decrypted_dir),
            "decoded_image_dir": str(self.decrypted_root / str(account["account_dir"]) / "decoded_images"),
            "wechat_process": os.environ.get("WECHAT_PROCESS_EXE", "Weixin.exe"),
            "wxwork_db_dir": "",
            "wxwork_keys_file": str(self.runtime_dir / "wxwork_keys.json"),
            "wxwork_decrypted_dir": str(self.decrypted_root / "wxwork"),
            "wxwork_export_dir": str(self.decrypted_root / "wxwork_export"),
            "wxwork_process": "WXWork.exe",
        }
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

        env = os.environ.copy()
        env["WECHAT_DECRYPT_NONINTERACTIVE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        command = [sys.executable, "main.py", "decrypt"]
        attempts = max(1, int(os.environ.get("WECHAT_DECRYPT_ATTEMPTS", "4")))
        retry_delay = max(0.0, float(os.environ.get("WECHAT_DECRYPT_RETRY_DELAY_SECONDS", "5")))
        last_result: dict[str, Any] | None = None
        try:
            for attempt in range(1, attempts + 1):
                completed = subprocess.run(
                    command,
                    cwd=self.decrypt_tool_dir,
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=int(os.environ.get("WECHAT_DECRYPT_TIMEOUT_SECONDS", "180")),
                )
                last_result = {
                    "success": completed.returncode == 0,
                    "returncode": completed.returncode,
                    "reason": "ok" if completed.returncode == 0 else "decrypt_command_failed",
                    "summary": self._decrypt_output_summary(
                        completed.stdout,
                        completed.stderr,
                        attempt=attempt,
                        attempts=attempts,
                    ),
                }
                if completed.returncode == 0:
                    return last_result
                if attempt < attempts and retry_delay:
                    time.sleep(retry_delay)
            return last_result or {"success": False, "reason": "decrypt_command_failed"}
        except Exception as exc:
            return {"success": False, "reason": f"decrypt_command_error:{type(exc).__name__}"}
        finally:
            try:
                keys_file.unlink(missing_ok=True)
            except Exception:
                pass

    def _read_contacts_from_db(self, db_path: Path, account: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            tables = {row[0] for row in con.execute("select name from sqlite_master where type='table'")}
            if "contact" not in tables:
                raise RuntimeError("contact_table_not_found")
            cols = {row[1] for row in con.execute("pragma table_info(contact)").fetchall()}
            id_col = self._first_existing(cols, ["id", "rowid"])
            username_col = self._first_existing(cols, ["username", "user_name", "wxid"])
            alias_col = self._first_existing(cols, ["alias"])
            remark_col = self._first_existing(cols, ["remark", "con_remark"])
            nick_col = self._first_existing(cols, ["nick_name", "nickname", "nickname_pinyin"])
            local_type_col = self._first_existing(cols, ["local_type"])
            flag_col = self._first_existing(cols, ["flag"])
            delete_flag_col = self._first_existing(cols, ["delete_flag"])
            verify_flag_col = self._first_existing(cols, ["verify_flag"])
            in_chat_room_col = self._first_existing(cols, ["is_in_chat_room"])
            if not username_col:
                raise RuntimeError("contact_username_column_not_found")
            select_cols = [
                id_col or "NULL",
                username_col,
                alias_col or "''",
                remark_col or "''",
                nick_col or "''",
                local_type_col or "NULL",
                flag_col or "NULL",
                delete_flag_col or "0",
                verify_flag_col or "0",
                in_chat_room_col or "0",
            ]
            query = f"select {', '.join(select_cols)} from contact"
            chatroom_member_ids: set[int] = set()
            if "chatroom_member" in tables and id_col:
                try:
                    chatroom_member_ids = {int(row[0]) for row in con.execute("select member_id from chatroom_member").fetchall() if row[0] is not None}
                except Exception:
                    chatroom_member_ids = set()
            contacts: list[dict[str, Any]] = []
            excluded: list[dict[str, Any]] = []
            seen: set[str] = set()
            for contact_id, username, alias, remark, nick_name, local_type, flag, delete_flag, verify_flag, is_in_chat_room in con.execute(query).fetchall():
                wxid = str(username or "").strip()
                if not wxid or wxid in seen:
                    continue
                seen.add(wxid)
                local_type_int = self._to_int(local_type)
                contact_flag = self._to_int(flag)
                delete_flag_int = self._to_int(delete_flag)
                verify_flag_int = self._to_int(verify_flag)
                is_chatroom_member = bool(self._to_int(is_in_chat_room)) or (
                    contact_id is not None and int(contact_id) in chatroom_member_ids
                )
                reason = self._exclude_reason(
                    wxid=wxid,
                    alias=str(alias or ""),
                    remark=str(remark or ""),
                    nickname=str(nick_name or ""),
                    local_type=local_type_int,
                    contact_flag=contact_flag,
                    delete_flag=delete_flag_int,
                    owner_wxid=str(account["account_id"]),
                )
                if reason:
                    excluded.append(
                        {
                            "wxid": wxid,
                            "nickname": str(nick_name or remark or alias or wxid),
                            "reason": reason,
                            "source": "wechat_local_contact_db",
                            "wechat_account_dir": str(account["account_dir"]),
                            "raw_wxid": wxid,
                            "local_type": local_type_int,
                            "contact_flag": contact_flag,
                            "delete_flag": delete_flag_int,
                            "verify_flag": verify_flag_int,
                            "is_chatroom_member": is_chatroom_member,
                        }
                    )
                    continue
                contacts.append(
                    {
                        "wxid": wxid,
                        "raw_wxid": wxid,
                        "alias": str(alias or ""),
                        "remark": str(remark or ""),
                        "nickname": str(nick_name or remark or alias or wxid),
                        "source": "wechat_local_contact_db",
                        "wechat_account_dir": str(account["account_dir"]),
                        "local_type": local_type_int,
                        "contact_flag": contact_flag,
                        "delete_flag": delete_flag_int,
                        "verify_flag": verify_flag_int,
                        "is_chatroom_member": is_chatroom_member,
                    }
                )
            return contacts, excluded
        finally:
            con.close()

    @staticmethod
    def _first_existing(columns: set[str], names: list[str]) -> str | None:
        for name in names:
            if name in columns:
                return name
        return None

    @staticmethod
    def _exclude_reason(
        *,
        wxid: str,
        alias: str,
        remark: str,
        nickname: str,
        local_type: int | None,
        contact_flag: int | None,
        delete_flag: int | None,
        owner_wxid: str = "",
    ) -> str:
        value = f"{wxid} {alias} {remark} {nickname}".strip()
        ui_artifacts = {"聊天记录", "从手机导入聊天记录", "语音通话", "聊天信息"}
        if owner_wxid and wxid == owner_wxid:
            return "self_account"
        if wxid in ui_artifacts or nickname in ui_artifacts or remark in ui_artifacts:
            return "non_contact_ui_artifact"
        if wxid in {"filehelper", "weixin", "fmessage", "medianote", "floatbottle", "notifymessage"}:
            return "system_contact"
        if wxid.endswith("@chatroom"):
            return "group_chat"
        if wxid.startswith("gh_") or "公众号" in value or "订阅号" in value or "服务通知" in value:
            return "official_account"
        if delete_flag not in {None, 0}:
            return "deleted_contact"
        if contact_flag == 4:
            return "group_member_cache"
        if local_type is not None and local_type not in {1, 5}:
            return "non_friend_contact"
        if contact_flag is not None and contact_flag not in {1, 3}:
            return "non_friend_contact"
        return ""

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _find_decrypted_contact_db(self, account_dir: Path) -> Path | None:
        candidates: list[Path] = []
        env_dir = os.environ.get("WECHAT_DECRYPTED_DIR")
        if env_dir:
            candidates.append(Path(env_dir) / "contact" / "contact.db")
        candidates.append(self.decrypted_root / account_dir.name / "contact" / "contact.db")
        candidates.extend(self._tool_config_decrypted_candidates(account_dir))
        for candidate in candidates:
            if candidate.exists() and self._is_sqlite_db(candidate):
                return candidate
        return None

    def _tool_config_decrypted_candidates(self, account_dir: Path) -> list[Path]:
        config_path = self.decrypt_tool_dir / "config.json"
        if not config_path.exists():
            return []
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        db_dir = Path(str(config.get("db_dir") or ""))
        try:
            if db_dir.resolve() != (account_dir / "db_storage").resolve():
                return []
        except Exception:
            return []
        decrypted = Path(str(config.get("decrypted_dir") or ""))
        if not decrypted.is_absolute():
            decrypted = self.decrypt_tool_dir / decrypted
        return [decrypted / "contact" / "contact.db"]

    @staticmethod
    def _is_sqlite_db(path: Path) -> bool:
        try:
            with path.open("rb") as handle:
                return handle.read(len(SQLITE_HEADER)) == SQLITE_HEADER
        except OSError:
            return False

    @staticmethod
    def _last_active_at(account_dir: Path) -> str:
        candidates = [
            account_dir / "db_storage" / "contact" / "contact.db",
            account_dir / "db_storage" / "session" / "session.db",
            account_dir / "db_storage" / "message",
            account_dir,
        ]
        mtimes = []
        for path in candidates:
            try:
                mtimes.append(path.stat().st_mtime)
            except OSError:
                continue
        ts = max(mtimes) if mtimes else 0
        return datetime.fromtimestamp(ts, UTC).isoformat() if ts else ""

    @staticmethod
    def _safe_decrypt_result(result: dict[str, Any] | None) -> dict[str, Any] | None:
        if not result:
            return None
        return {
            "success": bool(result.get("success")),
            "returncode": result.get("returncode"),
            "reason": result.get("reason"),
            "summary": result.get("summary") or "",
        }

    @staticmethod
    def _decrypt_output_summary(stdout: str, stderr: str, *, attempt: int | None = None, attempts: int | None = None) -> str:
        text = f"{stdout}\n{stderr}"
        patterns = [
            r"结果:\s*\d+/\d+\s*salts\s*找到密钥",
            r"密钥提取失败:\s*[^\r\n]+",
            r"未能提取到任何密钥",
            r"未能从任何微信进程中提取到密钥",
            r"无法打开进程\s*PID=\d+",
        ]
        matches: list[str] = []
        if attempt is not None and attempts is not None:
            matches.append(f"attempt {attempt}/{attempts}")
        for pattern in patterns:
            for match in re.findall(pattern, text):
                if match not in matches:
                    matches.append(match)
        return "；".join(matches[:4])
