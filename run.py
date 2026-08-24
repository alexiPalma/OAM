import asyncio
import bot
from battle_runtime import install

install(bot)

if __name__ == '__main__':
    asyncio.run(bot.main())
