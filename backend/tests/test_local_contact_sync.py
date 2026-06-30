from app.services.store import AgentStore


def test_local_db_contacts_are_auto_confirmed_and_ui_artifacts_are_excluded(tmp_path):
    store = AgentStore(f"sqlite:///{tmp_path / 'agent.db'}")
    store.create_schema()

    store.upsert_contact(account_id="wxid_local", wxid="聊天记录", nickname="聊天记录", source="visible_text")

    saved = store.upsert_synced_contacts(
        account_id="wxid_local",
        contacts=[
            {
                "wxid": "wxid_alice",
                "nickname": "Alice Nick",
                "remark": "Alice Remark",
                "alias": "alice_alias",
                "source": "wechat_local_contact_db",
                "wechat_account_dir": "wxid_local_abcd",
                "raw_wxid": "wxid_alice",
                "sync_batch_id": "sync_001",
                "local_type": 1,
                "contact_flag": 3,
                "delete_flag": 0,
                "verify_flag": 0,
                "is_chatroom_member": False,
            }
        ],
        auto_confirm=True,
        excluded=[
            {"wxid": "聊天记录", "reason": "non_contact_ui_artifact"},
            {"wxid": "wxid_group_cache", "reason": "group_member_cache", "local_type": 3, "contact_flag": 4},
        ],
    )

    assert saved[0].source == "wechat_local_contact_db"
    assert saved[0].eligible_for_touch is True
    assert saved[0].confirmed_for_touch is True
    assert saved[0].remark == "Alice Remark"
    assert saved[0].local_type == 1
    assert saved[0].contact_flag == 3

    contacts = {contact.wxid: contact for contact in store.list_contacts(limit=10)}
    assert contacts["聊天记录"].eligible_for_touch is False
    assert contacts["聊天记录"].eligibility_reason == "non_contact_ui_artifact"
    assert contacts["聊天记录"].confirmed_for_touch is False
    assert contacts["wxid_group_cache"].eligible_for_touch is False
    assert contacts["wxid_group_cache"].eligibility_reason == "group_member_cache"
    assert contacts["wxid_group_cache"].contact_flag == 4


def test_touchable_contacts_only_include_local_db_confirmed_contacts(tmp_path):
    store = AgentStore(f"sqlite:///{tmp_path / 'agent.db'}")
    store.create_schema()

    manual = store.upsert_contact(account_id="wxid_local", wxid="manual_contact", nickname="Manual", source="sidecar")
    store.set_contact_touch_confirmation(manual.id, confirmed=True)
    store.upsert_synced_contacts(
        account_id="wxid_local",
        contacts=[
            {"wxid": "wxid_alice", "nickname": "Alice", "source": "wechat_local_contact_db"},
        ],
        auto_confirm=True,
    )

    confirmed = store.list_contacts(
        eligible_for_touch=True,
        confirmed_for_touch=True,
        source="wechat_local_contact_db",
    )

    assert [contact.wxid for contact in confirmed] == ["wxid_alice"]


def test_removed_local_contact_is_not_touchable(tmp_path):
    store = AgentStore(f"sqlite:///{tmp_path / 'agent.db'}")
    store.create_schema()
    saved = store.upsert_synced_contacts(
        account_id="wxid_local",
        contacts=[
            {"wxid": "wxid_alice", "nickname": "Alice", "source": "wechat_local_contact_db", "local_type": 1, "contact_flag": 3},
            {"wxid": "wxid_bob", "nickname": "Bob", "source": "wechat_local_contact_db", "local_type": 5, "contact_flag": 1},
        ],
        auto_confirm=True,
    )

    store.exclude_contact_from_touch(saved[0].id)

    confirmed = store.list_contacts(
        eligible_for_touch=True,
        confirmed_for_touch=True,
        source="wechat_local_contact_db",
    )

    assert [contact.wxid for contact in confirmed] == ["wxid_bob"]
