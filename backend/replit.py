"""Opt-in public-web configuration and first-run accounts for a Replit demo."""
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from .store import Store, dumps, password_record

ROOT = Path(__file__).resolve().parents[1]


def normalize_public_origins(origins):
    """Accept exact HTTPS origins, never wildcard hosts or client-supplied headers."""
    if isinstance(origins, str):
        raise ValueError("Public origins must be a sequence of HTTPS origins")
    result = []
    for value in origins:
        try:
            value = value.strip()
            parsed = urlsplit(value)
            hostname = parsed.hostname
            valid_host = hostname and len(hostname) <= 253 and all(
                re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in hostname.split("."))
            if (parsed.scheme != "https" or not valid_host
                    or parsed.username is not None or parsed.password is not None
                    or parsed.port not in (None, 443) or parsed.path not in ("", "/")
                    or "?" in value or "#" in value or hostname == "localhost"):
                raise ValueError
        except (AttributeError, TypeError, ValueError):
            raise ValueError("Public origins must be exact HTTPS origins without credentials, paths or nonstandard ports") from None
        origin = "https://" + hostname
        if origin not in result:
            result.append(origin)
    return tuple(result)


def public_origins_from_environment(environment=None):
    environment = os.environ if environment is None else environment
    origins = []
    explicit = environment.get("EZQUOTE_PUBLIC_ORIGIN", "").strip()
    if explicit:
        origins.extend(normalize_public_origins([explicit]))
    domains = [environment.get("REPLIT_DEV_DOMAIN", "")]
    domains.extend(environment.get("REPLIT_DOMAINS", "").split(","))
    for domain in domains:
        domain = domain.strip()
        if domain:
            try:
                discovered = normalize_public_origins(["https://" + domain])
            except ValueError:
                # Platform metadata is a convenience; an explicit origin remains authoritative.
                continue
            origins.extend(origin for origin in discovered if origin not in origins)
    if not origins:
        raise RuntimeError("Set EZQUOTE_PUBLIC_ORIGIN to the exact HTTPS app URL, or provide Replit's domain environment variables")
    return tuple(origins)


def bootstrap_accounts(directory, environment):
    """Initialize accounts before public listening; never reset an existing installation."""
    store = Store(directory)
    with store.transaction() as db:
        users = db.execute("SELECT username,role FROM users").fetchall()
        if users:
            if {(row["username"], row["role"]) for row in users} != {("boss", "boss"), ("staff", "staff")}:
                raise RuntimeError("The cloud database must contain both boss and staff accounts; restore a complete backup")
            return
        boss = environment.get("EZQUOTE_BOSS_PASSWORD", "")
        staff = environment.get("EZQUOTE_STAFF_PASSWORD", "")
        if not all(isinstance(value, str) and 8 <= len(value) <= 128 for value in (boss, staff)):
            raise RuntimeError("Set EZQUOTE_BOSS_PASSWORD and EZQUOTE_STAFF_PASSWORD to passwords of 8 to 128 characters before first launch")
        if boss == staff:
            raise RuntimeError("EZQUOTE_BOSS_PASSWORD and EZQUOTE_STAFF_PASSWORD must be different")
        shop_name = environment.get("EZQUOTE_SHOP_NAME", "EzQuote Demo").strip()
        if not 1 <= len(shop_name) <= 100:
            raise RuntimeError("EZQUOTE_SHOP_NAME must contain 1 to 100 nonblank characters")
        for name, password in (("boss", boss), ("staff", staff)):
            salt, hashed = password_record(password)
            db.execute("INSERT INTO users VALUES(?,?,?,?)", (name, name, salt, hashed))
        shop = store.shop(db)
        shop["name"] = shop_name
        db.execute("INSERT OR REPLACE INTO settings VALUES('shop',?)", (dumps(shop),))


def create_replit_app(environment=None, data_dir=None, *, start_worker=True, transport=None):
    """Uvicorn factory: validate origins and initialize accounts before serving requests."""
    environment = os.environ if environment is None else environment
    origins = public_origins_from_environment(environment)
    directory = data_dir or environment.get("WA_QUOTE_DATA") or ROOT / "data" / "replit-demo"
    bootstrap_accounts(directory, environment)
    from .app import create_app
    return create_app(directory, transport=transport, start_worker=start_worker, public_origins=origins)
