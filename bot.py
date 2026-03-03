import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import database as db
from config import BOT_TOKEN
from handlers import admin, business, menu, payments, start
from keep_alive import start_keep_alive

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


async def main():
    await start_keep_alive()
    await db.init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(payments.router)
    dp.include_router(admin.router)
    dp.include_router(business.router)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await db.close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
