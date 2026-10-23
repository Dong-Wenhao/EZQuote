"""Scoped, expiring mobile links and a persistent WhatsApp notification outbox."""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.request

from fastapi import HTTPException

from .network import ServiceError
from .store import now


def _encode(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def gateway_online():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8766/health", timeout=.5) as response:
            return json.loads(response.read(1024)).get("mobile_gateway") is True
    except Exception:
        return False


class Mobile:
    def __init__(self, store, connections, transport, gateway_ready=gateway_online):
        self.store, self.connections, self.transport = store, connections, transport
        self.gateway_ready = gateway_ready
        path = store.directory / ".mobile-link-key"
        with connections.lock:
            if not path.exists():
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(secrets.token_bytes(32))
                    stream.flush()
                    os.fsync(stream.fileno())
            self.key = path.read_bytes()
        if len(self.key) != 32:
            raise ValueError("Mobile signing key is invalid; restore the data backup")

    def token(self, row):
        payload = _encode(json.dumps({"id": row["id"], "exp": row["expires"]}, separators=(",", ":")).encode())
        signature = _encode(hmac.new(self.key, payload.encode(), hashlib.sha256).digest())
        return payload + "." + signature

    def validate_token(self, authorization):
        token = authorization.removeprefix("Bearer ")
        if not authorization.startswith("Bearer ") or len(token) > 1000:
            raise HTTPException(401, "mobile_invalid_link")
        try:
            payload, signature = token.split(".")
            expected = _encode(hmac.new(self.key, payload.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            data = json.loads(_decode(payload))
            if set(data) != {"id", "exp"} or not re.fullmatch(r"[a-f0-9]{32}", data["id"]):
                raise ValueError
        except (ValueError, TypeError, KeyError, UnicodeError):
            raise HTTPException(401, "mobile_invalid_link") from None
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM mobile_links WHERE id=?", (data["id"],)).fetchone()
        if not row or row["expires"] != data["exp"]:
            raise HTTPException(401, "mobile_invalid_link")
        self.check(row)
        return dict(row)

    @staticmethod
    def check(row, require_unused=False):
        if row["expires"] <= int(time.time()):
            raise HTTPException(410, "mobile_expired")
        if row["revoked"]:
            raise HTTPException(409, "mobile_changed")
        if require_unused and row["used_at"]:
            raise HTTPException(409, "mobile_already_processed")

    def issue(self, db, quote, force=False):
        settings = self.connections.load()
        if not settings["public_url"]:
            raise ValueError("Start mobile mode or save the public HTTPS approval origin first")
        if not force:
            old = db.execute("SELECT * FROM mobile_links WHERE quote_id=? AND revision=? AND revoked=0 AND used_at='' AND expires>? ORDER BY expires DESC LIMIT 1",
                             (quote["id"], quote["revision"], int(time.time()))).fetchone()
            if old:
                return dict(old)
        db.execute("UPDATE mobile_links SET revoked=1 WHERE quote_id=? AND revision=? AND used_at=''",
                   (quote["id"], quote["revision"]))
        row = {"id": secrets.token_hex(16), "quote_id": quote["id"], "revision": quote["revision"],
               "expires": int(time.time()) + settings["link_minutes"] * 60}
        db.execute("INSERT INTO mobile_links(id,quote_id,revision,expires) VALUES(?,?,?,?)",
                   (row["id"], row["quote_id"], row["revision"], row["expires"]))
        return row

    def link(self, row, origin=None):
        return (origin or self.connections.load()["public_url"]) + "/mobile#" + self.token(row)

    def consume(self, db, link_id, quote, decision):
        if link_id is None:
            return
        row = db.execute("SELECT * FROM mobile_links WHERE id=?", (link_id,)).fetchone()
        if not row:
            raise HTTPException(401, "mobile_invalid_link")
        self.check(row, require_unused=True)
        if row["quote_id"] != quote["id"] or row["revision"] != quote["revision"] or quote["status"] != "PENDING_APPROVAL":
            raise HTTPException(409, "mobile_changed")
        db.execute("UPDATE mobile_links SET used_at=?,decision=? WHERE id=?", (now(), decision, link_id))

    def queue(self, db, quote, actor, retry=False, confirm=False):
        settings = self.connections.load()
        if not settings["wa_enabled"]:
            return None
        previous = db.execute("SELECT * FROM phone_outbox WHERE quote_id=? AND revision=?", (quote["id"], quote["revision"])).fetchone()
        if previous:
            if not retry or previous["status"] in {"PENDING", "SENDING", "WAITING_GATEWAY"}:
                return previous["id"]
            if previous["status"] in {"ACCEPTED", "UNKNOWN"} and not confirm:
                raise ValueError("confirm_resend")
        link = self.issue(db, quote, force=bool(previous))
        if previous:
            db.execute("UPDATE phone_outbox SET status='PENDING',link_id=?,provider_id='',error='',public_url=?,updated_at=? WHERE id=?",
                       (link["id"], settings["public_url"], now(), previous["id"]))
            job_id = previous["id"]
        else:
            cursor = db.execute("INSERT INTO phone_outbox(quote_id,revision,status,link_id,public_url,updated_at) VALUES(?,?,'PENDING',?,?,?)",
                                (quote["id"], quote["revision"], link["id"], settings["public_url"], now()))
            job_id = cursor.lastrowid
        self.store.event(db, quote, actor, "PHONE_NOTIFICATION_QUEUED")
        return job_id

    @staticmethod
    def summary(db, quote_id, revision):
        row = db.execute("SELECT status,error,attempts,updated_at FROM phone_outbox WHERE quote_id=? AND revision=?", (quote_id, revision)).fetchone()
        return dict(row) if row else None

    def payload(self, quote, link, settings):
        url = self.link(link, settings["public_url"])
        customer = " ".join(re.sub(r"https?://\S+|www\.\S+", "[link]", quote["customer"], flags=re.I).split())[:120] or "Customer"
        body = {"messaging_product": "whatsapp", "to": settings["boss_phone"]}
        if settings["wa_mode"] == "template":
            body.update(type="template", template={"name": settings["wa_template"],
                "language": {"code": settings["wa_template_language"]},
                "components": [{"type": "body", "parameters": [
                    {"type": "text", "text": value} for value in
                    [quote["id"], customer, "RM" + quote["total"], url]
                ]}]})
        else:
            headings = {"zh": "有一笔报价待你审批", "en": "A quotation needs your approval", "ms": "Sebut harga memerlukan kelulusan anda"}
            message = headings[settings["notification_language"]] + "\n" + quote["id"] + "\n" + customer + " · RM" + quote["total"] + "\n" + url
            body.update(type="text", text={"preview_url": False, "body": message})
        return body

    def recover(self):
        with self.store.transaction() as db:
            db.execute("UPDATE phone_outbox SET status='UNKNOWN',error='interrupted_during_send',updated_at=? WHERE status='SENDING'", (now(),))

    def dispatch(self, job_id):
        settings = self.connections.load()
        ready = self.gateway_ready() if settings["wa_enabled"] else False
        with self.store.transaction() as db:
            job = db.execute("SELECT * FROM phone_outbox WHERE id=?", (job_id,)).fetchone()
            if not job or job["status"] not in {"PENDING", "WAITING_GATEWAY"}:
                return
            quote = db.execute("SELECT * FROM quotes WHERE id=?", (job["quote_id"],)).fetchone()
            if not quote or quote["revision"] != job["revision"] or quote["status"] != "PENDING_APPROVAL":
                db.execute("UPDATE phone_outbox SET status='CANCELLED',updated_at=? WHERE id=?", (now(), job_id))
                return
            if not settings["wa_enabled"]:
                db.execute("UPDATE phone_outbox SET status='PAUSED',updated_at=? WHERE id=?", (now(), job_id))
                return
            if not ready:
                if job["status"] != "WAITING_GATEWAY":
                    db.execute("UPDATE phone_outbox SET status='WAITING_GATEWAY',updated_at=? WHERE id=?", (now(), job_id))
                return
            link = db.execute("SELECT * FROM mobile_links WHERE id=?", (job["link_id"],)).fetchone()
            if not link or link["revoked"] or link["used_at"]:
                db.execute("UPDATE phone_outbox SET status='CANCELLED',updated_at=? WHERE id=?", (now(), job_id))
                return
            if link["expires"] <= int(time.time()):
                db.execute("UPDATE mobile_links SET expires=? WHERE id=?", (int(time.time()) + settings["link_minutes"] * 60, link["id"]))
                link = db.execute("SELECT * FROM mobile_links WHERE id=?", (link["id"],)).fetchone()
            quote, link = dict(quote), dict(link)
            db.execute("UPDATE phone_outbox SET status='SENDING',attempts=attempts+1,public_url=?,updated_at=? WHERE id=?",
                       (settings["public_url"], now(), job_id))
        try:
            response = self.transport.post("https://graph.facebook.com/" + settings["wa_version"] + "/" + settings["wa_phone_id"] + "/messages",
                                           settings["wa_token"], self.payload(quote, link, settings), timeout=20)
            provider_id = response.get("messages", [{}])[0].get("id")
            if not isinstance(provider_id, str) or not provider_id or len(provider_id) > 500:
                raise ServiceError("provider_missing_message_id", True)
            status, error, action = "ACCEPTED", "", "PHONE_NOTIFICATION_ACCEPTED"
        except ServiceError as exc:
            status, error, action = ("UNKNOWN" if exc.uncertain else "FAILED"), exc.code, "PHONE_NOTIFICATION_FAILED"
            provider_id = ""
        except Exception:
            status, error, action, provider_id = "UNKNOWN", "provider_invalid_response", "PHONE_NOTIFICATION_FAILED", ""
        with self.store.transaction() as db:
            db.execute("UPDATE phone_outbox SET status=?,error=?,provider_id=?,updated_at=? WHERE id=?",
                       (status, error, provider_id, now(), job_id))
            self.store.event(db, quote, "system", action, {"status": status, "error": error})

    def run(self, stop):
        self.recover()
        while not stop.is_set():
            try:
                with self.store.connect() as db:
                    jobs = [row[0] for row in db.execute("SELECT id FROM phone_outbox WHERE status IN ('PENDING','WAITING_GATEWAY') ORDER BY id LIMIT 10")]
                for job_id in jobs:
                    if stop.is_set():
                        break
                    self.dispatch(job_id)
            except Exception:
                # No raw provider exception or request content is written to logs.
                pass
            stop.wait(2)
