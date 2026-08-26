"""Authoritative shop callback patch.

The live dispatcher goes through fix.callback -> run.callback -> bot.callback.
Some legacy compatibility layers were catching purchase exceptions and turning
them into the misleading "button is outdated" alert. Handle the current shop
callbacks directly at the authoritative fix layer.
"""
import fix
import bot as app

_ORIGINAL = fix.callback


async def callback(c, tg_bot):
    data = str(c.data or '')
    try:
        if data.startswith('buyq:'):
            return await app.buyq(c, data.split(':', 1)[1])
        if data.startswith('buyok:'):
            parts = data.split(':')
            if len(parts) != 3:
                return await c.answer('❌ Некорректная покупка.', show_alert=True)
            try:
                quantity = int(parts[2])
            except ValueError:
                return await c.answer('❌ Некорректное количество.', show_alert=True)
            return await app.buy_confirm(c, parts[1], quantity)
    except Exception as exc:
        print(f'[OAM SHOP PATCH] callback={data!r} error={exc!r}')
        try:
            await c.answer('❌ Ошибка покупки. Попробуйте открыть Арсенал заново.', show_alert=True)
        except Exception:
            pass
        return None
    return await _ORIGINAL(c, tg_bot)


fix.callback = callback
print('[OAM] SHOP CALLBACKS: DIRECT')
