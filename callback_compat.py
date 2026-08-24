"""Final callback adapter for aiogram 3.

The project has several callback layers (runtime, hotfixes, battles and
achievements). aiogram invokes a callback handler with one CallbackQuery
argument. This adapter keeps that public signature while forwarding every
non-achievement callback to the complete callback chain installed before it.
"""
import bot as app
import achievements


def install():
    # Capture the callback that exists after all runtime/hotfix layers have
    # been installed. Do not call runtime_fix.callback directly here: that
    # would bypass later hotfix layers (notably battle callbacks).
    previous_callback = app.callback

    async def callback(c):
        data = c.data or ""

        if data == "achievements":
            return await achievements.menu(c)
        if data.startswith("ach:"):
            return await achievements.detail(c, data.split(":", 1)[1])
        if data.startswith("ach_claim:"):
            return await achievements.claim(c, data.split(":", 1)[1])

        # Preserve the complete callback chain installed by runtime_fix and
        # later hotfix/battle layers.
        return await previous_callback(c, c.bot)

    app.callback = callback
