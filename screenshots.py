"""Снимает скриншоты веб-стенда (сервер должен быть запущен на :8000). Браузер — установленный Edge."""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path(__file__).resolve().parent.parent / "covers"

SCENARIOS = {
    "demo_support.png": ("support", """
        for (const q of ['Сколько стоит доставка одной бутыли?', 'Вернут ли залог за бутыль с трещиной?',
                         'В воде осадок, привезли вчера. Что делать?']) await ask(q);"""),
    "demo_crm.png": ("crm", """
        for (const s of ['amo_add', 'amo_status', 'bitrix_add']) {
            document.querySelector(`[data-s=${s}]`).click(); await new Promise(r => setTimeout(r, 400)); }"""),
    "demo_leads.png": ("leads", """
        await new Promise(r => setTimeout(r, 300));
        for (const t of ['Ольга', 'Доставка воды в офис', '8 916 123 45 67', 'Офис на Тверской, 8 бутылей в неделю', 'Отправить']) {
            await say(t); await new Promise(r => setTimeout(r, 200)); }"""),
}


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge")
        page = await browser.new_page(viewport={"width": 920, "height": 740}, device_scale_factor=2)
        for name, (path, script) in SCENARIOS.items():
            await page.goto(f"http://localhost:8000/{path}")
            await page.evaluate(f"(async () => {{ {script} }})()")
            await page.wait_for_timeout(500)
            await page.evaluate("document.querySelectorAll('.chat').forEach(c => c.scrollTop = 1e9)")
            await page.screenshot(path=OUT / name)
            print("saved", name)
        await browser.close()


asyncio.run(main())
