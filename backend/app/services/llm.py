from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import AgentSettings


@dataclass(frozen=True)
class AIReplyDraft:
    reply_text: str
    intent_label: str
    handoff_required: bool
    handoff_reason: str = ""
    risk_flags: list[str] = field(default_factory=list)
    recommended_next_action: str = ""


class DeepSeekAdapter:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-v4-flash",
        http_client: Any | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.http_client = http_client or httpx.Client()
        self.timeout_seconds = timeout_seconds

    def generate_reply(self, *, system_prompt: str, knowledge_base: str, user_message: str) -> AIReplyDraft:
        if not self.api_key:
            return self._fallback(user_message, reason="missing_api_key")

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": self._system_prompt(system_prompt=system_prompt, knowledge_base=knowledge_base),
                },
                {"role": "user", "content": user_message},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.4,
        }
        response = self.http_client.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return self._fallback(user_message, reason="invalid_json")
        return AIReplyDraft(
            reply_text=str(data.get("reply_text") or "").strip() or self._fallback(user_message).reply_text,
            intent_label=str(data.get("intent_label") or "unknown"),
            handoff_required=bool(data.get("handoff_required", False)),
            handoff_reason=str(data.get("handoff_reason") or ""),
            risk_flags=list(data.get("risk_flags") or []),
            recommended_next_action=str(data.get("recommended_next_action") or ""),
        )

    @staticmethod
    def _system_prompt(*, system_prompt: str, knowledge_base: str) -> str:
        return (
            f"{system_prompt}\n\n"
            "必须只输出 JSON 对象，字段为 reply_text、intent_label、handoff_required、handoff_reason、risk_flags、recommended_next_action。\n"
            "回复要像真人微信短句，不要长段落。报价、会员、售后、预约展厅、人工对接类意向必须 handoff_required=true。\n\n"
            f"知识库：\n{knowledge_base}"
        )

    @staticmethod
    def _fallback(user_message: str, reason: str = "fallback") -> AIReplyDraft:
        cleaned = user_message.strip() or "您的问题"
        handoff_keywords = ("报价", "会员", "售后", "展厅", "人工", "报修")
        handoff = any(keyword in cleaned for keyword in handoff_keywords)
        return AIReplyDraft(
            reply_text=f"您好，关于“{cleaned}”，我先帮您记录下需求，稍后给您更准确的回复。",
            intent_label="fallback",
            handoff_required=handoff or reason != "missing_api_key",
            handoff_reason=reason,
            risk_flags=[reason] if reason != "fallback" else [],
            recommended_next_action="人工复核" if handoff else "继续沟通",
        )


class LLMRouter:
    def __init__(self, settings: AgentSettings | None = None) -> None:
        self.settings = settings or AgentSettings.load()
        self.provider = self.settings.llm_provider
        self.adapter = DeepSeekAdapter(
            api_key=self.settings.deepseek_api_key,
            base_url=self.settings.deepseek_base_url,
            model=self.settings.deepseek_model,
        )

    def draft_reply(self, *, system_prompt: str, knowledge_base: str, message: str) -> AIReplyDraft:
        return self.adapter.generate_reply(system_prompt=system_prompt, knowledge_base=knowledge_base, user_message=message)

    def generate_reply(self, *, message: str, tone: str = "professional") -> str:
        _ = tone
        return DeepSeekAdapter._fallback(message, reason="compatibility").reply_text

    def generate_moment_copy(self, *, base_copy: str, limit: int = 3) -> list[dict[str, str]]:
        base = base_copy.strip() or "欢迎了解玺联惠会员超市"
        return [
            {"content": f"{base}，我可以按您的场景帮您核一版方案。", "comment": "可以先了解下您的使用场景。"}
            for _ in range(max(1, min(limit, 10)))
        ]
