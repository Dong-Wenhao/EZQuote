import base64
import copy
import json
import os
from pathlib import Path
import stat
import time
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from fastapi.responses import Response
import pytest

from backend.app import create_app
from backend.connections import ConnectionUpdate, public_origin
from backend.mobile_gateway import create_gateway
from backend.network import ServiceError
from backend.ai import evidence_number

ROOT = Path(__file__).resolve().parents[1]


class FakeProvider:
    def __init__(self):
        self.calls = []
        self.ai_response = None
        self.phone_error = None

    def post(self, url, token, body, timeout=45):
        self.calls.append({"url": url, "token": token, "body": copy.deepcopy(body)})
        if "api.openai.com" in url:
            if isinstance(self.ai_response, Exception):
                raise self.ai_response
            return copy.deepcopy(self.ai_response)
        if self.phone_error:
            raise self.phone_error
        return {"messages": [{"id": "wamid.SYNTHETIC-NOT-A-REAL-MESSAGE"}]}


@pytest.fixture
def connected(tmp_path):
    provider = FakeProvider()
    app = create_app(tmp_path, transport=provider, gateway_ready=lambda: True, start_worker=False)
    with TestClient(app) as client:
        auth = client.post("/api/setup", json={"shop_name": "Synthetic shop", "boss_password": "boss-mobile-test", "staff_password": "staff-mobile-test"}).json()
        boss = {"Authorization": "Bearer " + auth["token"]}
        auth = client.post("/api/login", json={"username": "staff", "password": "staff-mobile-test"}).json()
        staff = {"Authorization": "Bearer " + auth["token"]}
        client.post("/api/catalog/import", headers=boss, json={"filename": "products.xlsx",
            "content_b64": base64.b64encode((ROOT / "samples/products.xlsx").read_bytes()).decode()}).raise_for_status()
        yield client, boss, staff, app, provider


def configure(app, **values):
    old = app.state.connections.load()
    return app.state.connections.save(ConnectionUpdate(**{**old, **values}))


def create_pending(client, staff, key="mobile-fixture-key"):
    body = {"customer": "Synthetic Customer", "inquiry": "A牌50kg水泥20袋", "language": "zh",
            "items": [{"sku": "CEM-A-50", "quantity": "20"}], "notes": "", "source_confirmed": True, "request_key": key}
    response = client.post("/api/quotes", headers=staff, json=body)
    assert response.status_code == 200, response.text
    q = response.json()
    response = client.post("/api/quotes/" + q["id"] + "/submit", headers=staff, json={"expected_revision": 1})
    assert response.status_code == 200, response.text
    return response.json(), body


def mobile_auth(client, staff, q):
    response = client.post("/api/quotes/" + q["id"] + "/mobile-link", headers=staff, json={"expected_revision": q["revision"]})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + urlsplit(response.json()["url"]).fragment}


def extracted(source, normalized, product="水泥", brand="A牌", spec="50kg", quantity="20", unit="袋", missing=None):
    return {"source_text": source, "normalized_text": normalized,
            "evidence": {"product": product, "brand": brand, "spec": spec, "quantity": quantity, "unit": unit},
            "missing_fields": missing or []}


def response(items, language="zh"):
    return {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps({"language": language, "items": items}, ensure_ascii=False)}]}]}


def test_settings_are_boss_only_and_secrets_are_redacted(connected):
    c, boss, staff, app, provider = connected
    assert c.get("/api/integrations", headers=staff).status_code == 403
    settings = configure(app, ai_enabled=True, ai_key="sk-SYNTHETIC-KEY", wa_token="SYNTHETIC-WA-TOKEN")
    assert "ai_key" not in settings and "wa_token" not in settings
    settings = c.get("/api/integrations", headers=boss)
    assert "sk-SYNTHETIC" not in settings.text and "SYNTHETIC-WA-TOKEN" not in settings.text
    assert settings.json()["ai_key_saved"] is True
    assert "ai_key" not in c.get("/api/integrations/status", headers=staff).text
    posted = c.put("/api/integrations", headers=boss, json={"ai_enabled": True, "ai_key": ""})
    assert posted.status_code == 200
    assert app.state.connections.load()["ai_key"] == "sk-SYNTHETIC-KEY"
    assert provider.calls == []
    if os.name != "nt":
        assert stat.S_IMODE(app.state.connections.path.stat().st_mode) == 0o600


@pytest.mark.parametrize("url", ["http://example.com", "https://localhost", "https://127.0.0.1", "https://example.com/path",
                                    "https://user:secret@example.com", "https://example.com?token=x", "https://example.com#x"])
def test_only_public_https_origins_are_accepted(url):
    with pytest.raises(ValueError):
        public_origin(url)


def test_recipient_confirmation_required_and_validation_does_not_echo_keys(connected):
    c, boss, _, app, provider = connected
    response = c.put("/api/integrations", headers=boss, json={
        "wa_enabled": True, "wa_token": "SYNTHETIC-TOKEN", "wa_phone_id": "123456789",
        "boss_phone": "60123456789", "public_url": "https://approval.example.com"})
    assert response.status_code == 422
    assert "SYNTHETIC-TOKEN" not in response.text
    response = c.put("/api/integrations", headers=boss, json={"ai_key": "SYNTHETIC-SECRET", "extra": "forbidden"})
    assert response.status_code == 422 and "SYNTHETIC-SECRET" not in response.text
    assert provider.calls == []


@pytest.mark.parametrize("word,value", [("twenty", 20), ("dua puluh", 20), ("二十", 20), ("two hundred twenty", 220), ("dua ratus dua puluh", 220)])
def test_quantity_words_are_checked(word, value):
    assert evidence_number(word) == value


def test_ai_understands_two_items_and_never_receives_price_fields(connected):
    c, boss, staff, app, provider = connected
    configure(app, ai_enabled=True, ai_key="sk-SYNTHETIC-KEY")
    source = "A牌50kg水泥二十袋，还有 Brand A PVC pipe 20mm five pieces"
    provider.ai_response = response([
        extracted("A牌50kg水泥二十袋", "Brand A Cement 50kg 20 bags", quantity="二十"),
        extracted("Brand A PVC pipe 20mm five pieces", "Brand A PVC pipe 20mm 5 pieces",
                  product="PVC pipe", brand="Brand A", spec="20mm", quantity="five", unit="pieces")
    ])
    parsed = c.post("/api/inquiries/parse", headers=staff, json={"text": source})
    assert parsed.status_code == 200, parsed.text
    assert parsed.json()["method"] == "openai_catalog"
    assert parsed.json()["status"] == "READY", parsed.json()
    assert [line["sku"] for line in parsed.json()["items"]] == ["CEM-A-50", "PVC-A-20"]
    sent = provider.calls[0]["body"]
    assert sent["store"] is False and sent["text"]["format"]["strict"] is True
    assert "unit_price" not in sent["input"] and "18.50" not in sent["input"]
    assert "tools" not in sent


@pytest.mark.parametrize("source,language,product,brand,quantity,unit", [
    ("A牌50kg水泥二十袋", "zh", "水泥", "A牌", "二十", "袋"),
    ("Brand A cement 50kg twenty bags", "en", "cement", "Brand A", "twenty", "bags"),
    ("simen Brand A 50kg dua puluh beg", "ms", "simen", "Brand A", "dua puluh", "beg"),
])
def test_ai_three_languages_keep_source_evidence(connected, source, language, product, brand, quantity, unit):
    c, _, staff, app, provider = connected
    configure(app, ai_enabled=True, ai_key="sk-SYNTHETIC")
    provider.ai_response = response([extracted(source, "Brand A Cement 50kg 20 bags",
        product=product, brand=brand, quantity=quantity, unit=unit)], language)
    parsed = c.post("/api/inquiries/parse", headers=staff, json={"text": source}).json()
    assert parsed["method"] == "openai_catalog" and parsed["status"] == "READY", parsed
    assert parsed["language"] == language and parsed["items"][0]["sku"] == "CEM-A-50"
    assert parsed["items"][0]["source_text"] == source and parsed["items"][0]["quantity"] == "20"


@pytest.mark.parametrize("source,change,issue", [
    ("A牌水泥20袋", {"spec": ""}, "spec"),
    ("50kg水泥20袋", {"brand": ""}, "brand"),
    ("A牌50kg水泥10袋", {"quantity": "10"}, "quantity"),
])
def test_ai_cannot_fill_missing_or_conflicting_facts(connected, source, change, issue):
    c, _, staff, app, provider = connected
    configure(app, ai_enabled=True, ai_key="sk-SYNTHETIC")
    provider.ai_response = response([extracted(source, "Brand A Cement 50kg 20 bags", **change)])
    parsed = c.post("/api/inquiries/parse", headers=staff, json={"text": source}).json()
    assert parsed["method"] == "openai_catalog"
    assert parsed["status"] == "NEEDS_INFO" and parsed["items"][0]["sku"] == ""
    assert issue in parsed["items"][0]["issues"]


@pytest.mark.parametrize("result", [
    ServiceError("provider_network_or_timeout", True),
    {"status": "incomplete", "output": []},
    {"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "No"}]}]},
    {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "{}"}]}]},
])
def test_ai_failures_are_visible_rule_fallbacks(connected, result):
    c, _, staff, app, provider = connected
    configure(app, ai_enabled=True, ai_key="sk-SYNTHETIC")
    provider.ai_response = result
    parsed = c.post("/api/inquiries/parse", headers=staff, json={"text": "A牌50kg水泥20袋"}).json()
    assert parsed["method"] == "catalog_rules" and parsed["ai_state"] == "fallback"
    assert parsed["warning_code"]


def test_mobile_password_approval_is_scoped_and_single_use(connected):
    c, _, staff, app, _ = connected
    configure(app, public_url="https://approval.example.com")
    q, _ = create_pending(c, staff)
    auth = mobile_auth(c, staff, q)
    review = c.post("/api/mobile/review", headers=auth).json()
    assert review["can_decide"] is True and review["quote"]["total"] == "370.00"
    assert "source" not in review["quote"]
    body = {"decision": "approve", "expected_revision": 1, "boss_password": "incorrect"}
    assert c.post("/api/mobile/decision", headers=auth, json=body).status_code == 401
    assert c.get("/api/quotes/" + q["id"], headers=staff).json()["status"] == "PENDING_APPROVAL"
    body["boss_password"] = "boss-mobile-test"
    approved = c.post("/api/mobile/decision", headers=auth, json=body)
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"] == "approved" and approved.json()["pdf_ready"]
    assert c.post("/api/mobile/pdf", headers=auth).content.startswith(b"%PDF")
    assert c.post("/api/mobile/decision", headers=auth, json=body).status_code == 409
    with app.state.store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM approvals WHERE quote_id=?", (q["id"],)).fetchone()[0] == 1


def test_mobile_return_and_password_rate_limit(connected):
    c, _, staff, app, _ = connected
    configure(app, public_url="https://approval.example.com")
    q, _ = create_pending(c, staff)
    auth = mobile_auth(c, staff, q)
    body = {"decision": "return", "expected_revision": 1, "boss_password": "boss-mobile-test", "reason": "Check delivery"}
    returned = c.post("/api/mobile/decision", headers=auth, json=body)
    assert returned.status_code == 200 and returned.json()["state"] == "returned"
    q, _ = create_pending(c, staff, "second-mobile-fixture")
    auth = mobile_auth(c, staff, q)
    for _ in range(6):
        assert c.post("/api/mobile/decision", headers=auth, json={**body, "boss_password": "wrong"}).status_code == 401
    assert c.post("/api/mobile/decision", headers=auth, json=body).status_code == 429


def test_expired_tampered_and_revised_links_cannot_approve(connected):
    c, _, staff, app, _ = connected
    configure(app, public_url="https://approval.example.com")
    q, body = create_pending(c, staff)
    auth = mobile_auth(c, staff, q)
    bad = {"Authorization": auth["Authorization"][:-1] + ("A" if auth["Authorization"][-1] != "A" else "B")}
    assert c.post("/api/mobile/review", headers=bad).status_code == 401
    token = app.state.mobile.validate_token(auth["Authorization"])
    with app.state.store.transaction() as db:
        db.execute("UPDATE mobile_links SET expires=? WHERE id=?", (int(time.time()) - 1, token["id"]))
        row = dict(db.execute("SELECT * FROM mobile_links WHERE id=?", (token["id"],)).fetchone())
    expired = {"Authorization": "Bearer " + app.state.mobile.token(row)}
    assert c.post("/api/mobile/review", headers=expired).status_code == 410
    fresh = mobile_auth(c, staff, q)
    assert c.put("/api/quotes/" + q["id"], headers=staff, json={**body, "expected_revision": 1}).status_code == 200
    assert c.post("/api/mobile/review", headers=fresh).status_code == 409


def enable_phone(app):
    configure(app, wa_enabled=True, wa_token="SYNTHETIC-WA-TOKEN", wa_phone_id="123456789",
              boss_phone="60123456789", phone_confirmed=True, public_url="https://approval.example.com")


def test_notification_is_queued_once_and_acceptance_is_not_delivery(connected):
    c, _, staff, app, provider = connected
    enable_phone(app)
    q, _ = create_pending(c, staff)
    c.post("/api/quotes/" + q["id"] + "/submit", headers=staff, json={"expected_revision": 1})
    with app.state.store.connect() as db:
        rows = db.execute("SELECT * FROM phone_outbox").fetchall()
    assert len(rows) == 1
    app.state.mobile.dispatch(rows[0]["id"])
    app.state.mobile.dispatch(rows[0]["id"])
    assert len(provider.calls) == 1
    request = provider.calls[0]["body"]
    assert request["to"] == "60123456789" and request["type"] == "template"
    assert len(request["template"]["components"][0]["parameters"]) == 4
    quote = c.get("/api/quotes/" + q["id"], headers=staff).json()
    assert quote["mobile_notification"]["status"] == "ACCEPTED"
    assert not any("DELIVERED" in event["action"] for event in quote["activity"])
    retry = c.post("/api/quotes/" + q["id"] + "/phone-notification", headers=staff, json={"expected_revision": 1})
    assert retry.status_code == 409


def test_uncertain_notification_requires_confirmation_and_waits_for_gateway(connected):
    c, _, staff, app, provider = connected
    enable_phone(app)
    q, _ = create_pending(c, staff)
    with app.state.store.connect() as db:
        job_id = db.execute("SELECT id FROM phone_outbox").fetchone()[0]
    app.state.mobile.gateway_ready = lambda: False
    app.state.mobile.dispatch(job_id)
    assert provider.calls == []
    app.state.mobile.gateway_ready = lambda: True
    provider.phone_error = ServiceError("provider_network_or_timeout", True)
    app.state.mobile.dispatch(job_id)
    assert c.get("/api/quotes/" + q["id"], headers=staff).json()["mobile_notification"]["status"] == "UNKNOWN"
    app.state.mobile.dispatch(job_id)
    assert len(provider.calls) == 1
    assert c.post("/api/quotes/" + q["id"] + "/phone-notification", headers=staff, json={"expected_revision": 1}).status_code == 409
    assert c.post("/api/quotes/" + q["id"] + "/phone-notification", headers=staff,
                  json={"expected_revision": 1, "confirm_resend": True}).status_code == 200


def test_public_gateway_does_not_expose_the_workspace(connected):
    c, _, staff, app, _ = connected
    configure(app, public_url="https://approval.example.com")
    q, _ = create_pending(c, staff)
    auth = mobile_auth(c, staff, q)
    calls = []
    def proxy(operation, authorization, body):
        calls.append(operation)
        result = c.post("/api/mobile/" + operation, headers={"Authorization": authorization}, content=body)
        return Response(result.content, status_code=result.status_code, media_type=result.headers.get("content-type", "application/json"))
    with TestClient(create_gateway(proxy)) as gateway:
        assert gateway.get("/mobile").status_code == 200
        assert gateway.get("/api/catalog").status_code == 404
        assert gateway.get("/").status_code == 404
        assert gateway.get("/docs").status_code == 404
        assert gateway.post("/api/mobile/approve").status_code == 404
        assert calls == []
        review = gateway.post("/api/mobile/review", headers=auth, json={})
        assert review.status_code == 200
        assert review.headers["cache-control"] == "no-store"
        assert review.headers["referrer-policy"] == "no-referrer"
        assert calls == ["review"]


def test_interrupted_send_is_not_retried_automatically(connected):
    c, _, staff, app, provider = connected
    enable_phone(app)
    create_pending(c, staff)
    with app.state.store.transaction() as db:
        db.execute("UPDATE phone_outbox SET status='SENDING',attempts=1")
        job_id = db.execute("SELECT id FROM phone_outbox").fetchone()[0]
    app.state.mobile.recover()
    app.state.mobile.dispatch(job_id)
    assert provider.calls == []
    with app.state.store.connect() as db:
        assert db.execute("SELECT status FROM phone_outbox WHERE id=?", (job_id,)).fetchone()[0] == "UNKNOWN"


def test_worker_dispatches_a_submission_without_a_manual_send_call(tmp_path):
    provider = FakeProvider()
    app = create_app(tmp_path, transport=provider, gateway_ready=lambda: True)
    enable_phone(app)
    with TestClient(app) as client:
        auth = client.post("/api/setup", json={"shop_name": "Worker fixture", "boss_password": "boss-worker-test", "staff_password": "staff-worker-test"}).json()
        headers = {"Authorization": "Bearer " + auth["token"]}
        imported = client.post("/api/catalog/import", headers=headers, json={"filename": "products.xlsx",
            "content_b64": base64.b64encode((ROOT / "samples/products.xlsx").read_bytes()).decode()})
        assert imported.status_code == 200
        q, _ = create_pending(client, headers)
        for _ in range(70):
            current = client.get("/api/quotes/" + q["id"], headers=headers).json()
            if current["mobile_notification"]["status"] == "ACCEPTED":
                break
            time.sleep(.05)
        assert current["mobile_notification"]["status"] == "ACCEPTED"
        assert len(provider.calls) == 1


def test_mobile_launcher_will_not_tunnel_another_service(tmp_path, monkeypatch):
    import io
    import run as launcher
    processes = []
    class Process:
        stopped = False
        def poll(self):
            return None
        def terminate(self):
            self.stopped = True
    def popen(*args, **kwargs):
        process = Process()
        processes.append(process)
        return process
    monkeypatch.setenv("WA_QUOTE_DATA", str(tmp_path))
    monkeypatch.setattr(launcher.shutil, "which", lambda _: "/synthetic/cloudflared")
    monkeypatch.setattr(launcher.subprocess, "Popen", popen)
    monkeypatch.setattr(launcher.urllib.request, "urlopen", lambda *args, **kwargs: io.BytesIO(b'{"mobile_gateway":true,"instance":"another-process"}'))
    monkeypatch.setattr(launcher.time, "sleep", lambda _: None)
    assert launcher.start_mobile() == []
    assert len(processes) == 1 and processes[0].stopped
