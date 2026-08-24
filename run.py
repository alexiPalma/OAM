import asyncio
import bot
from battle_runtime import install as install_battle
from profile_patch import install as install_profile

install_battle(bot)
install_profile(bot)

if __name__ == '__main__':
    asyncio.run(bot.main())
