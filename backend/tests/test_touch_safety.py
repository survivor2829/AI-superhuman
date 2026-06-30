from app.models.schemas import AutomationAction, TaskStatus
from app.services.llm import AIReplyDraft
from app.services.message_cleaner import clean_outbound_message
from app.services.prompt_loader import HandoffRules, ImportedPrompt
from app.services.store import AgentStore


class FakeLLM:
    provider = "fake"

    def draft_reply(self, *, system_prompt: str, knowledge_base: str, message: str) -> AIReplyDraft:
        return AIReplyDraft(reply_text="您好，方便了解下您的清洁设备需求吗？", intent_label="touch", handoff_required=False)


def _save_test_profile(store: AgentStore) -> None:
    store.save_ai_profile(
        name="test",
        imported=ImportedPrompt(
            source_path="test.docx",
            system_prompt="你是销售顾问。",
            sales_flow="短句沟通。",
            constraints="不要长段落。",
            handoff_rules=HandoffRules(raw_text="报价转人工"),
            knowledge_base=[],
        ),
    )


def test_contact_eligibility_excludes_system_contacts_and_requires_confirmation(tmp_path):
    store = AgentStore(f"sqlite:///{tmp_path / 'agent.db'}")
    store.create_schema()

    system_contact = store.upsert_contact(account_id="wxid_test_001", wxid="文件传输助手", nickname="文件传输助手")
    customer = store.upsert_contact(account_id="wxid_test_001", wxid="A测试客户", nickname="A测试客户")

    assert system_contact.eligible_for_touch is False
    assert system_contact.eligibility_reason == "system_contact"
    assert customer.eligible_for_touch is True
    assert customer.confirmed_for_touch is False

    store.set_contact_touch_confirmation(customer.id, confirmed=True)
    confirmed_contacts = store.list_contacts(confirmed_for_touch=True)

    assert [contact.nickname for contact in confirmed_contacts] == ["A测试客户"]
    assert confirmed_contacts[0].confirmed_for_touch is True


def test_schema_migration_reclassifies_existing_contacts(tmp_path):
    import sqlite3

    db_path = tmp_path / "agent.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        create table contacts (
            id text primary key,
            account_id text,
            wxid text,
            nickname text,
            remark text,
            tags_json text,
            source text,
            created_at timestamp
        )
        """
    )
    connection.execute(
        "insert into contacts values (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        ("contact_1", "wxid_test_001", "文件传输助手", "文件传输助手", "", "[]", "sidecar"),
    )
    connection.commit()
    connection.close()

    store = AgentStore(f"sqlite:///{db_path}")
    store.create_schema()

    contact = store.list_contacts()[0]

    assert contact.eligible_for_touch is False
    assert contact.eligibility_reason == "system_contact"
    assert contact.confirmed_for_touch is False


def test_blocked_sidecar_send_marks_task_blocked_and_keeps_contact_untouched(monkeypatch, tmp_path):
    import app.main as main

    store = AgentStore(f"sqlite:///{tmp_path / 'agent.db'}")
    store.create_schema()
    monkeypatch.setattr(main, "store", store)

    def fake_sidecar_post(path: str, payload: dict) -> dict:
        return {
            "success": False,
            "verification_status": "blocked",
            "message": "blocked_wrong_search_surface",
            "failure_reason": "搜索结果进入搜一搜，未确认聊天会话",
            "evidence": {"failure": r"C:\evidence\failure.png"},
        }

    monkeypatch.setattr(main, "_sidecar_post", fake_sidecar_post)

    response = main.send_message(
        AutomationAction(
            action_type="message.send",
            account_id="wxid_test_001",
            target_id="A测试客户",
            payload={"content": "这是测试说明：您好"},
        )
    )

    assert response["task"]["status"] == TaskStatus.blocked.value
    assert response["sidecar"]["verification_status"] == "blocked"
    assert store.list_tasks()[0].status == TaskStatus.blocked
    assert store.list_task_events()[0].message == "blocked_wrong_search_surface"


def test_clean_outbound_message_keeps_single_prefix_and_removes_duplicate_punctuation():
    cleaned = clean_outbound_message(
        "这是测试说明：：  ，，您好，，  是玺联惠的创客合伙人。。",
        prefix="这是测试说明：",
    )

    assert cleaned == "这是测试说明：您好，是玺联惠的创客合伙人。"


def test_touch_run_sends_remark_nickname_alias_search_terms(monkeypatch, tmp_path):
    import app.main as main

    store = AgentStore(f"sqlite:///{tmp_path / 'agent.db'}")
    store.create_schema()
    _save_test_profile(store)
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "llm", FakeLLM())
    store.upsert_synced_contacts(
        account_id="wxid_local",
        contacts=[
            {
                "wxid": "wxid_alice",
                "nickname": "Alice昵称",
                "remark": "Alice备注",
                "alias": "alice_alias",
                "source": "wechat_local_contact_db",
                "local_type": 1,
                "contact_flag": 1,
                "delete_flag": 0,
            }
        ],
        auto_confirm=True,
    )
    captured: list[dict] = []

    def fake_sidecar_post(path: str, payload: dict) -> dict:
        captured.append(payload)
        return {"success": False, "verification_status": "blocked", "message": "blocked_target_not_verified", "evidence": {}}

    monkeypatch.setattr(main, "_sidecar_get", lambda path: {"mode": "non_screen", "verified": True, "message": "verified"})
    monkeypatch.setattr(main, "_sidecar_post", fake_sidecar_post)

    main.run_touch_plan("plan_search_terms", main.TouchRunRequest(limit=1, direct_send=True))

    assert captured[0]["payload"]["search_terms"] == ["Alice备注", "Alice昵称", "alice_alias", "wxid_alice"]


def test_touch_run_stops_batch_after_wechat_window_infrastructure_failure(monkeypatch, tmp_path):
    import app.main as main

    store = AgentStore(f"sqlite:///{tmp_path / 'agent.db'}")
    store.create_schema()
    _save_test_profile(store)
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "llm", FakeLLM())
    store.upsert_synced_contacts(
        account_id="wxid_local",
        contacts=[
            {"wxid": "wxid_1", "nickname": "客户1", "source": "wechat_local_contact_db", "local_type": 1, "contact_flag": 1, "delete_flag": 0},
            {"wxid": "wxid_2", "nickname": "客户2", "source": "wechat_local_contact_db", "local_type": 1, "contact_flag": 1, "delete_flag": 0},
        ],
        auto_confirm=True,
    )
    calls: list[dict] = []

    def fake_sidecar_post(path: str, payload: dict) -> dict:
        calls.append(payload)
        return {
            "success": False,
            "verification_status": "blocked",
            "message": "blocked_window_not_foreground",
            "failure_reason": "foreground_not_changed",
            "evidence": {},
        }

    monkeypatch.setattr(main, "_sidecar_get", lambda path: {"mode": "non_screen", "verified": True, "message": "verified"})
    monkeypatch.setattr(main, "_sidecar_post", fake_sidecar_post)

    response = main.run_touch_plan("plan_stop", main.TouchRunRequest(limit=2, direct_send=True))

    assert len(calls) == 1
    assert response["ran"] == 1
    assert response["results"][0]["status"] == "blocked"


def test_backend_exposes_send_driver_probe(monkeypatch):
    import app.main as main

    def fake_sidecar_get(path: str) -> dict:
        assert path == "/send/driver/probe"
        return {
            "mode": "non_screen",
            "verified": False,
            "message": "非屏幕发送通道未验证，未执行发送",
            "capabilities": ["contact_sync", "touch_preview", "audit_log"],
        }

    monkeypatch.setattr(main, "_sidecar_get", fake_sidecar_get)

    result = main.send_driver_probe()

    assert result["mode"] == "non_screen"
    assert result["verified"] is False
    assert result["message"] == "非屏幕发送通道未验证，未执行发送"


def test_touch_run_blocks_before_creating_send_tasks_when_non_screen_driver_unverified(monkeypatch, tmp_path):
    import app.main as main

    store = AgentStore(f"sqlite:///{tmp_path / 'agent.db'}")
    store.create_schema()
    _save_test_profile(store)
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "llm", FakeLLM())
    store.upsert_synced_contacts(
        account_id="wxid_local",
        contacts=[
            {"wxid": "wxid_1", "nickname": "客户1", "source": "wechat_local_contact_db", "local_type": 1, "contact_flag": 1, "delete_flag": 0},
            {"wxid": "wxid_2", "nickname": "客户2", "source": "wechat_local_contact_db", "local_type": 1, "contact_flag": 1, "delete_flag": 0},
        ],
        auto_confirm=True,
    )

    sidecar_calls: list[str] = []

    def fake_sidecar_get(path: str) -> dict:
        assert path == "/send/driver/probe"
        return {"mode": "non_screen", "verified": False, "message": "非屏幕发送通道未验证，未执行发送"}

    def fake_sidecar_post(path: str, payload: dict) -> dict:
        sidecar_calls.append(path)
        return {"success": True, "verification_status": "verified", "message": "should_not_send", "evidence": {}}

    monkeypatch.setattr(main, "_sidecar_get", fake_sidecar_get)
    monkeypatch.setattr(main, "_sidecar_post", fake_sidecar_post)

    response = main.run_touch_plan("plan_blocked", main.TouchRunRequest(limit=2, direct_send=True))

    assert response["ran"] == 0
    assert response["message"] == "非屏幕发送通道未验证，未执行发送"
    assert sidecar_calls == []
    assert store.list_tasks() == []
