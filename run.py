import asyncio
import bot
import admin_panel_patch  # replaces the placeholder admin sections before Dispatcher registration

if __name__ == '__main__':
    asyncio.run(bot.main())
