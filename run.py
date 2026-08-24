import asyncio
import bot
import runtime_fix
import hotfix_2026_08_24

# Install the layers once, in a deterministic order.
runtime_fix.install()
hotfix_2026_08_24.install()

if __name__ == '__main__':
    asyncio.run(bot.main())
