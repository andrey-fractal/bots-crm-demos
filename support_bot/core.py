"""Логика бота поддержки: найти разделы базы знаний, ответить по ним или передать оператору."""
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import llm
from .rag import Index, load_kb

KB_DIR = Path(__file__).parent / "kb"
DB = Path(__file__).parent / "tickets.sqlite3"
MIN_SCORE = 1.5  # ниже — в базе знаний нет ничего похожего, сразу к оператору

SYSTEM = """Ты — бот поддержки службы доставки воды «Родник».
Отвечай ТОЛЬКО по фрагментам базы знаний из сообщения пользователя. Ничего не придумывай: цены, сроки и условия бери дословно.
Пиши коротко, по-русски, на «вы», 1–4 предложения, без markdown-разметки.
Последней строкой напиши SOURCE: и название фрагмента из квадратных скобок, по которому отвечал.
Если во фрагментах нет ответа — ответь ровно одним словом HANDOFF.
Если нужен человек (претензия, ремонт, просьба позвать оператора) — сначала коротко скажи, что делать клиенту по базе знаний, и закончи отдельной строкой HANDOFF."""

HANDOFF_TEXT = "Передал ваш вопрос оператору, номер обращения #{id}. Ответим в течение 15 минут в рабочее время (8:00–22:00)."


@dataclass
class Answer:
    text: str
    sources: list[str] = field(default_factory=list)
    handoff: bool = False
    ticket_id: int | None = None


class SupportBot:
    def __init__(self, kb_dir: Path = KB_DIR, db: Path = DB, complete=llm.complete):
        self.index = Index(load_kb(kb_dir))
        self.complete = complete
        self.db = sqlite3.connect(db, check_same_thread=False)
        self.db.execute("create table if not exists tickets(id integer primary key, user text, question text, created text)")

    def ask(self, question: str, user: str = "web") -> Answer:
        hits = self.index.search(question)
        if not hits or hits[0][0] < MIN_SCORE:
            return self._handoff(question, user)
        context = "\n\n".join(f"[{c.source}]\n{c.text}" for _, c in hits)
        reply = self.complete(SYSTEM, f"Фрагменты базы знаний:\n{context}\n\nВопрос клиента: {question}")
        handoff = "HANDOFF" in reply
        reply, _, used = reply.replace("HANDOFF", "").partition("SOURCE:")
        reply, used = reply.strip(), used.strip().strip("[]")
        sources = [c.source for _, c in hits if c.source == used] or [hits[0][1].source]
        if handoff:
            return self._handoff(question, user, reply, sources)
        return Answer(reply, sources)

    def _handoff(self, question: str, user: str, prefix: str = "", sources: list[str] | None = None) -> Answer:
        cur = self.db.execute("insert into tickets(user, question, created) values (?,?,?)",
                              (user, question, datetime.now().isoformat(timespec="seconds")))
        self.db.commit()
        text = HANDOFF_TEXT.format(id=cur.lastrowid)
        return Answer(f"{prefix}\n\n{text}" if prefix else text, (sources or []) if prefix else [], handoff=True, ticket_id=cur.lastrowid)
