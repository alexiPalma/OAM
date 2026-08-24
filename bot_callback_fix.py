"""Compatibility fix for aiogram callback handlers.

The current bot.py defines callback(c, bot). aiogram 3 can fail to inject the
second argument in some dispatcher configurations, which makes every inline
button fail before its handler runs. The main callback should use c.bot.

Apply these exact replacements in bot.py:
    async def callback(c,bot):
        -> async def callback(c):

    if d=='battle_confirm':return await battle_confirm(c,bot)
        -> if d=='battle_confirm':return await battle_confirm(c,c.bot)

    if d.startswith('accept:'):return await battle_accept(c,int(d.split(':',1)[1]),bot)
        -> if d.startswith('accept:'):return await battle_accept(c,int(d.split(':',1)[1]),c.bot)

    if d.startswith('decline:'):return await battle_decline(c,int(d.split(':',1)[1]),bot)
        -> if d.startswith('decline:'):return await battle_decline(c,int(d.split(':',1)[1]),c.bot)

Also change any callback handler that receives bot only for Telegram API calls to
use c.bot, or keep the bot parameter only in functions called explicitly with
c.bot. This file is a diagnostic/compatibility note and is intentionally not
registered as a second dispatcher handler.
"""
