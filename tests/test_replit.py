"""The public demo is opt-in, origin-bounded and configured before first access."""
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.replit import create_replit_app, normalize_public_origins, public_origins_from_environment

ORIGIN = "https://ezquote-demo.replit.app"
PASSWORDS = {"boss": "synthetic-cloud-owner", "staff": "synthetic-cloud-staff"}


def environment(**changes):
    return {"EZQUOTE_PUBLIC_ORIGIN": ORIGIN,
            "EZQUOTE_BOSS_PASSWORD": PASSWORDS["boss"],
            "EZQUOTE_STAFF_PASSWORD": PASSWORDS["staff"],
            "EZQUOTE_SHOP_NAME": "Synthetic Cloud Demo", **changes}


def client_for(directory, config=None):
    return TestClient(create_replit_app(environment() if config is None else config, directory,
                                        start_worker=False), base_url=ORIGIN)


def test_desktop_default_still_rejects_public_access(tmp_path):
    with TestClient(create_app(tmp_path, start_worker=False), base_url=ORIGIN) as client:
        assert client.get("/api/health").status_code == 400
        assert client.get("/api/health", headers={"Host": "localhost", "Origin": ORIGIN}).status_code == 403


def test_exact_cloud_origin_supports_workspace_and_cors(tmp_path):
    with client_for(tmp_path) as client:
        response = client.get("/api/health", headers={"Origin": ORIGIN})
        assert response.json()["configured"] is True
        assert response.headers["access-control-allow-origin"] == ORIGIN
        assert "setupForm" in client.get("/").text
        response = client.options("/api/login", headers={"Origin": ORIGIN,
                                  "Access-Control-Request-Method": "POST",
                                  "Access-Control-Request-Headers": "Content-Type"})
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == ORIGIN


def test_cloud_rejects_unconfigured_origins_and_forwarded_host_spoofing(tmp_path):
    with client_for(tmp_path) as client:
        assert client.get("/api/health", headers={"Origin": "https://evil.example"}).status_code == 403
        assert client.get("/api/health", headers={"Host": "evil.example",
                         "X-Forwarded-Host": "ezquote-demo.replit.app", "Origin": ORIGIN}).status_code == 400
        assert client.get("/api/health", headers={"Host": "other.replit.app"}).status_code == 400


@pytest.mark.parametrize("origin", ["http://demo.replit.app", "https://*.replit.app",
    "https://user:secret@demo.replit.app", "https://demo.replit.app/path",
    "https://demo.replit.app?secret=example", "https://demo.replit.app#fragment",
    "https://demo.replit.app:444", "https://demo.replit.app:invalid", "https://bad..replit.app"])
def test_invalid_public_origin_fails_before_database_creation(tmp_path, origin):
    with pytest.raises(ValueError) as error:
        create_replit_app(environment(EZQUOTE_PUBLIC_ORIGIN=origin), tmp_path / "new")
    assert origin not in str(error.value)
    assert not (tmp_path / "new").exists()


def test_platform_domain_discovery_is_exact_and_deduplicated():
    config = {"REPLIT_DEV_DOMAIN": "demo.replit.dev",
              "REPLIT_DOMAINS": "demo.replit.app, demo.replit.dev"}
    assert public_origins_from_environment(config) == ("https://demo.replit.dev", ORIGIN.replace("ezquote-demo", "demo"))
    assert normalize_public_origins([ORIGIN + "/", ORIGIN + ":443"]) == (ORIGIN,)
    with pytest.raises(RuntimeError):
        public_origins_from_environment({})


def test_explicit_origin_works_when_optional_platform_metadata_is_unusable():
    assert public_origins_from_environment({"EZQUOTE_PUBLIC_ORIGIN": ORIGIN,
        "REPLIT_DEV_DOMAIN": "not/a/domain", "REPLIT_DOMAINS": "https://unexpected.example"}) == (ORIGIN,)


def test_cloud_default_data_directory_is_separate_from_local_accounts(tmp_path, monkeypatch):
    import backend.replit as cloud
    monkeypatch.setattr(cloud, "ROOT", tmp_path)
    app = create_replit_app(environment(), start_worker=False)
    assert app.state.store.directory == tmp_path / "data" / "replit-demo"
    assert not (tmp_path / "data" / "quotes.sqlite3").exists()


@pytest.mark.parametrize("changes", [{"EZQUOTE_BOSS_PASSWORD": ""},
    {"EZQUOTE_STAFF_PASSWORD": "short"}, {"EZQUOTE_STAFF_PASSWORD": "x" * 129},
    {"EZQUOTE_STAFF_PASSWORD": PASSWORDS["boss"]}])
def test_first_run_password_configuration_fails_without_exposing_values(tmp_path, changes):
    config = environment(**changes)
    with pytest.raises(RuntimeError) as error:
        create_replit_app(config, tmp_path)
    for value in (config["EZQUOTE_BOSS_PASSWORD"], config["EZQUOTE_STAFF_PASSWORD"]):
        if value:
            assert value not in str(error.value)
    with create_app(tmp_path, start_worker=False).state.store.connect() as db:
        assert db.execute("SELECT count(*) FROM users").fetchone()[0] == 0


def test_accounts_are_ready_before_public_requests_and_setup_is_closed(tmp_path):
    with client_for(tmp_path) as client:
        for username, password in PASSWORDS.items():
            response = client.post("/api/login", json={"username": username, "password": password})
            assert response.status_code == 200
            token = response.json()["token"]
            me = client.get("/api/me", headers={"Authorization": "Bearer " + token}).json()
            assert me["username"] == username and me["role"] == username
        assert client.post("/api/setup", json={"shop_name": "Unwanted reset",
            "boss_password": "synthetic-reset-owner", "staff_password": "synthetic-reset-staff"}).status_code == 409
        assert PASSWORDS["boss"].encode() not in (tmp_path / "quotes.sqlite3").read_bytes()


def test_restart_preserves_existing_accounts_sessions_and_shop(tmp_path):
    with client_for(tmp_path) as client:
        token = client.post("/api/login", json={"username": "boss", "password": PASSWORDS["boss"]}).json()["token"]
    config = {"EZQUOTE_PUBLIC_ORIGIN": ORIGIN, "EZQUOTE_BOSS_PASSWORD": "do-not-reset-owner",
              "EZQUOTE_STAFF_PASSWORD": "do-not-reset-staff", "EZQUOTE_SHOP_NAME": "Do not replace"}
    with client_for(tmp_path, config) as client:
        headers = {"Authorization": "Bearer " + token}
        assert client.get("/api/me", headers=headers).status_code == 200
        assert client.get("/api/shop", headers=headers).json()["name"] == "Synthetic Cloud Demo"
        assert client.post("/api/login", json={"username": "boss", "password": PASSWORDS["boss"]}).status_code == 200
        assert client.post("/api/login", json={"username": "boss", "password": config["EZQUOTE_BOSS_PASSWORD"]}).status_code == 401
    with client_for(tmp_path, {"EZQUOTE_PUBLIC_ORIGIN": ORIGIN}) as client:
        assert client.get("/api/health").json()["configured"] is True
