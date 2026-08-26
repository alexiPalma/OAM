"""OAM master runtime fix.

This is the single runtime entrypoint used by working_launcher.py and
fixed_launcher.py. It keeps the existing feature modules intact, but makes
callback registration explicit so aiogram never calls a callback without Bot.
Battle callbacks are routed through battle_force_sync, where both players'
messages are advanced by the same animation clock and the result is sent only
after the final frame.
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
    """One callback entrypoint with the Bot dependency supplied by aiogram."""
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
        await db.execute(
            "INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (ADMIN_ID,)
        )
        if OWNER_ID2:
            await db.execute(
                "INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (OWNER_ID2,)
            )
        await db.commit()
    finally:
        await db.close()

    await achievements.init_achievements()
    achievements.install_sync()

    tg = Bot(BOT_TOKEN)
    dp = Dispatcher()

    # All normal handlers from run.py.
    dp.message.register(run.start_wrapper, CommandStart())
    dp.message.register(run.text_handler, F.text)

    # Exactly one callback dispatcher. Do not register run.callback separately.
    # This prevents the old callback(c) path from receiving a callback with a
    # missing Bot argument and keeps battle callbacks on the synchronized path.
    dp.callback_query.register(callback, F.data)

    print("[OAM] MASTER FIX ACTIVE")
    print("[OAM] working_launcher.py -> fix.py -> one Dispatcher")
    print("[OAM] battle animation: shared 15-second clock for both players")
    print("[OAM] battle result: shown to both only after the last animation frame")
    await dp.start_polling(tg)


if __name__ == "__main__":
    asyncio.run(main())
