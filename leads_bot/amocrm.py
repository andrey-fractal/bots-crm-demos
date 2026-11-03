"""Создание сделки с контактом в amoCRM (API v4, POST /api/v4/leads/complex) и уведомление менеджера."""
import os
import sqlite3
from datetime import datetime
from pathlib import Path

import httpx

from .core import Lead


class AmoCRM:
    def __init__(self, subdomain: str, token: str, pipeline_id: int | None = None):
        self.base = f"https://{subdomain}.amocrm.ru/api/v4"
        self.headers = {"Authorization": f"Bearer {token}"}
        self.pipeline_id = pipeline_id

    def create_lead(self, lead: Lead) -> int:
        body = [{
            "name": f"{lead.service} — {lead.name}",
            **({"pipeline_id": self.pipeline_id} if self.pipeline_id else {}),
            "_embedded": {
                "tags": [{"name": "telegram-бот"}],
                "contacts": [{
                    "first_name": lead.name,
                    "custom_fields_values": [{"field_code": "PHONE", "values": [{"value": lead.phone, "enum_code": "MOB"}]}],
                }],
            },
        }]
        r = httpx.post(f"{self.base}/leads/complex", json=body, headers=self.headers, timeout=15)
        r.raise_for_status()
        lead_id = r.json()[0]["id"]
        if lead.comment:
            httpx.post(f"{self.base}/leads/{lead_id}/notes", headers=self.headers, timeout=15,
                       json=[{"note_type": "common", "params": {"text": lead.comment}}]).raise_for_status()
        return lead_id


class LocalCRM:
    """Замена amoCRM без ключей: те же данные пишутся в SQLite. Для стенда и тестов."""

    def __init__(self, path: Path = Path(__file__).parent / "leads.sqlite3"):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("create table if not exists leads(id integer primary key, name text, service text, phone text, comment text, created text)")

    def create_lead(self, lead: Lead) -> int:
        cur = self.db.execute("insert into leads(name, service, phone, comment, created) values (?,?,?,?,?)",
                              (lead.name, lead.service, lead.phone, lead.comment, datetime.now().isoformat(timespec="seconds")))
        self.db.commit()
        return 10400 + cur.lastrowid


def crm_from_env():
    if os.getenv("AMO_TOKEN"):
        return AmoCRM(os.environ["AMO_SUBDOMAIN"], os.environ["AMO_TOKEN"], int(os.getenv("AMO_PIPELINE_ID", 0)) or None)
    return LocalCRM()


def manager_text(lead_id: int, lead: Lead) -> str:
    return (f"🔔 Новая заявка №{lead_id}\n{lead.name}, {lead.phone}\n{lead.service}"
            + (f"\n💬 {lead.comment}" if lead.comment else "") + "\nСделка создана в CRM, позвоните в течение 15 минут.")
