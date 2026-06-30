import sqlite3
from datetime import UTC, datetime

from app.models.schemas import AutomationAction
from app.services.llm import AIReplyDraft
from app.services.local_messages import WechatSessionMessageScanner
from app.services.store import AgentStore


class FakeReplyLLM:
    provider = "fake"

    def __init__(self, *, handoff: bool = False) -> None:
        self.handoff = handoff

    def draft_reply(self, *, system_prompt: str, knowledge_base: str, message: str) -> AIReplyDraft:
        return AIReplyDraft(
            reply_text="\u60a8\u597d\uff0c\u6211\u5148\u5e2e\u60a8\u8bb0\u4e0b\u9700\u6c42\u3002",
            intent_label="price" if self.handoff else "reply",
            handoff_required=self.handoff,
            handoff_reason="\u62a5\u4ef7\u9700\u4eba\u5de5\u63a5\u7ba1" if self.handoff else "",
        )


def test_session_scanner_reads_only_unread_private_text(tmp_path):
    session_dir = tmp_path / "wechat_decrypted" / "wxid_test" / "session"
    session_dir.mkdir(parents=True)
    db_path = session_dir / "session.db"
    con = sqlite3.connect(db_path)
    con.execute(
        """
        create table SessionTable (
            username text,
            unread_count integer,
            summary text,
            last_timestamp integer,
            last_msg_type integer
        )
        """
    )
    con.executemany(
        "insert into SessionTable values (?, ?, ?, ?, ?)",
        [
            ("wxid_customer", 1, "\u4ef7\u683c\u600e\u4e48\u7b97", 1780000000, 1),
            ("room@chatroom", 2, "\u7fa4\u6d88\u606f", 1780000001, 1),
            ("gh_official", 1, "\u516c\u4f17\u53f7", 1780000002, 1),
            ("wxid_image", 1, "[\u56fe\u7247]", 1780000003, 3),
        ],
    )
    con.commit()
    con.close()

    messages = WechatSessionMessageScanner(tmp_path).scan_unread_private_text(limit=10)

    assert len(messages) == 1
    assert messages[0].wxid == "wxid_customer"
    assert messages[0].content == "\u4ef7\u683c\u600e\u4e48\u7b97"


def test_auto_reply_scan_queues_unread_messages(monkeypatch, tmp_path):
    import app.main as main

    store = AgentStore(f"sqlite:///{tmp_path / 'agent.db'}")
    store.create_schema()
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(
        main,
        "message_scanner",
        type("Scanner", (), {"scan_unread_private_text": lambda self, limit=20: [
            type("Msg", (), {
                "message_key": "wxid_customer:1:abc",
                "wxid": "wxid_customer",
                "content": "\u4f60\u597d",
                "created_at": datetime(2026, 6, 30, tzinfo=UTC),
            })()
        ]})(),
    )

    response = main.scan_auto_replies(main.AutoReplyScanRequest(limit=5))

    assert response["queued"] == 1
    assert store.list_auto_reply_items(statuses={"pending"})[0]["wxid"] == "wxid_customer"


def test_auto_reply_handoff_does_not_send(monkeypatch, tmp_path):
    import app.main as main

    store = AgentStore(f"sqlite:///{tmp_path / 'agent.db'}")
    store.create_schema()
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "llm", FakeReplyLLM(handoff=True))
    store.upsert_auto_reply_item(
        message_key="wxid_customer:1:abc",
        wxid="wxid_customer",
        inbound_text="\u62a5\u4ef7\u591a\u5c11",
        inbound_created_at=datetime(2026, 6, 30, tzinfo=UTC),
    )
    sent: list[AutomationAction] = []
    monkeypatch.setattr(main, "send_message", lambda action: sent.append(action) or {"sidecar": {"success": True, "verification_status": "verified"}})

    response = main.run_auto_reply_queue(main.AutoReplyRunRequest(limit=1, direct_send=True))

    assert response["processed"] == 1
    assert response["results"][0]["status"] == "handoff"
    assert sent == []


def test_auto_reply_non_handoff_sends_and_marks_sent(monkeypatch, tmp_path):
    import app.main as main

    store = AgentStore(f"sqlite:///{tmp_path / 'agent.db'}")
    store.create_schema()
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "llm", FakeReplyLLM(handoff=False))
    store.upsert_auto_reply_item(
        message_key="wxid_customer:1:abc",
        wxid="wxid_customer",
        inbound_text="\u4f60\u597d",
        inbound_created_at=datetime(2026, 6, 30, tzinfo=UTC),
    )

    def fake_send(action: AutomationAction) -> dict:
        return {"task": {"id": "task_1"}, "sidecar": {"success": True, "verification_status": "verified", "message": "message_sent"}}

    monkeypatch.setattr(main, "send_message", fake_send)

    response = main.run_auto_reply_queue(main.AutoReplyRunRequest(limit=1, direct_send=True))

    assert response["results"][0]["status"] == "sent"
    assert store.list_auto_reply_items(statuses={"sent"})[0]["reply_text"] == "\u60a8\u597d\uff0c\u6211\u5148\u5e2e\u60a8\u8bb0\u4e0b\u9700\u6c42\u3002"
