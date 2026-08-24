import asyncio
import bot
import runtime_fix
import hotfix_2026_08_24
import achievements
import achievement_priority
import callback_compat

# Install deterministic layers before starting polling.
runtime_fix.install()
hotfix_2026_08_24.install()

async def _install_achievements():
    await achievements.init_achievements()
    achievements.install_sync()
    achievement_priority.install()

if __name__ == '__main__':
    asyncio.run(_install_achievements())
    # aiogram 3 supplies only CallbackQuery to callback handlers. The
    # compatibility layer adapts the legacy two-argument handlers and also
    # routes achievement callbacks safely.
    callback_compat.install()
    asyncio.run(bot.main())
