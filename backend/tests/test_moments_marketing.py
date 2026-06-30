from app.models.schemas import AutomationAction


def test_moments_interaction_blocks_non_whitelisted_target(monkeypatch, tmp_path):
    import app.main as main

    called: list[dict] = []
    monkeypatch.setattr(main, "_sidecar_post", lambda path, payload: called.append({"path": path, "payload": payload}) or {})

    response = main.run_moments_interactions(
        AutomationAction(
            action_type="moments.like",
            account_id="local",
            target_id="wxid_customer",
            payload={"whitelist": ["wxid_other"]},
        )
    )

    assert response["success"] is False
    assert response["message"] == "moments_target_not_whitelisted"
    assert called == []


def test_moments_interaction_allows_whitelisted_target(monkeypatch):
    import app.main as main

    calls: list[dict] = []

    def fake_sidecar(path: str, payload: dict) -> dict:
        calls.append({"path": path, "payload": payload})
        return {"success": True, "message": "moments_like_recorded", "evidence": {"after": r"C:\evidence\moments.png"}}

    monkeypatch.setattr(main, "_sidecar_post", fake_sidecar)

    response = main.run_moments_interactions(
        AutomationAction(
            action_type="moments.like",
            account_id="local",
            target_id="wxid_customer",
            payload={"whitelist": ["wxid_customer"]},
        )
    )

    assert response["success"] is True
    assert calls[0]["path"] == "/wechat/moments/like"


def test_scan_moments_feed_proxies_visible_scan(monkeypatch):
    import app.main as main

    monkeypatch.setattr(
        main,
        "_sidecar_get",
        lambda path: {
            "success": True,
            "message": "moments_feed_scanned",
            "items": [{"owner": "A测试客户", "target_id": "wxid_customer"}],
            "evidence": {"feed": r"C:\evidence\feed.png"},
        },
    )

    response = main.scan_moments_feed()

    assert response["success"] is True
    assert response["items"][0]["target_id"] == "wxid_customer"
