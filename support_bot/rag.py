"""Поиск по базе знаний: markdown режется на разделы по заголовкам ##, ранжирование BM25."""
import math
import re
from dataclasses import dataclass
from pathlib import Path

WORD = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)
STOP = set("и в во на по за до от из к ко с со у о об а но или ли не ни что как это то же бы для при без".split())


def tokens(text: str) -> list[str]:
    # грубый стемминг: первые 5 букв слова ловят «бутыль/бутыли/бутылей»
    return [w[:5] for w in (m.lower() for m in WORD.findall(text)) if w not in STOP]


@dataclass
class Chunk:
    source: str   # файл и раздел: «dostavka.md › Стоимость доставки»
    text: str


def load_kb(kb_dir: Path) -> list[Chunk]:
    chunks = []
    for path in sorted(kb_dir.glob("*.md")):
        title, section, lines = "", "", []
        for line in path.read_text(encoding="utf-8").splitlines() + ["## "]:
            if line.startswith("# "):
                title = line[2:].strip()
            elif line.startswith("## "):
                if section and lines:
                    chunks.append(Chunk(f"{title} › {section}", "\n".join(lines).strip()))
                section, lines = line[3:].strip(), []
            elif line.strip():
                lines.append(line)
    return chunks


class Index:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.docs = [tokens(c.source + " " + c.text) for c in chunks]
        self.avg = sum(map(len, self.docs)) / len(self.docs)
        self.k1, self.b = k1, b
        df: dict[str, int] = {}
        for d in self.docs:
            for t in set(d):
                df[t] = df.get(t, 0) + 1
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, top: int = 3) -> list[tuple[float, Chunk]]:
        q = tokens(query)
        scored = []
        for doc, chunk in zip(self.docs, self.chunks):
            s = 0.0
            for t in q:
                tf = doc.count(t)
                if tf:
                    s += self.idf[t] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * len(doc) / self.avg))
            if s > 0:
                scored.append((s, chunk))
        return sorted(scored, key=lambda x: -x[0])[:top]
