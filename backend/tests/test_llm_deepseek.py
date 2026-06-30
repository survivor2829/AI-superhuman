import json

from app.services.llm import DeepSeekAdapter, AIReplyDraft


class FakeResponse:
    status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "reply_text": "您好，我先了解下您主要看设备还是会员政策。",
                                "intent_label": "需求咨询",
                                "handoff_required": False,
                                "handoff_reason": "",
                                "risk_flags": [],
                                "recommended_next_action": "继续询问需求",
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }


class FakeClient:
    def __init__(self):
        self.payload = None

    def post(self, url, *, headers, json, timeout):
        self.payload = {"url": url, "headers": headers, "json": json, "timeout": timeout}
        return FakeResponse()


def test_deepseek_adapter_posts_openai_compatible_request_and_parses_structured_reply():
    client = FakeClient()
    adapter = DeepSeekAdapter(api_key="secret", base_url="https://api.deepseek.com", model="deepseek-v4-flash", http_client=client)

    draft = adapter.generate_reply(system_prompt="你是销售顾问", knowledge_base="会员权益", user_message="怎么合作")

    assert isinstance(draft, AIReplyDraft)
    assert draft.reply_text.startswith("您好")
    assert draft.intent_label == "需求咨询"
    assert client.payload["url"] == "https://api.deepseek.com/chat/completions"
    assert client.payload["headers"]["Authorization"] == "Bearer secret"
    assert client.payload["json"]["model"] == "deepseek-v4-flash"
    assert client.payload["json"]["response_format"] == {"type": "json_object"}


def test_deepseek_adapter_falls_back_to_safe_draft_when_json_is_invalid():
    class InvalidClient(FakeClient):
        def post(self, url, *, headers, json, timeout):
            return type(
                "InvalidResponse",
                (),
                {
                    "raise_for_status": lambda self: None,
                    "json": lambda self: {"choices": [{"message": {"content": "不是 JSON"}}]},
                },
            )()

    adapter = DeepSeekAdapter(api_key="secret", http_client=InvalidClient())

    draft = adapter.generate_reply(system_prompt="prompt", knowledge_base="", user_message="报价")

    assert draft.handoff_required is True
    assert draft.intent_label == "fallback"
    assert "报价" in draft.reply_text
