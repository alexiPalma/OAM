import asyncio
import bot
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from battle_runtime import install as install_battle
from profile_patch import install as install_profile

# Apply runtime fixes BEFORE registering handlers.
# The old run.py called bot.main(), which registered the original callback
# before these replacements could be used by aiogram.
install_battle(bot)
install_profile(bot)

async def main():
    if not bot.BOT_TOKEN:
        raise RuntimeError('BOT_TOKEN is empty')
    await bot.init_db()
    await bot.init_settings(bot.ADMIN_ID)
    db = await bot.connect()
    await db.execute('INSERT OR IGNORE INTO admins(user_id) VALUES(?)', (bot.ADMIN_ID,))
    await db.commit()
    await db.close()

    tg = Bot(bot.BOT_TOKEN)
    dp = Dispatcher()
    dp.message.register(bot.start, CommandStart())
    dp.message.register(bot.text_handler, F.text)
    dp.callback_query.register(bot.callback, F.data)

    print('WorldWarDynasty started with runtime battle/bonus fixes')
    await dp.start_polling(tg)

if __name__ == '__main__':
    asyncio.run(main())
