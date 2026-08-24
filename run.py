import asyncio
import bot
import runtime_fix
import hotfix_2026_08_24
import achievements
import achievement_priority

# Install deterministic layers before starting polling.
runtime_fix.install()
hotfix_2026_08_24.install()

async def _install_achievements():
    await achievements.init_achievements()
    achievements.install_sync()
    achievement_priority.install()

if __name__ == '__main__':
    asyncio.run(_install_achievements())
    asyncio.run(bot.main())
