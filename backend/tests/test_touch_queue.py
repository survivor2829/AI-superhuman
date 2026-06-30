from datetime import UTC, datetime, timedelta

from app.models.schemas import AutomationAction
from app.services.llm import AIReplyDraft
from app.services.prompt_loader import HandoffRules, ImportedPrompt
from app.services.store import AgentStore


class FakeLLM:
    provider = "fake"

    def draft_reply(self, *, system_prompt: str, knowledge_base: str, message: str) -> AIReplyDraft:
        return AIReplyDraft(reply_text="\u60a8\u597d\uff0c\u8fd9\u662f\u961f\u5217\u89e6\u8fbe\u6d4b\u8bd5\u3002", intent_label="touch", handoff_required=False)


def _save_profile(store: AgentStore) -> None:
    store.save_ai_profile(
        name="test",
        imported=ImportedPrompt(
            source_path="test.docx",
            system_prompt="\u4f60\u662f\u9500\u552e\u987e\u95ee\u3002",
            sales_flow="\u77ed\u53e5\u6c9f\u901a\u3002",
            constraints="\u4e0d\u8981\u957f\u6bb5\u843d\u3002",
            handoff_rules=HandoffRules(raw_text="\u62a5\u4ef7\u8f6c\u4eba\u5de5"),
            knowledge_base=[],
        ),
    )


def test_plan_target_queue_persists_status_and_stats(tmp_path):
    store = AgentStore(f"sqlite:///{tmp_path / 'agent.db'}")
    store.create_schema()
    c1 = store.upsert_contact(account_id="wxid_local", wxid="wxid_1", nickname="\u5ba2\u62371", source="wechat_local_contact_db")
    c2 = store.upsert_contact(account_id="wxid_local", wxid="wxid_2", nickname="\u5ba2\u62372", source="wechat_local_contact_db")

    store.upsert_plan_target(plan_id="plan_1", contact_id=c1.id, status="pending")
    store.upsert_plan_target(plan_id="plan_1", contact_id=c2.id, status="skipped", skip_reason="touch_interval_active")

    stats = store.plan_target_stats("plan_1")
    rows = store.list_plan_targets(plan_id="plan_1")

    assert stats == {"pending": 1, "skipped": 1}
    assert [row["status"] for row in rows] == ["pending", "skipped"]


def test_build_touch_queue_skips_recently_touched_contacts(monkeypatch, tmp_path):
    import app.main as main

    store = AgentStore(f"sqlite:///{tmp_path / 'agent.db'}")
    store.create_schema()
    monkeypatch.setattr(main, "store", store)
    c1 = store.upsert_contact(account_id="wxid_local", wxid="wxid_1", nickname="\u5ba2\u62371", source="wechat_local_contact_db")
    c2 = store.upsert_contact(account_id="wxid_local", wxid="wxid_2", nickname="\u5ba2\u62372", source="wechat_local_contact_db")
    store.set_contact_touch_confirmation(c1.id, confirmed=True)
    store.set_contact_touch_confirmation(c2.id, confirmed=True)
    store.mark_contact_touched(plan_id="plan_queue", contact_id=c2.id, touched_at=datetime.now(UTC) - timedelta(days=2))

    response = main.build_touch_queue("plan_queue", main.TouchQueueBuildRequest(max_contacts=10))

    assert response["stats"]["pending"] == 1
    assert response["stats"]["skipped"] == 1
    skipped = [row for row in store.list_plan_targets(plan_id="plan_queue") if row["status"] == "skipped"][0]
    assert skipped["skip_reason"] == "touch_interval_active"


def test_run_touch_queue_sends_pending_targets_and_marks_sent(monkeypatch, tmp_path):
    import app.main as main

    store = AgentStore(f"sqlite:///{tmp_path / 'agent.db'}")
    store.create_schema()
    _save_profile(store)
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "llm", FakeLLM())
    contact = store.upsert_contact(
        account_id="wxid_local",
        wxid="wxid_1",
        nickname="\u5ba2\u62371",
        source="wechat_local_contact_db",
        local_type=1,
        contact_flag=1,
        delete_flag=0,
    )
    store.set_contact_touch_confirmation(contact.id, confirmed=True)
    store.upsert_plan_target(plan_id="plan_queue", contact_id=contact.id, status="pending")

    def fake_send(action: AutomationAction) -> dict:
        return {
            "task": {"id": "task_1", "status": "succeeded"},
            "sidecar": {
                "success": True,
                "verification_status": "verified",
                "message": "message_sent",
                "evidence": {"after_send": r"C:\evidence\after.png"},
            },
        }

    monkeypatch.setattr(main, "send_message", fake_send)

    response = main.run_touch_queue("plan_queue", main.TouchQueueRunRequest(limit=1))

    assert response["ran"] == 1
    assert response["results"][0]["status"] == "sent"
    target = store.get_plan_target(plan_id="plan_queue", contact_id=contact.id)
    assert target is not None
    assert target["status"] == "sent"
    assert target["last_touched_at"] is not None
