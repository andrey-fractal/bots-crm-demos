"""Приёмник вебхуков CRM → уведомление в Telegram.

Запуск: TG_TOKEN=... TG_CHAT_ID=... uvicorn crm_notify.server:app --port 8001
Без TG_TOKEN уведомления не отправляются, а копятся в OUTBOX (для стенда и тестов).
"""
import os

import httpx
from fastapi import FastAPI, Request

from .events import parse_amo, parse_bitrix, render

app = FastAPI(title="CRM → Telegram")
OUTBOX: list[str] = []
SEEN: set[tuple[str, str, str]] = set()  # CRM повторяют вебхук при таймауте — не дублируем

AMO_USERS = {"8812345": "Алексей Петров"}  # id → имя; в проде подтягивается из /api/v4/users
AMO_STAGES = {"142": "Успешно реализовано", "143": "Закрыто и не реализовано", "61522": "Переговоры", "61523": "Счёт выставлен"}


def bitrix_deal(deal_id: str) -> dict:
    hook = os.getenv("BITRIX_WEBHOOK")  # https://<портал>.bitrix24.ru/rest/<user>/<token>
    if not hook:
        return DEMO_BITRIX_DEALS.get(deal_id, {})
    deal = httpx.get(f"{hook}/crm.deal.get.json", params={"id": deal_id}, timeout=10).raise_for_status().json()["result"]
    users = httpx.get(f"{hook}/user.get.json", params={"ID": deal["ASSIGNED_BY_ID"]}, timeout=10).raise_for_status().json()["result"]
    if users:
        deal["ASSIGNED_BY_NAME"] = f"{users[0].get('NAME', '')} {users[0].get('LAST_NAME', '')}".strip()
    return deal


DEMO_BITRIX_DEALS = {"512": {"TITLE": "Поставка кулеров в офис, ООО «Вектор»", "OPPORTUNITY": "86400.00",
                             "STAGE_ID": "NEW", "ASSIGNED_BY_ID": "7", "ASSIGNED_BY_NAME": "Ирина Смирнова"}}


def send(text: str) -> None:
    token, chat = os.getenv("TG_TOKEN"), os.getenv("TG_CHAT_ID")
    if not token:
        OUTBOX.append(text)
        return
    httpx.post(f"https://api.telegram.org/bot{token}/sendMessage",
               json={"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
               timeout=10).raise_for_status()


def handle(events) -> int:
    sent = 0
    for e in events:
        key = (e.crm, e.deal_id, e.kind + e.stage)
        if key in SEEN:
            continue
        SEEN.add(key)
        send(render(e))
        sent += 1
    return sent


@app.post("/webhook/amocrm")
async def amocrm(request: Request):
    return {"sent": handle(parse_amo((await request.body()).decode(), AMO_STAGES, AMO_USERS))}


@app.post("/webhook/bitrix24")
async def bitrix24(request: Request):
    return {"sent": handle(parse_bitrix((await request.body()).decode(), bitrix_deal))}
