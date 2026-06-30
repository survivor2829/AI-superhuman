from __future__ import annotations

import os

from fastapi import FastAPI
from pydantic import BaseModel

from app.services.automation import WeixinAutomationDriver
from app.services.guardrails import LocalAction, LocalActionResult
from app.services.weixin_driver import build_default_driver

app = FastAPI(title="Agent MVP RPA Sidecar", version="0.1.0")
driver = WeixinAutomationDriver(
    build_default_driver(),
    dry_run=os.environ.get("RPA_DRY_RUN", "false").lower() in {"1", "true", "yes"},
)


class ContactSyncRequest(BaseModel):
    mode: str = "local_db_full"
    account_id: str = "auto"
    auto_decrypt: bool = True


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "rpa-sidecar", "mode": "dry_run" if driver.dry_run else "real"}


@app.get("/wechat/status")
def wechat_status() -> dict[str, object]:
    return driver.status()


@app.get("/wechat/window/probe")
def window_probe() -> dict[str, object]:
    return driver.probe()


@app.get("/send/driver/probe")
def send_driver_probe() -> dict[str, object]:
    return driver.send_driver_probe()


@app.get("/wechat/accounts/local")
def local_accounts() -> dict[str, object]:
    return {"accounts": driver.local_accounts()}


@app.post("/wechat/contacts/sync")
def sync_contacts(request: ContactSyncRequest) -> dict[str, object]:
    return driver.sync_contacts(account_id=request.account_id, auto_decrypt=request.auto_decrypt)


@app.get("/wechat/chat/sessions")
def chat_sessions() -> dict[str, object]:
    return {"dry_run": driver.dry_run, "sessions": []}


@app.post("/wechat/message/send", response_model=LocalActionResult)
def send_message(action: LocalAction) -> LocalActionResult:
    return driver.execute(LocalAction(action_type="message.send", target_id=action.target_id, payload=action.payload))


@app.post("/wechat/moments/publish", response_model=LocalActionResult)
def publish_moment(action: LocalAction) -> LocalActionResult:
    return driver.execute(LocalAction(action_type="moments.publish", target_id=action.target_id, payload=action.payload))


@app.post("/wechat/moments/like", response_model=LocalActionResult)
def like_moment(action: LocalAction) -> LocalActionResult:
    return driver.execute(LocalAction(action_type="moments.like", target_id=action.target_id, payload=action.payload))


@app.post("/wechat/moments/comment", response_model=LocalActionResult)
def comment_moment(action: LocalAction) -> LocalActionResult:
    return driver.execute(LocalAction(action_type="moments.comment", target_id=action.target_id, payload=action.payload))


@app.post("/rpa/stop", response_model=LocalActionResult)
def stop() -> LocalActionResult:
    return driver.stop()
