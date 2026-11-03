"""Диалог приёма заявки как конечный автомат: не зависит от мессенджера, одинаково работает в Telegram, MAX и на сайте."""
import re
from dataclasses import dataclass, field

SERVICES = ["Доставка воды в офис", "Аренда кулера", "Разовая доставка домой"]
PHONE = re.compile(r"^\+?[78]?[\s\-()]*(\d[\s\-()]*){10}$")


@dataclass
class Reply:
    text: str
    buttons: list[str] = field(default_factory=list)


@dataclass
class Lead:
    name: str = ""
    service: str = ""
    phone: str = ""
    comment: str = ""


def normalize_phone(raw: str) -> str | None:
    if not PHONE.match(raw.strip()):
        return None
    digits = re.sub(r"\D", "", raw)[-10:]
    return f"+7 {digits[:3]} {digits[3:6]}-{digits[6:8]}-{digits[8:]}"


class LeadDialog:
    """Шаги: имя → услуга → телефон → комментарий → подтверждение. submit(lead) вызывается после «Отправить»."""

    def __init__(self, submit):
        self.submit = submit
        self.step = "start"
        self.lead = Lead()

    def handle(self, text: str) -> Reply:
        text = text.strip()
        if text in ("/start", "Начать заново"):
            self.step, self.lead = "name", Lead()
            return Reply("Здравствуйте! Оставьте заявку — менеджер перезвонит в течение 15 минут.\nКак к вам обращаться?")
        step = getattr(self, f"_{self.step}", None)
        return step(text) if step else self.handle("/start")

    def _name(self, text):
        if len(text) < 2:
            return Reply("Напишите, пожалуйста, имя.")
        self.lead.name, self.step = text, "service"
        return Reply(f"{text}, что вас интересует?", SERVICES)

    def _service(self, text):
        if text not in SERVICES:
            return Reply("Выберите вариант кнопкой ниже.", SERVICES)
        self.lead.service, self.step = text, "phone"
        return Reply("Ваш номер телефона?")

    def _phone(self, text):
        phone = normalize_phone(text)
        if not phone:
            return Reply("Не похоже на номер. Пример: +7 916 123-45-67")
        self.lead.phone, self.step = phone, "comment"
        return Reply("Есть пожелания? Адрес, количество бутылей, удобное время звонка.", ["Без комментария"])

    def _comment(self, text):
        self.lead.comment = "" if text == "Без комментария" else text
        self.step = "confirm"
        l = self.lead
        summary = f"Проверьте заявку:\n{l.name}, {l.phone}\n{l.service}" + (f"\n{l.comment}" if l.comment else "")
        return Reply(summary, ["Отправить", "Начать заново"])

    def _confirm(self, text):
        if text != "Отправить":
            return Reply("Нажмите «Отправить» или «Начать заново».", ["Отправить", "Начать заново"])
        lead_id = self.submit(self.lead)
        self.step = "done"
        return Reply(f"Заявка №{lead_id} принята. Менеджер перезвонит в течение 15 минут.", ["Начать заново"])

    def _done(self, text):
        return Reply("Заявка уже отправлена. Хотите оставить ещё одну?", ["Начать заново"])
