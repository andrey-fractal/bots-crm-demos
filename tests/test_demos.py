from fastapi.testclient import TestClient

from crm_notify import server
from crm_notify.events import parse_amo, parse_bitrix, render
from leads_bot.core import LeadDialog, normalize_phone
from support_bot.core import SupportBot

AMO_ADD = ("leads%5Badd%5D%5B0%5D%5Bid%5D=24101&leads%5Badd%5D%5B0%5D%5Bname%5D=%D0%9E%D1%84%D0%B8%D1%81+%D0%BD%D0%B0+%D0%A2%D0%B2%D0%B5%D1%80%D1%81%D0%BA%D0%BE%D0%B9"
           "&leads%5Badd%5D%5B0%5D%5Bprice%5D=42000&account%5Bsubdomain%5D=rodnik")


def test_amo_add_parsed_and_rendered():
    [e] = parse_amo(AMO_ADD)
    assert (e.kind, e.deal_id, e.title, e.amount) == ("Новая сделка", "24101", "Офис на Тверской", 42000)
    text = render(e)
    assert "42 000 ₽" in text and "rodnik.amocrm.ru/leads/detail/24101" in text


def test_bitrix_fetches_deal_by_id():
    body = "event=ONCRMDEALADD&data%5BFIELDS%5D%5BID%5D=512&auth%5Bdomain%5D=rodnik.bitrix24.ru"
    [e] = parse_bitrix(body, lambda i: {"TITLE": "Кулеры", "OPPORTUNITY": "86400.00", "STAGE_ID": "NEW"})
    assert (e.deal_id, e.amount, e.stage) == ("512", 86400, "Новая")


def test_webhook_retry_is_not_duplicated():
    server.OUTBOX.clear(); server.SEEN.clear()
    c = TestClient(server.app)
    for _ in range(2):
        c.post("/webhook/amocrm", content=AMO_ADD, headers={"content-type": "application/x-www-form-urlencoded"})
    assert len(server.OUTBOX) == 1


def test_phone_normalization():
    assert normalize_phone("8 (916) 123-45-67") == "+7 916 123-45-67"
    assert normalize_phone("+79161234567") == "+7 916 123-45-67"
    assert normalize_phone("12345") is None


def test_lead_dialog_happy_path():
    got = []
    d = LeadDialog(lambda lead: got.append(lead) or 1)
    for msg in ["/start", "Ольга", "Аренда кулера", "89161234567", "Без комментария"]:
        d.handle(msg)
    r = d.handle("Отправить")
    assert "№1" in r.text and got[0].phone == "+7 916 123-45-67" and got[0].comment == ""


def test_lead_dialog_rejects_bad_phone():
    d = LeadDialog(lambda lead: 1)
    for msg in ["/start", "Ольга", "Аренда кулера"]:
        d.handle(msg)
    assert "Не похоже" in d.handle("позвоните мне").text


def test_support_answers_from_kb_and_hands_off(tmp_path):
    seen = {}

    def fake_llm(system, user):
        seen["ctx"] = user
        return "Доставка одной бутыли — 250 ₽."

    bot = SupportBot(db=tmp_path / "t.db", complete=fake_llm)
    a = bot.ask("Сколько стоит доставка одной бутыли?")
    assert not a.handoff and "250 ₽" in seen["ctx"]
    assert bot.ask("Какой у вас ИНН директора?").handoff is True
