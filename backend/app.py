import hashlib
import json
import os
import secrets
import threading
import time
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .catalog import CatalogError, FIELDS, amount, parse_inquiry, price_items, read_catalog
from .exports import create_ledger, create_pdf, reply_text
from .store import Store, dumps, now, password_record, verify_password
from .ai import AIParser
from .connections import Connections, ConnectionUpdate
from .mobile import Mobile, gateway_online
from .network import ProviderHTTP
from .business import read_business, import_business, get_business, business_summary, number
from .requirements import understand
from .pricing import recommend, save_pricing, get_pricing, totals, ensure_stock
from .reviews import review as create_review, validate as validate_review, saved_review, bind as bind_review, stale as review_stale
from .requirement_tokens import VERSION as PARSER_VERSION

ROOT = Path(__file__).resolve().parents[1]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Setup(Model):
    shop_name: str = Field(min_length=1, max_length=100)
    boss_password: str = Field(min_length=8, max_length=128)
    staff_password: str = Field(min_length=8, max_length=128)


class Login(Model):
    username: Literal["boss", "staff"]
    password: str = Field(min_length=1, max_length=128)


class Upload(Model):
    filename: str = Field(min_length=1, max_length=100)
    content_b64: str = Field(max_length=7_000_000)
    mapping: dict[str, str] = Field(default_factory=dict)
    sheet_name: str | None = None


class Inquiry(Model):
    text: str = Field(min_length=1, max_length=12000)
    mode: Literal["catalog", "requirements"] = "catalog"
    area: str = Field(default="", max_length=160)
    fulfilment: Literal["auto", "delivery", "pickup"] = "auto"


class Item(Model):
    sku: str = Field(min_length=1, max_length=100)
    quantity: str = Field(min_length=1, max_length=30)


class ReviewItem(Item):
    source_id: str | None = Field(default=None, max_length=100)


class Correction(Model):
    issue_id: str = Field(min_length=1, max_length=100)
    value: str | dict[str, str] | list[str]
    reason: str = Field(min_length=3, max_length=500)


class RequirementReview(Model):
    inquiry: str = Field(min_length=1, max_length=12000)
    items: list[ReviewItem] = Field(min_length=1, max_length=40)
    area: str = Field(default="", max_length=160)
    fulfilment: Literal["delivery", "pickup"]
    corrections: list[Correction] = Field(default_factory=list, max_length=100)
    quote_id: str | None = Field(default=None, max_length=100)
    expected_revision: int = Field(default=0, ge=0)


class WhatsAppSource(Model):
    kind: Literal["whatsapp"]
    tab_id: int = Field(ge=0)
    page_session: str = Field(min_length=1, max_length=100)
    chat_token: str = Field(min_length=1, max_length=100)
    chat_title: str = Field(min_length=1, max_length=160)
    message_id: str = Field(default="", max_length=500)
    anchor: str = Field(min_length=1, max_length=100)


class Draft(Model):
    customer: str = Field(min_length=1, max_length=160)
    inquiry: str = Field(min_length=1, max_length=12000)
    language: Literal["zh", "en", "ms"]
    items: list[Item] = Field(min_length=1, max_length=40)
    notes: str = Field(default="", max_length=1000)
    source_confirmed: Literal[True]
    request_key: str = Field(min_length=8, max_length=100)
    source: WhatsAppSource | None = None
    pricing_enabled: bool = False
    delivery_area: str = Field(default="", max_length=160)
    fulfilment: Literal["delivery", "pickup"] = "delivery"
    review_id: str | None = Field(default=None, max_length=100)


class RevisionDraft(Draft):
    expected_revision: int = Field(ge=1)


class Version(Model):
    expected_revision: int = Field(ge=1)


class Approval(Version):
    discount_pct: str | None = Field(default=None, max_length=30)
    freight: str | None = Field(default=None, max_length=30)
    pricing_note: str = Field(default="", max_length=500)


class PricingPreview(Model):
    items: list[Item] = Field(min_length=1, max_length=40)
    inquiry: str = Field(default="", max_length=12000)
    area: str = Field(default="", max_length=160)
    fulfilment: Literal["delivery", "pickup"]
    quote_id: str | None = Field(default=None, max_length=100)
    review_id: str | None = Field(default=None, max_length=100)


class Outcome(Version):
    outcome: Literal["open", "won", "lost"]
    expected_outcome_version: int = Field(default=0, ge=0)
    note: str = Field(default="", max_length=500)
    actual_delivery_cost: str | None = Field(default=None, max_length=30)


class Rejection(Version):
    reason: str = Field(min_length=1, max_length=500)


class Shop(Model):
    name: str = Field(min_length=1, max_length=100)
    address: str = Field(default="", max_length=240)
    phone: str = Field(default="", max_length=80)
    terms: str = Field(default="Delivery and any applicable tax subject to confirmation.", max_length=600)


class Activity(Model):
    action: Literal["REPLY_COPIED", "PDF_PREPARED", "REPLY_INSERTED"]
    revision: int = Field(ge=1)


class PhoneRetry(Version):
    confirm_resend: bool = False


class MobileDecision(Version):
    decision: Literal["approve", "return"]
    boss_password: str = Field(min_length=1, max_length=128)
    reason: str = Field(default="", max_length=500)
    discount_pct: str | None = Field(default=None, max_length=30)
    freight: str | None = Field(default=None, max_length=30)
    pricing_note: str = Field(default="", max_length=500)


def create_app(data_dir=None, transport=None, gateway_ready=None, start_worker=True):
    store = Store(data_dir or os.getenv("WA_QUOTE_DATA") or ROOT / "data")
    connections = Connections(store.directory)
    transport = transport or ProviderHTTP()
    mobile = Mobile(store, connections, transport, gateway_ready or gateway_online)
    parser = AIParser(connections, transport)

    @asynccontextmanager
    async def lifespan(application):
        if not start_worker:
            yield
            return
        stop = threading.Event()
        worker = threading.Thread(target=mobile.run, args=(stop,), name="quote-phone-outbox", daemon=True)
        worker.start()
        try:
            yield
        finally:
            stop.set()
            worker.join(timeout=1)

    app = FastAPI(title="AI Quote Copilot", version="1.6.1", lifespan=lifespan)
    app.state.store = store
    app.state.connections = connections
    app.state.mobile = mobile
    app.state.ai = parser
    export_lock = threading.RLock()
    login_attempts = {}
    mobile_attempts = {}
    app.add_middleware(CORSMiddleware,
                       allow_origins=["http://127.0.0.1:8765", "http://localhost:8765"],
                       allow_origin_regex=r"chrome-extension://[a-p]{32}",
                       allow_credentials=False, allow_methods=["GET", "POST", "PUT", "OPTIONS"],
                       allow_headers=["Authorization", "Content-Type"])

    @app.middleware("http")
    async def local_access(request: Request, call_next):
        if request.headers.get("host", "").split(":")[0] not in {"127.0.0.1", "localhost", "testserver"}:
            return JSONResponse({"detail": "Use the local 127.0.0.1 address"}, status_code=400)
        origin = request.headers.get("origin", "")
        if origin and origin not in {"http://127.0.0.1:8765", "http://localhost:8765"}:
            import re
            if not re.fullmatch(r"chrome-extension://[a-p]{32}", origin):
                return JSONResponse({"detail": "Origin is not allowed"}, status_code=403)
        try:
            if int(request.headers.get("content-length", 0)) > 8_000_000:
                return JSONResponse({"detail": "Request exceeds 8 MB"}, status_code=413)
        except ValueError:
            return JSONResponse({"detail": "Invalid content length"}, status_code=400)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self' http://127.0.0.1:8765; object-src 'none'; frame-ancestors 'none'"
        return response

    @app.exception_handler(CatalogError)
    async def catalog_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=422)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # In particular, do not echo API keys or a boss password in validation errors.
        return JSONResponse({"detail": [{"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
                                        for item in error.errors()]}, status_code=422)

    def current_user(authorization: str = Header(default="")):
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "Please sign in")
        digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
        with store.connect() as db:
            row = db.execute("SELECT u.username,u.role FROM sessions s JOIN users u ON s.username=u.username WHERE token_hash=? AND expires>?", (digest, time.time())).fetchone()
        if not row:
            raise HTTPException(401, "Session expired. Please sign in again")
        return dict(row)

    def boss(user=Depends(current_user)):
        if user["role"] != "boss":
            raise HTTPException(403, "Boss approval is required")
        return user

    def issue_session(db, username):
        token = secrets.token_urlsafe(32)
        db.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))
        db.execute("INSERT INTO sessions VALUES(?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), username, time.time() + 12*60*60))
        return {"token": token, "user": {"username": username, "role": username}, "expires_in": 43200}

    def get_quote(db, quote_id, user):
        q = db.execute("SELECT * FROM quotes WHERE id=?", (quote_id,)).fetchone()
        if not q:
            raise HTTPException(404, "Quotation not found")
        q = dict(q)
        if user["role"] != "boss" and q["owner"] != user["username"]:
            raise HTTPException(403, "This quotation belongs to another user")
        q["items"] = json.loads(q["items"])
        q["pricing"] = get_pricing(db, quote_id, q["revision"])
        q["review"] = saved_review(db, quote_id, q["revision"])
        current_business = get_business(store, db)
        q["review_required"] = bool(current_business["configured"] and q["status"] not in {"COMPLETED", "EXPORT_PENDING"} and (
            not q["pricing"] or not q["review"] or q["review"]["parser_version"] != PARSER_VERSION or
            q["review"]["catalog_id"] != store.catalog(db)["id"] or q["review"]["business_version"] != current_business["id"]))
        outcome = db.execute("SELECT outcome,note,actor,updated_at,version,actual_delivery_cost FROM quote_outcomes WHERE quote_id=? AND revision=?",
                             (quote_id, q["revision"])).fetchone()
        q["outcome"] = dict(outcome) if outcome else {"outcome": "open", "version": 0, "note": "", "actual_delivery_cost": ""}
        return q

    def version(q, expected):
        if q["revision"] != expected:
            raise HTTPException(409, "Quotation changed. Refresh and review the latest revision")

    def _validate_saved(db, q, user):
        checked = q["review"]
        if not checked:
            review_stale()
        req = q["pricing"]["requirement"]
        validate_review(store, db, checked["review_id"], user, q["inquiry"], q["items"], req["area"], req["fulfilment"],
                        q["id"], bound_revision=q["revision"])

    def result(quote_id, user):
        with store.connect() as db:
            q = get_quote(db, quote_id, user)
            source = db.execute("SELECT source FROM quote_sources WHERE quote_id=? AND revision=?",
                                (quote_id, q["revision"])).fetchone()
            q["source"] = json.loads(source[0]) if source else None
            q["mobile_notification"] = mobile.summary(db, quote_id, q["revision"])
            q.pop("request_key", None)
            q.pop("request_hash", None)
            a = db.execute("SELECT * FROM approvals WHERE quote_id=? AND revision=?", (quote_id, q["revision"])).fetchone()
            q["approval"] = None
            if a:
                snap = json.loads(a["snapshot"])
                q["approval"] = {"approved_by": snap["approved_by"], "approved_at": snap["approved_at"],
                                 "export_status": a["export_status"], "error": a["error"],
                                 "replies": {lang: reply_text(snap, lang) for lang in ["zh", "en", "ms"]}}
            q["approved_revisions"] = [r[0] for r in db.execute("SELECT revision FROM approvals WHERE quote_id=? ORDER BY revision", (quote_id,))]
            q["activity"] = [{**dict(r), "details": json.loads(r["details"])} for r in db.execute("SELECT * FROM events WHERE quote_id=? ORDER BY id", (quote_id,))]
            return q

    def export_approval(quote_id, revision):
        with export_lock:
            with store.connect() as db:
                row = db.execute("SELECT * FROM approvals WHERE quote_id=? AND revision=?", (quote_id, revision)).fetchone()
                if not row:
                    raise HTTPException(409, "An approved snapshot is required")
                if row["export_status"] == "COMPLETED":
                    return
                snap = json.loads(row["snapshot"])
            try:
                create_pdf(snap, store.directory / "pdf" / f"{quote_id}-r{revision}.pdf")
                create_ledger(store, store.directory / "exports" / "quotations.xlsx")
                with store.transaction() as db:
                    db.execute("UPDATE approvals SET export_status='COMPLETED',error='' WHERE quote_id=? AND revision=?", (quote_id, revision))
                    db.execute("UPDATE quotes SET status='COMPLETED',updated_at=? WHERE id=? AND revision=?", (now(), quote_id, revision))
                    store.event(db, {"id": quote_id, "revision": revision}, "system", "EXPORT_COMPLETED")
            except Exception as e:
                with store.transaction() as db:
                    db.execute("UPDATE approvals SET export_status='EXPORT_PENDING',error=? WHERE quote_id=? AND revision=?", (type(e).__name__ + ": " + str(e)[:240], quote_id, revision))
                    db.execute("UPDATE quotes SET status='EXPORT_PENDING',updated_at=? WHERE id=? AND revision=?", (now(), quote_id, revision))
                    store.event(db, {"id": quote_id, "revision": revision}, "system", "EXPORT_FAILED", {"error": type(e).__name__})

    @app.get("/api/health")
    def health():
        with store.connect() as db:
            configured = bool(db.execute("SELECT 1 FROM users LIMIT 1").fetchone())
        return {"ok": True, "version": "1.6.1", "configured": configured, "parser": "requirements_rules_and_optional_openai"}

    @app.post("/api/setup")
    def setup(body: Setup):
        if body.boss_password == body.staff_password:
            raise HTTPException(422, "Use different passwords for boss and staff")
        with store.transaction() as db:
            if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                raise HTTPException(409, "Setup is already complete")
            for name, password in [("boss", body.boss_password), ("staff", body.staff_password)]:
                salt, hashed = password_record(password)
                db.execute("INSERT INTO users VALUES(?,?,?,?)", (name, name, salt, hashed))
            shop = store.shop(db)
            shop["name"] = body.shop_name.strip()
            db.execute("INSERT INTO settings VALUES('shop',?)", (dumps(shop),))
            return issue_session(db, "boss")

    @app.post("/api/login")
    def login(body: Login, request: Request):
        key = (request.client.host, body.username)
        recent = [t for t in login_attempts.get(key, []) if t > time.time()-60]
        if len(recent) >= 8:
            raise HTTPException(429, "Too many attempts. Please wait one minute")
        login_attempts[key] = [*recent, time.time()]
        with store.transaction() as db:
            row = db.execute("SELECT * FROM users WHERE username=?", (body.username,)).fetchone()
            if not row or not verify_password(body.password, row["salt"], row["password_hash"]):
                raise HTTPException(401, "Incorrect account or password")
            login_attempts.pop(key, None)
            return issue_session(db, body.username)

    @app.post("/api/logout")
    def logout(authorization: str = Header(default=""), user=Depends(current_user)):
        with store.transaction() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(authorization[7:].encode()).hexdigest(),))
        return {"ok": True}

    @app.get("/api/me")
    def me(user=Depends(current_user)):
        return user

    @app.get("/api/shop")
    def shop(user=Depends(current_user)):
        return store.shop()

    @app.put("/api/shop")
    def save_shop(body: Shop, user=Depends(boss)):
        with store.transaction() as db:
            db.execute("INSERT OR REPLACE INTO settings VALUES('shop',?)", (dumps(body.model_dump()),))
        return body

    @app.get("/api/integrations/status")
    def integration_status(user=Depends(current_user)):
        return connections.status()

    @app.get("/api/integrations")
    def integration_settings(user=Depends(boss)):
        return connections.redacted(connections.load())

    @app.put("/api/integrations")
    def save_integration_settings(body: ConnectionUpdate, user=Depends(boss)):
        try:
            return connections.save(body)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None

    @app.get("/api/catalog")
    def catalog(user=Depends(current_user)):
        return store.catalog()

    @app.post("/api/catalog/preview")
    def preview(body: Upload, user=Depends(boss)):
        if not body.filename.lower().endswith(".xlsx"):
            raise HTTPException(422, "Only .xlsx workbooks are supported")
        data, raw = read_catalog(body.content_b64, body.mapping, body.sheet_name)
        return data

    @app.post("/api/catalog/import")
    def import_catalog(body: Upload, user=Depends(boss)):
        data, raw = read_catalog(body.content_b64, body.mapping, body.sheet_name)
        if not data["valid"]:
            raise HTTPException(422, {"message": "Fix catalog errors before importing", "errors": data["errors"]})
        safe_filename = Path(body.filename.replace("\\", "/")).name
        original = store.directory / "uploads" / (data["sha256"] + ".xlsx")
        if not original.exists():
            original.write_bytes(raw)
        with store.transaction() as db:
            db.execute("INSERT INTO catalogs(created_at,filename,products) VALUES(?,?,?)", (now(), safe_filename, dumps(data["products"])))
        return store.catalog()

    @app.get("/api/catalog/template")
    def template(user=Depends(current_user)):
        return FileResponse(ROOT / "samples" / "products.xlsx", filename="products.xlsx")

    @app.get("/api/business")
    def business_status(user=Depends(current_user)):
        return business_summary(store)

    @app.get("/api/business/template")
    def business_template(user=Depends(current_user)):
        return FileResponse(ROOT / "samples" / "business_demo.xlsx", filename="business_demo.xlsx")

    @app.post("/api/business/preview")
    def business_preview(body: Upload, user=Depends(boss)):
        data, raw = read_business(body.content_b64)
        return {"valid": True, "products": len(data["products"]), "inventory_rows": len(data["inventory"]),
                "history_orders": len({h['order_id'] for h in data['history']}), "delivery_areas": len(data["delivery"]),
                "rules": data["rules"], "fingerprint": data["fingerprint"]}

    @app.post("/api/business/import")
    def business_import(body: Upload, user=Depends(boss)):
        data, raw = read_business(body.content_b64)
        import_business(store, data, raw, body.filename, user["username"])
        return business_summary(store)

    @app.post("/api/pricing/preview")
    def pricing_preview(body: PricingPreview, user=Depends(current_user)):
        with store.connect() as db:
            q = get_quote(db, body.quote_id, user) if body.quote_id else None
            cat = store.catalog(db)
            items, total = price_items([i.model_dump() for i in body.items], cat["products"])
            if not body.review_id:
                raise HTTPException(422, {"code": "review_required", "can_quote": False})
            checked = validate_review(store, db, body.review_id, user, body.inquiry, items, body.area, body.fulfilment,
                                      body.quote_id, q["revision"] if q else 0)
            result = recommend(store, db, items, body.inquiry, body.area, body.fulfilment, body.quote_id)
            result["review_id"] = checked["review_id"]
            return result

    @app.post("/api/requirements/review")
    def requirements_review(body: RequirementReview, user=Depends(current_user)):
        with store.transaction() as db:
            if body.quote_id:
                q = get_quote(db, body.quote_id, user)
                version(q, body.expected_revision)
            elif body.expected_revision:
                review_stale()
            return create_review(store, db, user, body)

    @app.post("/api/inquiries/parse")
    def parse(body: Inquiry, user=Depends(current_user)):
        cat = store.catalog()
        if not cat["products"]:
            raise HTTPException(409, "Ask the boss to import the Excel price list first")
        parsed = understand(body.text, cat["products"], get_business(store), body.area, body.fulfilment) if body.mode == "requirements" else parser.parse(body.text, cat["products"])
        return {**parsed, "catalog_id": cat["id"]}

    @app.post("/api/quotes")
    def create_quote(body: Draft, user=Depends(current_user)):
        data = body.model_dump()
        # Keep request hashes compatible with 1.0 when no source is supplied.
        with store.transaction() as db:
            if body.review_id:
                r = db.execute("SELECT content_hash,actor FROM requirement_reviews WHERE review_id=?", (body.review_id,)).fetchone()
                if not r or r["actor"] != user["username"]:
                    review_stale()
                data["review_id"] = r["content_hash"]
            digest = hashlib.sha256(dumps({k: v for k, v in data.items()
                                          if k != "request_key" and not (k in {"source", "review_id"} and v is None)
                                          and not (k in {"pricing_enabled", "delivery_area", "fulfilment"} and not body.pricing_enabled)}).encode()).hexdigest()
            existing = db.execute("SELECT id,owner,request_hash FROM quotes WHERE request_key=?", (body.request_key,)).fetchone()
            if existing:
                if existing["owner"] != user["username"] or existing["request_hash"] != digest:
                    raise HTTPException(409, "Request key was already used for different content")
                quote_id = existing["id"]
            else:
                if not body.customer.strip() or not body.inquiry.strip():
                    raise HTTPException(422, "Customer and inquiry are required")
                if get_business(store, db)["configured"] and not body.pricing_enabled:
                    raise HTTPException(422, "Business data is configured. Historical pricing review is required")
                cat = store.catalog(db)
                items, total = price_items([i.model_dump() for i in body.items], cat["products"])
                if body.pricing_enabled:
                    ensure_stock(items, get_business(store, db))
                checked = validate_review(store, db, body.review_id, user, body.inquiry, items, body.delivery_area, body.fulfilment) if body.pricing_enabled else None
                quote_id = "Q-" + now()[:10].replace("-", "") + "-" + secrets.token_hex(4).upper()
                stamp = now()
                db.execute("INSERT INTO quotes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (quote_id, 1, "DRAFT", user["username"], body.customer.strip(), body.inquiry.strip(), body.language,
                            dumps(items), total, cat["id"], body.notes, stamp, stamp, body.request_key, digest))
                if body.pricing_enabled:
                    pricing = save_pricing(store, db, {"id": quote_id, "revision": 1}, items, body.inquiry, body.delivery_area, body.fulfilment, checked)
                    bind_review(db, quote_id, 1, checked, user)
                    db.execute("UPDATE quotes SET total=? WHERE id=?", (pricing["recommendation"]["recommended_total"], quote_id))
                    store.event(db, {"id": quote_id, "revision": 1}, "system", "PRICING_RECOMMENDED",
                                {"business_version": pricing["recommendation"]["business_version"], "engine": "local_statistics_v1"})
                if body.source:
                    db.execute("INSERT INTO quote_sources VALUES(?,?,?)",
                               (quote_id, 1, dumps(body.source.model_dump())))
                store.event(db, {"id": quote_id, "revision": 1}, user["username"], "DRAFT_CREATED", {"source_confirmed": True})
        return result(quote_id, user)

    @app.put("/api/quotes/{quote_id}")
    def revise_quote(quote_id: str, body: RevisionDraft, user=Depends(current_user)):
        with store.transaction() as db:
            q = get_quote(db, quote_id, user)
            version(q, body.expected_revision)
            if not body.customer.strip() or not body.inquiry.strip():
                raise HTTPException(422, "Customer and inquiry are required")
            if get_business(store, db)["configured"] and not body.pricing_enabled:
                raise HTTPException(422, "Business data is configured. Historical pricing review is required")
            cat = store.catalog(db)
            items, total = price_items([i.model_dump() for i in body.items], cat["products"])
            checked = validate_review(store, db, body.review_id, user, body.inquiry, items, body.delivery_area, body.fulfilment, quote_id, body.expected_revision) if body.pricing_enabled else None
            new_revision = q["revision"] + 1
            db.execute("UPDATE quotes SET revision=?,status='DRAFT',customer=?,inquiry=?,language=?,items=?,total=?,catalog_id=?,notes=?,updated_at=? WHERE id=?",
                       (new_revision, body.customer.strip(), body.inquiry.strip(), body.language, dumps(items), total, cat["id"], body.notes, now(), quote_id))
            db.execute("UPDATE notifications SET seen=1 WHERE quote_id=?", (quote_id,))
            db.execute("UPDATE mobile_links SET revoked=1 WHERE quote_id=? AND used_at=''", (quote_id,))
            db.execute("UPDATE phone_outbox SET status='CANCELLED',updated_at=? WHERE quote_id=? AND status IN ('PENDING','WAITING_GATEWAY','PAUSED')", (now(), quote_id))
            if body.source:
                db.execute("INSERT INTO quote_sources VALUES(?,?,?)",
                           (quote_id, new_revision, dumps(body.source.model_dump())))
            if body.pricing_enabled:
                pricing = save_pricing(store, db, {"id": quote_id, "revision": new_revision}, items, body.inquiry, body.delivery_area, body.fulfilment, checked)
                bind_review(db, quote_id, new_revision, checked, user)
                db.execute("UPDATE quotes SET total=? WHERE id=?", (pricing["recommendation"]["recommended_total"], quote_id))
                store.event(db, {"id": quote_id, "revision": new_revision}, "system", "PRICING_RECOMMENDED",
                            {"business_version": pricing["recommendation"]["business_version"], "engine": "local_statistics_v1"})
            store.event(db, {"id": quote_id, "revision": new_revision}, user["username"], "DRAFT_REVISED", {"previous_revision": q["revision"]})
        return result(quote_id, user)

    @app.get("/api/quotes")
    def quotes(user=Depends(current_user)):
        with store.connect() as db:
            rows = db.execute(
                "SELECT q.id,q.revision,q.status,q.customer,q.total,q.language,q.updated_at,q.owner,"
                "COALESCE(o.outcome,'open') AS outcome FROM quotes q "
                "LEFT JOIN quote_outcomes o ON o.quote_id=q.id AND o.revision=q.revision "
                + ("" if user["role"] == "boss" else "WHERE q.owner=? ")
                + "ORDER BY q.updated_at DESC LIMIT 200",
                () if user["role"] == "boss" else (user["username"],)).fetchall()
        return [dict(r) for r in rows]

    @app.get("/api/quotes/{quote_id}")
    def quote(quote_id: str, user=Depends(current_user)):
        return result(quote_id, user)

    @app.post("/api/quotes/{quote_id}/submit")
    def submit(quote_id: str, body: Version, user=Depends(current_user)):
        with store.transaction() as db:
            q = get_quote(db, quote_id, user)
            version(q, body.expected_revision)
            if get_business(store, db)["configured"] and not q["pricing"]:
                raise HTTPException(409, "Business data is configured. Revise this quotation with historical pricing")
            if q["pricing"]:
                _validate_saved(db, q, user)
                current_business = get_business(store, db)
                if q["pricing"]["recommendation"]["business_version"] != current_business["id"] or current_business["catalog_id"] != store.catalog(db)["id"]:
                    raise HTTPException(409, "Business data changed. Save a new quotation revision before submitting")
                ensure_stock(q["items"], current_business)
            if q["status"] == "PENDING_APPROVAL":
                pass
            elif q["status"] != "DRAFT":
                raise HTTPException(409, "Save a draft revision before submitting")
            else:
                db.execute("UPDATE quotes SET status='PENDING_APPROVAL',updated_at=? WHERE id=?", (now(), quote_id))
                db.execute("INSERT INTO notifications(quote_id,revision,recipient_role,message,created_at) VALUES(?,?,?,?,?)",
                           (quote_id, q["revision"], "boss", f"{q['customer']} · RM{q['total']}", now()))
                store.event(db, q, user["username"], "SUBMITTED_FOR_APPROVAL")
            mobile.queue(db, q, user["username"])
        return result(quote_id, user)

    def approve_quote(quote_id, body, user, link_id=None):
        with store.transaction() as db:
            q = get_quote(db, quote_id, user)
            version(q, body.expected_revision)
            mobile.consume(db, link_id, q, "approve")
            exists = db.execute("SELECT 1 FROM approvals WHERE quote_id=? AND revision=?", (quote_id, q["revision"])).fetchone()
            if exists and q["pricing"] and (getattr(body, "discount_pct", None) is not None or getattr(body, "freight", None) is not None):
                decision = q["pricing"]["decision"]
                if (getattr(body, "discount_pct", None) is not None and number(body.discount_pct, "discount_pct", 100) != Decimal(decision["discount_pct"])) or (getattr(body, "freight", None) is not None and number(body.freight, "freight") != Decimal(decision["freight"])):
                    raise HTTPException(409, "Approved pricing is immutable. Create a new revision")
            if not exists:
                if q["status"] != "PENDING_APPROVAL":
                    raise HTTPException(409, "Only a submitted quotation can be approved")
                if get_business(store, db)["configured"] and not q["pricing"]:
                    raise HTTPException(409, "Business data is configured. Revise this quotation with historical pricing")
                if q["pricing"]:
                    _validate_saved(db, q, user)
                    pricing = q["pricing"]
                    current_business = get_business(store, db)
                    if pricing["recommendation"]["business_version"] != current_business["id"] or current_business["catalog_id"] != store.catalog(db)["id"]:
                        raise HTTPException(409, "Business data changed. Revise and review the current data before approval")
                    ensure_stock(q["items"], current_business)
                    rec = pricing["recommendation"]
                    pct = getattr(body, "discount_pct", None)
                    freight = getattr(body, "freight", None)
                    decision = totals(rec, pct if pct is not None else rec["suggested_discount_pct"], freight if freight is not None else rec["suggested_freight"])
                    decision.update(mode="accepted" if decision["discount_pct"] == rec["suggested_discount_pct"] and decision["freight"] == rec["suggested_freight"] else "edited",
                                    note=getattr(body, "pricing_note", ""), approved_by=user["username"], approved_at=now())
                    db.execute("UPDATE quote_pricing SET decision=? WHERE quote_id=? AND revision=?", (dumps(decision), quote_id, q["revision"]))
                    q["total"] = decision["final_total"]
                    q["pricing"]["decision"] = decision
                    db.execute("UPDATE quotes SET total=? WHERE id=?", (q["total"], quote_id))
                    store.event(db, q, user["username"], "PRICING_APPROVED", {"mode": decision["mode"], "suggested_discount_pct": rec["suggested_discount_pct"], "suggested_freight": rec["suggested_freight"], "decision": decision})
                elif getattr(body, "discount_pct", None) is not None or getattr(body, "freight", None) is not None:
                    raise HTTPException(422, "Price adjustments require historical pricing mode")
                snap = {k: q[k] for k in ["id", "revision", "owner", "customer", "inquiry", "language", "items", "total", "catalog_id", "notes"]}
                if q["pricing"]:
                    snap["pricing"] = q["pricing"]
                    snap["requirement_review"] = q["review"]
                snap.update(shop=store.shop(db), approved_by=user["username"], approved_at=now())
                db.execute("INSERT INTO approvals(quote_id,revision,snapshot,export_status) VALUES(?,?,?,'EXPORT_PENDING')", (quote_id, q["revision"], dumps(snap)))
                db.execute("UPDATE quotes SET status='EXPORT_PENDING',updated_at=? WHERE id=?", (now(), quote_id))
                db.execute("UPDATE notifications SET seen=1 WHERE quote_id=? AND revision=?", (quote_id, q["revision"]))
                store.event(db, q, user["username"], "APPROVED")
        export_approval(quote_id, body.expected_revision)
        return result(quote_id, user)

    @app.post("/api/quotes/{quote_id}/approve")
    def approve(quote_id: str, body: Approval, user=Depends(boss)):
        return approve_quote(quote_id, body, user)

    @app.post("/api/quotes/{quote_id}/outcome")
    def record_outcome(quote_id: str, body: Outcome, user=Depends(current_user)):
        cost = "" if body.actual_delivery_cost in {None, ""} else amount(number(body.actual_delivery_cost, "actual_delivery_cost"))
        with store.transaction() as db:
            q = get_quote(db, quote_id, user)
            version(q, body.expected_revision)
            if not db.execute("SELECT 1 FROM approvals WHERE quote_id=? AND revision=?", (quote_id, q["revision"])).fetchone():
                raise HTTPException(409, "Record a customer outcome only after owner approval")
            old = db.execute("SELECT * FROM quote_outcomes WHERE quote_id=? AND revision=?", (quote_id, q["revision"])).fetchone()
            unchanged = old and old["outcome"] == body.outcome and old["note"] == body.note and old["actual_delivery_cost"] == cost
            if not unchanged:
                if body.expected_outcome_version != (old["version"] if old else 0):
                    raise HTTPException(409, "Outcome changed. Refresh before editing")
                new_version = (old["version"] if old else 0) + 1
                db.execute("INSERT OR REPLACE INTO quote_outcomes(quote_id,revision,outcome,note,actor,updated_at,version,actual_delivery_cost) VALUES(?,?,?,?,?,?,?,?)",
                           (quote_id, q["revision"], body.outcome, body.note, user["username"], now(), new_version, cost))
                store.event(db, q, user["username"], "OUTCOME_RECORDED", {"outcome": body.outcome, "previous": old["outcome"] if old else "open", "note": body.note, "actual_delivery_cost": cost})
        ledger_error = ""
        try:
            with export_lock:
                create_ledger(store, store.directory / "exports" / "quotations.xlsx")
        except Exception:
            ledger_error = "ledger_retry_required"
        return {**result(quote_id, user), "ledger_error": ledger_error}

    def reject_quote(quote_id, body, user, link_id=None):
        with store.transaction() as db:
            q = get_quote(db, quote_id, user)
            version(q, body.expected_revision)
            mobile.consume(db, link_id, q, "return")
            if q["status"] != "PENDING_APPROVAL":
                raise HTTPException(409, "Only a submitted quotation can be returned")
            db.execute("UPDATE quotes SET status='REJECTED',updated_at=? WHERE id=?", (now(), quote_id))
            db.execute("UPDATE notifications SET seen=1 WHERE quote_id=?", (quote_id,))
            store.event(db, q, user["username"], "RETURNED", {"reason": body.reason})
        return result(quote_id, user)

    @app.post("/api/quotes/{quote_id}/reject")
    def reject(quote_id: str, body: Rejection, user=Depends(boss)):
        return reject_quote(quote_id, body, user)

    @app.post("/api/quotes/{quote_id}/mobile-link")
    def prepare_mobile_link(quote_id: str, body: Version, user=Depends(current_user)):
        with store.transaction() as db:
            q = get_quote(db, quote_id, user)
            version(q, body.expected_revision)
            if q["status"] != "PENDING_APPROVAL":
                raise HTTPException(409, "Only a submitted quotation can be reviewed on mobile")
            try:
                link = mobile.issue(db, q)
            except ValueError as error:
                raise HTTPException(409, str(error)) from None
            store.event(db, q, user["username"], "MOBILE_LINK_PREPARED")
        return {"url": mobile.link(link), "expires": link["expires"]}

    @app.post("/api/quotes/{quote_id}/phone-notification")
    def retry_phone_notification(quote_id: str, body: PhoneRetry, user=Depends(current_user)):
        with store.transaction() as db:
            q = get_quote(db, quote_id, user)
            version(q, body.expected_revision)
            if q["status"] != "PENDING_APPROVAL":
                raise HTTPException(409, "Only a submitted quotation can be notified")
            try:
                job_id = mobile.queue(db, q, user["username"], retry=True, confirm=body.confirm_resend)
            except ValueError as error:
                raise HTTPException(409, str(error)) from None
            if job_id is None:
                raise HTTPException(409, "Enable WhatsApp notifications in connection settings first")
        return result(quote_id, user)

    def mobile_result(link):
        user = {"username": "boss", "role": "boss"}
        q = result(link["quote_id"], user)
        if q["revision"] != link["revision"]:
            raise HTTPException(409, "mobile_changed")
        can_decide = not link["used_at"] and q["status"] == "PENDING_APPROVAL"
        state = "pending" if can_decide else "approved" if q["approval"] else "returned" if q["status"] == "REJECTED" else "processed"
        return {"state": state, "expires": link["expires"], "can_decide": can_decide,
                "pdf_ready": bool(q["approval"] and q["approval"]["export_status"] == "COMPLETED"),
                "quote": {key: q[key] for key in ("id", "revision", "customer", "inquiry", "language", "items", "total", "notes", "status", "pricing", "review_required")},
                "shop": store.shop()["name"]}

    @app.post("/api/mobile/review")
    def mobile_review(authorization: str = Header(default="")):
        return mobile_result(mobile.validate_token(authorization))

    @app.post("/api/mobile/decision")
    def mobile_decision(body: MobileDecision, request: Request, authorization: str = Header(default="")):
        link = mobile.validate_token(authorization)
        mobile.check(link, require_unused=True)
        current = mobile_result(link)
        if not current["can_decide"] or current["quote"]["revision"] != body.expected_revision:
            raise HTTPException(409, "mobile_changed")
        key = link["id"]
        recent = [stamp for stamp in mobile_attempts.get(key, []) if stamp > time.time() - 60]
        if len(recent) >= 6:
            raise HTTPException(429, "mobile_too_many_attempts")
        mobile_attempts[key] = [*recent, time.time()]
        with store.connect() as db:
            account = db.execute("SELECT * FROM users WHERE username='boss'").fetchone()
        if not account or not verify_password(body.boss_password, account["salt"], account["password_hash"]):
            raise HTTPException(401, "mobile_wrong_password")
        mobile_attempts.pop(key, None)
        user = {"username": "boss", "role": "boss"}
        if body.decision == "approve":
            approve_quote(link["quote_id"], Approval(expected_revision=body.expected_revision, discount_pct=body.discount_pct, freight=body.freight, pricing_note=body.pricing_note), user, link["id"])
        else:
            if not body.reason.strip():
                raise HTTPException(422, "mobile_reason_required")
            reject_quote(link["quote_id"], Rejection(expected_revision=body.expected_revision, reason=body.reason.strip()), user, link["id"])
        return mobile_result(mobile.validate_token(authorization))

    @app.post("/api/mobile/pdf")
    def mobile_pdf(authorization: str = Header(default="")):
        link = mobile.validate_token(authorization)
        details = mobile_result(link)
        if not details["pdf_ready"]:
            raise HTTPException(409, "mobile_pdf_pending")
        return FileResponse(store.directory / "pdf" / (link["quote_id"] + "-r" + str(link["revision"]) + ".pdf"),
                            media_type="application/pdf", filename=link["quote_id"] + ".pdf")

    @app.post("/api/quotes/{quote_id}/export")
    def retry_export(quote_id: str, body: Version, user=Depends(current_user)):
        with store.connect() as db:
            q = get_quote(db, quote_id, user)
            version(q, body.expected_revision)
        export_approval(quote_id, body.expected_revision)
        return result(quote_id, user)

    @app.get("/api/quotes/{quote_id}/pdf")
    def pdf(quote_id: str, revision: int | None = None, user=Depends(current_user)):
        with store.connect() as db:
            q = get_quote(db, quote_id, user)
            revision = revision or q["revision"]
            a = db.execute("SELECT 1 FROM approvals WHERE quote_id=? AND revision=?", (quote_id, revision)).fetchone()
            if not a:
                raise HTTPException(409, "Approval is required before preparing the PDF")
        path = store.directory / "pdf" / f"{quote_id}-r{revision}.pdf"
        if not path.exists():
            raise HTTPException(409, "PDF is pending. Retry the export")
        return FileResponse(path, media_type="application/pdf", filename=path.name)

    @app.post("/api/quotes/{quote_id}/activity")
    def activity(quote_id: str, body: Activity, user=Depends(current_user)):
        with store.transaction() as db:
            q = get_quote(db, quote_id, user)
            if not db.execute("SELECT 1 FROM approvals WHERE quote_id=? AND revision=?", (quote_id, body.revision)).fetchone():
                raise HTTPException(409, "Approval is required")
            store.event(db, {"id": quote_id, "revision": body.revision}, user["username"], body.action)
        return {"ok": True}

    @app.get("/api/exports/ledger")
    def ledger(user=Depends(current_user)):
        with export_lock:
            path = store.directory / "exports" / "quotations.xlsx"
            create_ledger(store, path)
        return FileResponse(path, filename="quotations.xlsx")

    @app.get("/api/notifications")
    def notifications(user=Depends(current_user)):
        with store.connect() as db:
            rows = db.execute("SELECT * FROM notifications WHERE recipient_role=? AND seen=0 ORDER BY id DESC LIMIT 100", (user["role"],)).fetchall()
        return [dict(r) for r in rows]

    app.mount("/assets", StaticFiles(directory=ROOT / "extension"), name="assets")

    @app.get("/")
    def home():
        return FileResponse(ROOT / "extension" / "panel.html")

    @app.get("/{asset_name}")
    def front_asset(asset_name: str):
        if asset_name not in {"panel.css", "theme.css", "panel.js", "i18n.js", "copilot.js"}:
            raise HTTPException(404, "Not found")
        return FileResponse(ROOT / "extension" / asset_name)

    return app


app = create_app()
