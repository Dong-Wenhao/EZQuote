"""Boss-managed local settings. Secrets never leave the server in API responses."""
import copy
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

DEFAULTS = {
    "ai_enabled": False, "ai_model": "gpt-5.4-mini", "ai_key": "",
    "wa_enabled": False, "wa_token": "", "wa_phone_id": "", "boss_phone": "",
    "phone_confirmed": False, "wa_version": "v26.0", "wa_mode": "template",
    "wa_template": "quote_approval", "wa_template_language": "en_US",
    "notification_language": "zh", "public_url": "", "link_minutes": 60,
}
SECRET_FIELDS = {"ai_key", "wa_token"}
_locks_guard = threading.Lock()
_locks = {}


class ConnectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ai_enabled: bool = False
    ai_model: str = Field(default="gpt-5.4-mini", min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9._:/-]+$")
    ai_key: str = Field(default="", max_length=4096)
    clear_ai_key: bool = False
    wa_enabled: bool = False
    wa_token: str = Field(default="", max_length=4096)
    clear_wa_token: bool = False
    wa_phone_id: str = Field(default="", max_length=50)
    boss_phone: str = Field(default="", max_length=30)
    phone_confirmed: bool = False
    wa_version: str = Field(default="v26.0", pattern=r"^v[0-9]{1,3}\.[0-9]{1,2}$")
    wa_mode: Literal["text", "template"] = "template"
    wa_template: str = Field(default="quote_approval", max_length=100, pattern=r"^[a-z0-9_]*$")
    wa_template_language: str = Field(default="en_US", max_length=12, pattern=r"^[a-z]{2,3}(?:_[A-Z]{2})?$")
    notification_language: Literal["zh", "en", "ms"] = "zh"
    public_url: str = Field(default="", max_length=300)
    link_minutes: int = Field(default=60, ge=15, le=1440)


def public_origin(value):
    value = value.strip().rstrip("/")
    if not value:
        return ""
    try:
        url = urlsplit(value)
        if (url.scheme != "https" or not url.hostname or url.username or url.password or
                url.query or url.fragment or url.path or url.port not in (None, 443)):
            raise ValueError
        host = url.hostname.lower()
        if host in {"localhost", "testserver"} or host.endswith((".localhost", ".local")) or "." not in host:
            raise ValueError
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError("Use a public HTTPS origin, without a path, query or credentials")
    return "https://" + host


class Connections:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "connections.json"
        with _locks_guard:
            self.lock = _locks.setdefault(str(self.path.resolve()), threading.RLock())

    def load(self):
        with self.lock:
            if not self.path.exists():
                return copy.deepcopy(DEFAULTS)
            if self.path.stat().st_size > 65536:
                raise ValueError("Connection settings file is invalid")
            return {**copy.deepcopy(DEFAULTS), **json.loads(self.path.read_text("utf-8"))}

    def _write(self, data):
        temporary = self.directory / (".connections-" + secrets.token_hex(6) + ".tmp")
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def save(self, body: ConnectionUpdate):
        with self.lock:
            data = self.load()
            update = body.model_dump()
            for key in SECRET_FIELDS:
                value = update.pop(key).strip()
                clear = update.pop("clear_" + key)
                if "\r" in value or "\n" in value:
                    raise ValueError("API credentials must be on one line")
                if clear:
                    data[key] = ""
                elif value:
                    data[key] = value
            update["public_url"] = public_origin(update["public_url"])
            update["boss_phone"] = re.sub(r"[ +()-]", "", update["boss_phone"])
            if update["boss_phone"] and not re.fullmatch(r"[1-9][0-9]{6,14}", update["boss_phone"]):
                raise ValueError("Boss phone needs country code and 7–15 digits")
            if update["wa_phone_id"] and not re.fullmatch(r"[0-9]{5,50}", update["wa_phone_id"]):
                raise ValueError("WhatsApp Phone Number ID must contain digits")
            data.update(update)
            if data["ai_enabled"] and not data["ai_key"]:
                raise ValueError("Save an OpenAI API key before enabling AI")
            if data["wa_enabled"]:
                missing = [key for key in ("wa_token", "wa_phone_id", "boss_phone", "public_url") if not data[key]]
                if data["wa_mode"] == "template" and not data["wa_template"]:
                    missing.append("wa_template")
                if missing:
                    raise ValueError("Complete phone notification settings: " + ", ".join(missing))
                if not data["phone_confirmed"]:
                    raise ValueError("Confirm the boss phone recipient before enabling notifications")
            self._write(data)
            return self.redacted(data)

    def set_tunnel_origin(self, value):
        value = public_origin(value)
        if not value.endswith(".trycloudflare.com"):
            raise ValueError("Unexpected quick tunnel origin")
        with self.lock:
            data = self.load()
            if data["public_url"] and not data["public_url"].endswith(".trycloudflare.com"):
                return False
            data["public_url"] = value
            self._write(data)
            return True

    @staticmethod
    def redacted(data):
        return {**{k: v for k, v in data.items() if k not in SECRET_FIELDS},
                "ai_key_saved": bool(data["ai_key"]), "wa_token_saved": bool(data["wa_token"])}

    def status(self):
        data = self.load()
        return {"ai_enabled": data["ai_enabled"], "ai_ready": bool(data["ai_enabled"] and data["ai_key"]),
                "phone_enabled": data["wa_enabled"],
                "phone_ready": bool(data["wa_enabled"] and all(data[k] for k in ("wa_token", "wa_phone_id", "boss_phone", "public_url")))}
