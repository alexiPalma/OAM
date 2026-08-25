"""Artillery shop runtime patch."""
import bot as app
from config import UNITS


def install():
    original_shop = getattr(app, 'shop', None)
    if original_shop is not None and not getattr(original_shop, '_artillery_shop_patch', False):
        async def shop(c):
            items = '\n'.join(f'{v["title"]} — ${app.money(v["price"])}' for v in UNITS.values())
            rows = [[(f'{v["title"]} — ${app.money(v["price"])}', f'buyq:{k}')] for k, v in UNITS.items()]
            rows.append([('⬅️ Назад', 'home')])
            await app.safe(c, f'🛒 {app.BRAND} • ВОЕННЫЙ АРСЕНАЛ\n\n{items}\n\nВыберите единицу и введите количество.', app.kb(rows))
        shop._artillery_shop_patch = True
        app.shop = shop

    original_shop_message = getattr(app, 'shop_from_message', None)
    if original_shop_message is not None and not getattr(original_shop_message, '_artillery_shop_patch', False):
        async def shop_from_message(m):
            items = '\n'.join(f'{v["title"]} — ${app.money(v["price"])}' for v in UNITS.values())
            rows = [[(f'{v["title"]} — ${app.money(v["price"])}', f'buyq:{k}')] for k, v in UNITS.items()]
            rows.append([('⬅️ Назад', 'home')])
            await m.answer(f'🛒 {app.BRAND} • ВОЕННЫЙ АРСЕНАЛ\n\n{items}\n\nВыберите единицу.', reply_markup=app.kb(rows))
        shop_from_message._artillery_shop_patch = True
        app.shop_from_message = shop_from_message

    original_buyq = getattr(app, 'buyq', None)
    if original_buyq is not None and not getattr(original_buyq, '_artillery_shop_patch', False):
        async def buyq(c, k):
            if k not in UNITS:
                return await c.answer('Недоступно', show_alert=True)
            app.STATE[c.from_user.id] = ('buy', k)
            await app.safe(c, f'🛒 {UNITS[k]["title"]}\n\nЦена: ${app.money(UNITS[k]["price"])}\n\nВведите количество:', app.back('shop'))
        buyq._artillery_shop_patch = True
        app.buyq = buyq

install()
