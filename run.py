import asyncio
import bot
import runtime_fix
import hotfix_2026_08_24
import achievements
import achievement_priority
import callback_compat

# Install the base runtime layer first.
runtime_fix.install()
# Freeze this layer before later wrappers replace bot.callback. The final
# dispatcher uses this stable reference and can therefore never call itself.
bot._runtime_callback = bot.callback

hotfix_2026_08_24.install()

async def _install_achievements():
    await achievements.init_achievements()
    achievements.install_sync()
    achievement_priority.install()

if __name__ == '__main__':
    asyncio.run(_install_achievements())
    callback_compat.install()
    asyncio.run(bot.main())
