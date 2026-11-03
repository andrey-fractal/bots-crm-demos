"""Разбор вебхуков amoCRM и Bitrix24 в одно событие и текст уведомления."""
from dataclasses import dataclass
from urllib.parse import parse_qsl

AMO_ACTIONS = {"add": "Новая сделка", "status": "Сделка сменила этап", "update": "Сделка изменена"}
BITRIX_STAGES = {"NEW": "Новая", "PREPARATION": "Подготовка документов", "PREPAYMENT_INVOICE": "Счёт на предоплату",
                 "EXECUTING": "В работе", "WON": "Сделка успешна", "LOSE": "Сделка провалена"}
BITRIX_EVENTS = {"ONCRMDEALADD": "Новая сделка", "ONCRMDEALUPDATE": "Сделка изменена", "ONCRMLEADADD": "Новый лид"}


@dataclass
class Event:
    crm: str
    kind: str
    deal_id: str
    title: str = ""
    amount: int | None = None
    stage: str = ""
    responsible: str = ""
    url: str = ""


def parse_amo(body: str, stages: dict[str, str] | None = None, users: dict[str, str] | None = None) -> list[Event]:
    """amoCRM шлёт form-urlencoded: leads[add][0][id]=1&leads[add][0][name]=...&account[subdomain]=..."""
    flat = dict(parse_qsl(body))
    sub = flat.get("account[subdomain]", "")
    found: dict[tuple[str, str], dict[str, str]] = {}
    for key, value in flat.items():
        parts = key.replace("]", "").split("[")
        if len(parts) == 4 and parts[0] == "leads":
            _, action, idx, fld = parts
            found.setdefault((action, idx), {})[fld] = value
    events = []
    for (action, _), f in found.items():
        events.append(Event(
            crm="amoCRM", kind=AMO_ACTIONS.get(action, action), deal_id=f.get("id", ""),
            title=f.get("name", ""), amount=int(f["price"]) if f.get("price") else None,
            stage=(stages or {}).get(f.get("status_id", ""), ""), responsible=(users or {}).get(f.get("responsible_user_id", ""), ""),
            url=f"https://{sub}.amocrm.ru/leads/detail/{f.get('id')}" if sub else "",
        ))
    return events


def parse_bitrix(body: str, fetch_deal=None) -> list[Event]:
    """Bitrix24 присылает только event и ID; поля сделки дозапрашиваются через REST crm.deal.get."""
    flat = dict(parse_qsl(body))
    event = flat.get("event", "")
    deal_id = flat.get("data[FIELDS][ID]", "")
    if event not in BITRIX_EVENTS or not deal_id:
        return []
    deal = fetch_deal(deal_id) if fetch_deal else {}
    domain = flat.get("auth[domain]", "")
    return [Event(
        crm="Bitrix24", kind=BITRIX_EVENTS[event], deal_id=deal_id, title=deal.get("TITLE", ""),
        amount=int(float(deal["OPPORTUNITY"])) if deal.get("OPPORTUNITY") else None,
        stage=BITRIX_STAGES.get(deal.get("STAGE_ID", ""), deal.get("STAGE_ID", "")), responsible=deal.get("ASSIGNED_BY_NAME", ""),
        url=f"https://{domain}/crm/deal/details/{deal_id}/" if domain else "",
    )]


def money(n: int) -> str:
    return f"{n:,}".replace(",", " ") + " ₽"


def render(e: Event) -> str:
    """HTML для Telegram (parse_mode=HTML)."""
    lines = [f"<b>{e.kind}</b> · {e.crm}", f"№{e.deal_id} {e.title}".strip()]
    if e.amount is not None:
        lines.append(f"Сумма: {money(e.amount)}")
    if e.stage:
        lines.append(f"Этап: {e.stage}")
    if e.responsible:
        lines.append(f"Ответственный: {e.responsible}")
    if e.url:
        lines.append(f'<a href="{e.url}">Открыть в CRM</a>')
    return "\n".join(lines)
