"""Authoritative, non-masking shop callback patch.

The previous version caught every exception from a purchase and replaced the
real cause with a misleading stale-button message. This layer validates the
callback, delegates to the existing shop logic, and logs the real exception.
It does not change the shop UI.
"""
import traceback
import fix
import bot as app
from config import UNITS

_ORIGINAL = fix.callback


async def callback(c, bot):
    data = str(c.data or '')
    if data.startswith('buyq:'):
        unit = data.split(':', 1)[1]
        if unit not in UNITS:
            return await c.answer('Недоступно', show_alert=True)
        return await app.buyq(c, unit)

    if data.startswith('buyok:'):
        parts = data.split(':')
        if len(parts) != 3 or parts[1] not in UNITS:
            return await c.answer('❌ Некорректная покупка.', show_alert=True)
        try:
            quantity = int(parts[2])
        except (TypeError, ValueError):
            return await c.answer('❌ Некорректное количество.', show_alert=True)
        if quantity < 1 or quantity > 1_000_000:
            return await c.answer('Некорректное количество', show_alert=True)
        try:
            return await app.buy_confirm(c, parts[1], quantity)
        except Exception as exc:
            print(f'[OAM SHOP ERROR] callback={data!r}: {exc!r}')
            traceback.print_exc()
            try:
                await c.answer('❌ Ошибка покупки. Попробуйте ещё раз.', show_alert=True)
            except Exception:
                pass
            return None

    return await _ORIGINAL(c, bot)


fix.callback = callback
print('[OAM] SHOP CALLBACKS: DIRECT / NON-MASKING')
