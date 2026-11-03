"""Telegram-адаптер. Запуск: BOT_TOKEN=... OPERATOR_CHAT_ID=... python -m support_bot.bot"""
import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from .core import SupportBot

dp = Dispatcher()
support = SupportBot()


@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("Здравствуйте! Я бот поддержки «Родник». Спросите про доставку, оплату, залог или кулеры.")


@dp.message(F.text)
async def question(m: Message, bot: Bot):
    await bot.send_chat_action(m.chat.id, "typing")
    ans = await asyncio.to_thread(support.ask, m.text, str(m.from_user.id))
    await m.answer(ans.text)
    operator = os.getenv("OPERATOR_CHAT_ID")
    if ans.handoff and operator:
        await bot.send_message(operator, f"Обращение #{ans.ticket_id} от @{m.from_user.username or m.from_user.id}:\n{m.text}")


async def main():
    await dp.start_polling(Bot(os.environ["BOT_TOKEN"]))


if __name__ == "__main__":
    asyncio.run(main())
