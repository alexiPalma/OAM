"""Compatibility layer for aiogram 3 callback handlers.

The project historically used callbacks with (callback, bot), while
Dispatcher supplies the CallbackQuery event itself. This adapter keeps the
existing legacy handlers working without exposing a second positional
argument to aiogram.
"""
import bot as app
import achievements
import runtime_fix


def install():
    async def callback(c):
        data = c.data or ""

        # Achievement callbacks are handled here because bot.main() creates
        # its Dispatcher locally, so achievements cannot register directly on
        # that dispatcher during module initialization.
        if data == "achievements":
            return await achievements.menu(c)
        if data.startswith("ach:"):
            return await achievements.detail(c, data.split(":", 1)[1])
        if data.startswith("ach_claim:"):
            return await achievements.claim(c, data.split(":", 1)[1])

        # runtime_fix.callback is the active project callback handler and
        # expects the legacy second argument. Supply it explicitly here.
        return await runtime_fix.callback(c, c.bot)

    app.callback = callback
