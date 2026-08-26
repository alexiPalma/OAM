"""Final callback safety layer.

A Telegram inline button can outlive the code that created it.  The old
runtime could then leave the callback unanswered or show the misleading
"Кнопка не найдена." message.  This guard sits on the ACTUAL fix.py callback
that the dispatcher registers, so every callback gets an answer even when a
stale/legacy callback reaches the bot.
"""
import fix
import bot as app

_ORIGINAL = fix.callback


async def callback(c, bot):
    data = str(c.data or '')
    try:
        result = await _ORIGINAL(c, bot)
        # A callback must always be acknowledged.  If the underlying handler
        # already answered it, Telegram will reject the duplicate and we ignore
        # that harmless error.
        try:
            await c.answer()
        except Exception:
            pass
        return result
    except Exception as exc:
        print(f'[OAM CALLBACK GUARD] recovered data={data!r}: {exc}')
        # Never expose a raw "button not found"/stale callback error to the
        # player.  Return the user to their own menu instead.
        try:
            u = await app.user(c.from_user.id)
            if u:
                await app.safe(c, f'⚔️ {app.BRAND}\n\n💵 Баланс: ${app.money(u["balance"])}\n🏭 Ферма: {u["farm_level"]}/10\n\n🛰 Центр управления войсками:', app.home_kb(await app.admin(c.from_user.id)))
            else:
                await c.answer('⚠️ Меню устарело. Откройте меню заново.')
        except Exception:
            try:
                await c.answer('⚠️ Меню устарело. Откройте меню заново.')
            except Exception:
                pass
        return None


fix.callback = callback
print('[OAM] CALLBACK GUARD: ON')
