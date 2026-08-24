import asyncio
import bot
import runtime_fix
import hotfix_2026_08_24
import hotfix_final

runtime_fix.install()
hotfix_2026_08_24.install()
hotfix_final.install()

if __name__ == '__main__':
    asyncio.run(bot.main())
