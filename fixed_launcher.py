"""Stable OAM launcher with battle callbacks registered directly on Dispatcher.

This intentionally does not monkey-patch run.callback after Dispatcher creation.
Battle callbacks are routed here first, while all other callbacks keep using run.py.
"""
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart

import achievements
import battle_force_sync
import run
from config import ADMIN_ID, BOT_TOKEN, OWNER_ID2
from db import connect, init_db
from settings import init_settings


async def callback(c, bot: Bot):
    data = c.data or ""

    if data == "battle_confirm":
        return await battle_force_sync.confirm(c, bot)

    if data.startswith("accept:"):
        try:
            attacker_id = int(data.split(":", 1)[1])
        except (ValueError, TypeError):
            return await c.answer("Некорректный запрос боя.", show_alert=True)
        return await battle_force_sync.accept(c, attacker_id, bot)

    if data.startswith("decline:"):
        try:
            attacker_id = int(data.split(":", 1)[1])
        except (ValueError, TypeError):
            return await c.answer("Некорректный запрос боя.", show_alert=True)
        return await battle_force_sync.decline(c, attacker_id, bot)

    return await run.callback(c, bot)


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty")

    await init_db()
    await init_settings(ADMIN_ID)

    db = await connect()
    try:
        await db.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (ADMIN_ID,))
        if OWNER_ID2:
            await db.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (OWNER_ID2,))
        await db.commit()
    finally:
        await db.close()

    await achievements.init_achievements()
    achievements.install_sync()

    tg = Bot(BOT_TOKEN)
    dp = Dispatcher()
    dp.message.register(run.start_wrapper, CommandStart())
    dp.message.register(run.text_handler, F.text)
    dp.callback_query.register(callback, F.data)

    print("[OAM] FIXED LAUNCHER ACTIVE")
    print("[OAM] battle_confirm / accept / decline are registered directly")
    print("[OAM] attacker and defender share one animation clock")
    await dp.start_polling(tg)


if __name__ == "__main__":
    asyncio.run(main())
