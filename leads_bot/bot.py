"""Telegram-адаптер к LeadDialog. Запуск: BOT_TOKEN=... MANAGER_CHAT_ID=... python -m leads_bot.bot"""
import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from .amocrm import crm_from_env, manager_text
from .core import LeadDialog, Reply

dp = Dispatcher()
crm = crm_from_env()
dialogs: dict[int, LeadDialog] = {}


def keyboard(r: Reply):
    if not r.buttons:
        return ReplyKeyboardRemove()
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=b)] for b in r.buttons], resize_keyboard=True)


@dp.message(F.text)
async def on_text(m: Message, bot: Bot):
    async def notify(text):
        if os.getenv("MANAGER_CHAT_ID"):
            await bot.send_message(os.environ["MANAGER_CHAT_ID"], text)

    def submit(lead):
        lead_id = crm.create_lead(lead)
        asyncio.get_running_loop().create_task(notify(manager_text(lead_id, lead)))
        return lead_id

    dialog = dialogs.setdefault(m.from_user.id, LeadDialog(submit))
    reply = dialog.handle(m.text)
    await m.answer(reply.text, reply_markup=keyboard(reply))


async def main():
    await dp.start_polling(Bot(os.environ["BOT_TOKEN"]))


if __name__ == "__main__":
    asyncio.run(main())
