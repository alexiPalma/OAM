"""Callback compatibility/recovery layer.

Some Telegram messages can outlive a runtime update: their inline buttons
still contain callback_data from an older version of the bot.  The old
runtime displayed the misleading "Кнопка не найдена." alert for those
callbacks.  Keep all current callbacks untouched, support a couple of legacy
purchase prefixes, and make genuinely stale callbacks fail quietly with a
useful message instead of the old error.
"""
import bot

_ORIGINAL = bot.callback


def _legacy_purchase(data):
    if data.startswith('buy:'):
        return data.split(':', 1)[1]
    if data.startswith('buy_unit:'):
        return data.split(':', 1)[1]
    return None


async def callback(c, tg_bot):
    data = c.data or ''
    legacy_unit = _legacy_purchase(data)
    if legacy_unit:
        # Old shop keyboards used buy:/buy_unit:. Convert them to the current
        # buyq flow instead of falling through to "button not found".
        return await bot.buyq(c, legacy_unit)

    try:
        return await _ORIGINAL(c, tg_bot)
    except Exception as exc:
        print(f'[OAM CALLBACK] handler error data={data!r}: {exc}')
        try:
            await c.answer('⚠️ Эта кнопка устарела. Откройте меню заново.', show_alert=True)
        except Exception:
            pass


bot.callback = callback
print('[OAM] CALLBACK COMPATIBILITY: ON')
