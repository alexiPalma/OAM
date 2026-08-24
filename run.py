import asyncio
import bot
import runtime_fix

runtime_fix.install()

if __name__ == '__main__':
    asyncio.run(bot.main())
