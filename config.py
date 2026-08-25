import os
import sys
import importlib.abc
import importlib.machinery
import contextvars
import functools
from urllib.parse import urlparse

from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN', '')
OWNER_ID = int(os.getenv('OWNER_ID') or os.getenv('ADMIN_ID') or '0')
OWNER_ID2 = int(os.getenv('OWNER_ID2') or '0')
OWNER_IDS = tuple(x for x in (OWNER_ID, OWNER_ID2) if x)
ADMIN_ID = OWNER_ID
DB_PATH = os.getenv('DB_PATH', 'voennabot.db')

FARMS = {
    0: {'income': 0, 'upgrade': 500_000},
    1: {'income': 15_000, 'upgrade': 500_000},
    2: {'income': 36_000, 'upgrade': 900_000},
    3: {'income': 50_000, 'upgrade': 1_000_000},
    4: {'income': 50_000, 'upgrade': 2_000_000},
    5: {'income': 100_000, 'upgrade': 3_000_000},
    6: {'income': 140_000, 'upgrade': 6_000_000},
    7: {'income': 220_000, 'upgrade': 9_000_000},
    8: {'income': 333_000, 'upgrade': 11_000_000},
    9: {'income': 777_000, 'upgrade': 18_000_000},
    10: {'income': 899_000, 'upgrade': 30_000_000},
}

UNITS = {
    'soldier': {'id': 1, 'title': '🪖 Пехота', 'price': 20_000, 'loss': 1_000, 'rating': 1},
    'interceptor': {'id': 2, 'title': '🎯 Дрон-перехватчик', 'price': 9_000, 'loss': 4_000, 'rating': 1},
    'drone': {'id': 3, 'title': '🛩 БПЛА', 'price': 120_000, 'loss': 20_000, 'rating': 3},
    'bmp': {'id': 4, 'title': '🚙 БМП', 'price': 1_000_000, 'loss': 55_000, 'rating': 7},
    'artillery': {'id': 9, 'title': '💥 Артиллерия', 'price': 2_500_000, 'loss': 250_000, 'rating': 8},
    'tank': {'id': 5, 'title': '🛡 Танк', 'price': 3_000_000, 'loss': 100_000, 'rating': 10},
    'helicopter': {'id': 6, 'title': '🚁 Вертолёт', 'price': 4_000_000, 'loss': 100_000, 'rating': 15},
    'plane': {'id': 7, 'title': '✈️ Самолёт', 'price': 6_000_000, 'loss': 500_000, 'rating': 25},
    'missile': {'id': 8, 'title': '🚀 Ракета', 'price': 20_000_000, 'loss': 1_000_000, 'rating': 50},
}
UNIT_BY_ID = {v['id']: k for k, v in UNITS.items()}
DONATIONS = {50: 5_000_000, 100: 11_000_000, 500: 100_000_000}
DAILY_BONUS_PRIZES = [
    (49.0, 'money', 100_000, '$100 000'),
    (20.0, 'interceptor', 10, '10 перехватчиков'),
    (10.0, 'drone', 2, '2 БПЛА'),
    (5.0, 'bmp', 1, 'БМП'),
    (5.0, 'drone', 10, '10 БПЛА'),
    (4.9, 'interceptor', 50, '50 перехватчиков'),
    (2.5, 'tank', 1, 'танк'),
    (2.5, 'money', 300_000, '$300 000'),
    (0.9, 'case1', 1, '📦 кейс №1'),
    (0.1, 'case2', 1, '📦 кейс №2'),
]

_GROUP_RENDER_USER = contextvars.ContextVar('wwd_group_render_user', default=None)
_GROUP_PREFIX = '__wwd_user__:'


class _RunFixLoader(importlib.abc.Loader):
    def __init__(self, loader):
        self.loader = loader

    def create_module(self, spec):
        fn = getattr(self.loader, 'create_module', None)
        return fn(spec) if fn else None

    def exec_module(self, module):
        self.loader.exec_module(module)
        _patch_run(module)


class _RunFixFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname != 'run':
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec and spec.loader and not isinstance(spec.loader, _RunFixLoader):
            spec.loader = _RunFixLoader(spec.loader)
        return spec


def _admin(uid, app):
    try:
        return uid in OWNER_IDS or bool(app.admin(uid))
    except Exception:
        return uid in OWNER_IDS


def _prefix_rows(rows, owner):
    if not owner:
        return rows
    result = []
    for row in rows:
        new_row = []
        for item in row:
            if not isinstance(item, (tuple, list)) or len(item) != 2:
                new_row.append(item)
                continue
            text, data = item
            data = str(data)
            if data.startswith(_GROUP_PREFIX) or data.startswith('accept:') or data.startswith('decline:'):
                new_row.append((text, data))
            else:
                new_row.append((text, f'{_GROUP_PREFIX}{owner}:{data}'))
        result.append(new_row)
    return result


def _patch_bot(app, run):
    if getattr(app, '_wwd_bot_final_patch', False):
        return
    app._wwd_bot_final_patch = True

    original_kb = app.kb

    def scoped_kb(rows):
        return original_kb(_prefix_rows(rows, _GROUP_RENDER_USER.get()))

    app.kb = scoped_kb

    def render_context(uid):
        return _GROUP_RENDER_USER.set(uid if uid else None)

    def restore_context(token):
        try:
            _GROUP_RENDER_USER.reset(token)
        except Exception:
            pass

    async def scoped_start(message, *args, **kwargs):
        token = render_context(message.from_user.id if getattr(message, 'chat', None) and message.chat.type != 'private' else None)
        try:
            return await original_start(message, *args, **kwargs)
        finally:
            restore_context(token)

    original_start = getattr(app, 'start', None)
    if original_start:
        app.start = scoped_start

    original_text_handler = getattr(app, 'text_handler', None)
    if original_text_handler:
        @functools.wraps(original_text_handler)
        async def scoped_text_handler(message, bot, *args, **kwargs):
            token = render_context(message.from_user.id if getattr(message, 'chat', None) and message.chat.type != 'private' else None)
            try:
                return await original_text_handler(message, bot, *args, **kwargs)
            finally:
                restore_context(token)
        app.text_handler = scoped_text_handler

    async def fixed_shop(c):
        rows = [[(f'{v["title"]} — ${app.money(v["price"])}', f'buyq:{k}')] for k, v in UNITS.items()]
        rows.append([('⬅️ Назад', 'home')])
        text = '🛒 ' + app.BRAND + ' • ВОЕННЫЙ АРСЕНАЛ\n\n'
        text += '\n'.join(f'{v["title"]} — ${app.money(v["price"])}' for v in UNITS.values())
        text += '\n\nВыберите единицу и введите количество.'
        return await app.safe(c, text, app.kb(rows))

    async def fixed_shop_message(message):
        rows = [[(f'{v["title"]} — ${app.money(v["price"])}', f'buyq:{k}')] for k, v in UNITS.items()]
        rows.append([('⬅️ Назад', 'home')])
        text = '🛒 ' + app.BRAND + ' • ВОЕННЫЙ АРСЕНАЛ\n\n'
        text += '\n'.join(f'{v["title"]} — ${app.money(v["price"])}' for v in UNITS.values())
        return await message.answer(text, reply_markup=app.kb(rows))

    async def fixed_buyq(c, k):
        if k not in UNITS:
            return await c.answer('Недоступно', show_alert=True)
        app.STATE[c.from_user.id] = ('buy', k)
        return await app.safe(c, f'🛒 {UNITS[k]["title"]}\n\nЦена: ${app.money(UNITS[k]["price"])}\n\nВведите количество:', app.back('shop'))

    async def fixed_buy_confirm(c, k, q):
        if k not in UNITS or q < 1 or q > 1_000_000:
            return await c.answer('Некорректное количество', show_alert=True)
        price = UNITS[k]['price'] * q
        db = await connect()
        try:
            cur = await db.execute(f'UPDATE users SET balance=balance-?,{k}={k}+? WHERE user_id=? AND balance>=?', (price, q, c.from_user.id, price))
            await db.commit()
        finally:
            await db.close()
        if cur.rowcount != 1:
            return await app.safe(c, '❌ Недостаточно средств.', app.back('shop'))
        return await app.safe(c, f'✅ Покупка выполнена\n\n{UNITS[k]["title"]} × {q}\n💵 Списано: ${app.money(price)}', app.back('shop'))

    app.shop = fixed_shop
    app.shop_from_message = fixed_shop_message
    app.buyq = fixed_buyq
    app.buy_confirm = fixed_buy_confirm

    try:
        import shop_runtime_patch
        shop_runtime_patch.install()
    except Exception:
        pass


def _patch_run(run):
    if getattr(run, '_wwd_config_patched', False):
        return
    run._wwd_config_patched = True
    try:
        import bot as app
        _patch_bot(app, run)
    except Exception:
        pass


if not any(isinstance(x, _RunFixFinder) for x in sys.meta_path):
    sys.meta_path.insert(0, _RunFixFinder())
