from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LocalAction(BaseModel):
    action_type: str
    target_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class LocalActionResult(BaseModel):
    success: bool
    message: str
    dry_run: bool = True
    evidence: dict[str, Any] = Field(default_factory=dict)
    verification_status: str = "failed"
    opened_conversation_title: str = ""
    matched_target: str = ""
    failure_reason: str = ""
