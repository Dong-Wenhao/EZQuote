"""SQLite persistence. Approval snapshots are immutable; exports are retryable."""
import hashlib
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "quotes.sqlite3"
        for name in ("uploads", "pdf", "exports"):
            (self.directory / name).mkdir(exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS users(
              username TEXT PRIMARY KEY, role TEXT NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(
              token_hash TEXT PRIMARY KEY, username TEXT NOT NULL, expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS catalogs(
              id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
              filename TEXT NOT NULL, products TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS quotes(
              id TEXT PRIMARY KEY, revision INTEGER NOT NULL, status TEXT NOT NULL,
              owner TEXT NOT NULL, customer TEXT NOT NULL, inquiry TEXT NOT NULL,
              language TEXT NOT NULL, items TEXT NOT NULL, total TEXT NOT NULL,
              catalog_id INTEGER NOT NULL, notes TEXT NOT NULL,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              request_key TEXT UNIQUE, request_hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS approvals(
              quote_id TEXT NOT NULL, revision INTEGER NOT NULL, snapshot TEXT NOT NULL,
              export_status TEXT NOT NULL, error TEXT NOT NULL DEFAULT '',
              PRIMARY KEY(quote_id, revision));
            CREATE TABLE IF NOT EXISTS events(
              id INTEGER PRIMARY KEY AUTOINCREMENT, quote_id TEXT NOT NULL,
              revision INTEGER NOT NULL, at TEXT NOT NULL, actor TEXT NOT NULL,
              action TEXT NOT NULL, details TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS notifications(
              id INTEGER PRIMARY KEY AUTOINCREMENT, quote_id TEXT NOT NULL,
              revision INTEGER NOT NULL, recipient_role TEXT NOT NULL,
              message TEXT NOT NULL, created_at TEXT NOT NULL, seen INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS quote_sources(
              quote_id TEXT NOT NULL, revision INTEGER NOT NULL, source TEXT NOT NULL,
              PRIMARY KEY(quote_id, revision));
            CREATE TABLE IF NOT EXISTS mobile_links(
              id TEXT PRIMARY KEY, quote_id TEXT NOT NULL, revision INTEGER NOT NULL,
              expires INTEGER NOT NULL, revoked INTEGER NOT NULL DEFAULT 0,
              used_at TEXT NOT NULL DEFAULT '', decision TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS phone_outbox(
              id INTEGER PRIMARY KEY AUTOINCREMENT, quote_id TEXT NOT NULL, revision INTEGER NOT NULL,
              status TEXT NOT NULL, link_id TEXT NOT NULL, provider_id TEXT NOT NULL DEFAULT '',
              error TEXT NOT NULL DEFAULT '', attempts INTEGER NOT NULL DEFAULT 0,
              public_url TEXT NOT NULL, updated_at TEXT NOT NULL,
              UNIQUE(quote_id, revision));
            CREATE TABLE IF NOT EXISTS business_versions(
              id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
              filename TEXT NOT NULL, fingerprint TEXT NOT NULL, catalog_id INTEGER NOT NULL,
              data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS quote_pricing(
              quote_id TEXT NOT NULL, revision INTEGER NOT NULL,
              requirement TEXT NOT NULL, recommendation TEXT NOT NULL,
              decision TEXT NOT NULL DEFAULT '', PRIMARY KEY(quote_id,revision));
            CREATE TABLE IF NOT EXISTS quote_outcomes(
              quote_id TEXT NOT NULL, revision INTEGER NOT NULL,
              outcome TEXT NOT NULL, note TEXT NOT NULL, actor TEXT NOT NULL,
              updated_at TEXT NOT NULL, version INTEGER NOT NULL, actual_delivery_cost TEXT NOT NULL DEFAULT '',
              PRIMARY KEY(quote_id,revision));
            CREATE TABLE IF NOT EXISTS requirement_reviews(
              review_id TEXT PRIMARY KEY, actor TEXT NOT NULL, content_hash TEXT NOT NULL,
              parser_version TEXT NOT NULL, catalog_id INTEGER NOT NULL, business_version INTEGER NOT NULL,
              quote_id TEXT NOT NULL, base_revision INTEGER NOT NULL, snapshot TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS quote_reviews(
              quote_id TEXT NOT NULL, revision INTEGER NOT NULL, review_id TEXT NOT NULL UNIQUE,
              PRIMARY KEY(quote_id,revision));
            """)
            if "actual_delivery_cost" not in {r[1] for r in db.execute("PRAGMA table_info(quote_outcomes)")}:
                db.execute("ALTER TABLE quote_outcomes ADD COLUMN actual_delivery_cost TEXT NOT NULL DEFAULT ''")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @contextmanager
    def transaction(self):
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def catalog(self, db=None):
        if db is None:
            with self.connect() as conn:
                return self.catalog(conn)
        row = db.execute("SELECT * FROM catalogs ORDER BY id DESC LIMIT 1").fetchone()
        return {"id": row["id"], "products": json.loads(row["products"]),
                "filename": row["filename"], "created_at": row["created_at"]} if row else {"id": 0, "products": []}

    def shop(self, db=None):
        if db is None:
            with self.connect() as conn:
                return self.shop(conn)
        row = db.execute("SELECT value FROM settings WHERE key='shop'").fetchone()
        return json.loads(row[0]) if row else {"name": "Demo Building Supplies", "address": "", "phone": "", "terms": "Delivery and any applicable tax subject to confirmation."}

    @staticmethod
    def event(db, quote, actor, action, details=None):
        db.execute("INSERT INTO events(quote_id,revision,at,actor,action,details) VALUES(?,?,?,?,?,?)",
                   (quote["id"], quote["revision"], now(), actor, action, dumps(details or {})))


def password_record(password):
    salt = secrets.token_hex(16)
    return salt, hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


def verify_password(password, salt, expected):
    actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return secrets.compare_digest(actual, expected)
