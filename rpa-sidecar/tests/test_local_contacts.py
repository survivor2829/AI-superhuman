import sqlite3
from pathlib import Path

from app.services.local_contacts import WechatLocalContactExtractor


def _create_key_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute(
        "create table LoginKeyInfoTable (user_name_md5 text, key_md5 text, key_info_md5 text, key_info_data blob)"
    )
    con.execute("insert into LoginKeyInfoTable values (?, ?, ?, ?)", ("u", "", "k", b"local-test"))
    con.commit()
    con.close()


def _create_contact_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute(
        """
        create table contact (
            id integer primary key,
            username text,
            local_type integer,
            alias text,
            flag integer,
            delete_flag integer,
            verify_flag integer,
            remark text,
            nick_name text,
            is_in_chat_room integer
        )
        """
    )
    con.execute("create table chatroom_member (room_id integer, member_id integer)")
    con.executemany(
        """
        insert into contact (
            username, local_type, alias, flag, delete_flag, verify_flag, remark, nick_name, is_in_chat_room
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("wxid_alice", 1, "alice_alias", 3, 0, 0, "Alice Remark", "Alice Nick", 0),
            ("wxid_bob", 5, "", 1, 0, 0, "", "Bob Nick", 0),
            ("wxid_owner", 1, "", 1, 0, 0, "", "Owner Self", 0),
            ("wxid_group_cache", 3, "", 4, 0, 0, "", "Group Member Cache", 0),
            ("wxid_deleted", 1, "", 3, 1, 0, "", "Deleted Friend", 0),
            ("filehelper", 1, "", 3, 0, 0, "", "File Transfer", 0),
            ("gh_public", 1, "", 3, 0, 0, "", "Official", 0),
            ("123@chatroom", 1, "", 3, 0, 0, "", "Group", 0),
            ("聊天记录", 1, "", 3, 0, 0, "", "聊天记录", 0),
        ],
    )
    con.execute("insert into chatroom_member values (?, ?)", (999, 3))
    con.commit()
    con.close()


def test_discovers_local_wechat_accounts_from_xwechat_files(tmp_path):
    root = tmp_path / "xwechat_files"
    _create_key_db(root / "all_users" / "login" / "wxid_owner" / "key_info.db")
    _create_contact_db(root / "wxid_owner_abcd" / "db_storage" / "contact" / "contact.db")

    extractor = WechatLocalContactExtractor(root=root)

    accounts = extractor.list_accounts()

    assert len(accounts) == 1
    assert accounts[0]["account_id"] == "wxid_owner"
    assert accounts[0]["account_dir"] == "wxid_owner_abcd"
    assert accounts[0]["contact_db_found"] is True
    assert accounts[0]["key_info_db_found"] is True
    assert accounts[0]["contact_db_encrypted"] is False


def test_sync_contacts_reads_contact_db_and_excludes_non_contacts(tmp_path):
    root = tmp_path / "xwechat_files"
    _create_key_db(root / "all_users" / "login" / "wxid_owner" / "key_info.db")
    _create_contact_db(root / "wxid_owner_abcd" / "db_storage" / "contact" / "contact.db")

    extractor = WechatLocalContactExtractor(root=root)

    result = extractor.sync_contacts(account_id="auto", auto_decrypt=False)

    assert result["success"] is True
    assert result["mode"] == "local_db_full"
    assert result["account_id"] == "wxid_owner"
    assert [contact["wxid"] for contact in result["contacts"]] == ["wxid_alice", "wxid_bob"]
    assert result["friend_count"] == 2
    assert result["filter_version"] == "wechat4_friend_only_v1"
    assert result["group_member_excluded"] == 1
    assert result["contacts"][0]["remark"] == "Alice Remark"
    assert result["contacts"][0]["alias"] == "alice_alias"
    assert result["contacts"][0]["local_type"] == 1
    assert result["contacts"][0]["contact_flag"] == 3
    assert all(contact["source"] == "wechat_local_contact_db" for contact in result["contacts"])
    excluded = {item["wxid"]: item["reason"] for item in result["excluded"]}
    assert excluded["wxid_owner"] == "self_account"
    assert excluded["wxid_group_cache"] == "group_member_cache"
    assert excluded["wxid_deleted"] == "deleted_contact"
    assert {item["wxid"] for item in result["excluded"]} >= {"filehelper", "gh_public", "123@chatroom", "聊天记录"}
