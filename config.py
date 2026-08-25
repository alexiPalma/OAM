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
    'interceptor': {'id': 2, 'title': '🎯 Дрон-перехватчик', 'price': 4_000, 'loss': 4_000, 'rating': 1},
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
        db = await app.connect()
        try:
            cur = await db.execute(
                f'UPDATE users SET balance=balance-?,{k}={k}+? WHERE user_id=? AND balance>=?',
                (price, q, c.from_user.id, price),
            )
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

    async def fixed_top(c):
        from db import top_users
        rows = await top_users(50)
        out = []
        for i, r in enumerate(rows, 1):
            medal = ['🥇', '🥈', '🥉'][i - 1] if i <= 3 else '🎖️'
            name = '@' + r['username'] if r['username'] else f'ID {r["user_id"]}'
            out.append(f'{medal} {i}. {name} — 🎖 {app.money(r["army_total"])}')
        text = f'🏆 {app.BRAND} • ТОП ВОЯК\n\n' + ('\n'.join(out) if out else 'Пока игроков нет.')
        return await app.safe(c, text, app.back())

    app.top = fixed_top

    async def fixed_daily(c):
        import random
        from datetime import date
        u = await app.user(c.from_user.id)
        today = app.now().date().isoformat()
        if u['daily_claim'] == today:
            return await c.answer('Сегодня уже получено.', show_alert=True)
        r = random.uniform(0, 100)
        acc = 0
        selected = None
        for prize in DAILY_BONUS_PRIZES:
            acc += prize[0]
            if r < acc:
                selected = prize
                break
        if selected is None:
            return await c.answer('Попробуйте ещё раз.', show_alert=True)
        _, kind, amount, label = selected
        db = await app.connect()
        try:
            if kind in ('case1', 'case2', 'donate_case'):
                await db.execute('CREATE TABLE IF NOT EXISTS case_inventory(user_id INTEGER PRIMARY KEY,case1 INTEGER NOT NULL DEFAULT 0,case2 INTEGER NOT NULL DEFAULT 0,donate_case INTEGER NOT NULL DEFAULT 0)')
                await db.execute(
                    f'INSERT INTO case_inventory(user_id,{kind}) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET {kind}={kind}+excluded.{kind}',
                    (c.from_user.id, int(amount)),
                )
            else:
                col = 'balance' if kind == 'money' else kind
                await db.execute(f'UPDATE users SET {col}={col}+?,daily_claim=? WHERE user_id=?', (amount, today, c.from_user.id))
            await db.execute('UPDATE users SET daily_claim=? WHERE user_id=?', (today, c.from_user.id))
            await db.commit()
        finally:
            await db.close()
        return await app.safe(c, f'🎁 Вы получили: {label}.', app.back('bonus'))

    app.daily = fixed_daily

    async def fixed_promo(message, code):
        db = await app.connect()
        try:
            cur = await db.execute('SELECT * FROM promos WHERE lower(code)=lower(?)', (code.strip(),))
            promo = await cur.fetchone()
            if not promo:
                return await message.answer('❌ Промокод не найден.')
            if int(promo['uses']) >= int(promo['max_uses']):
                return await message.answer('❌ Промокод больше недоступен.')
            cur = await db.execute('SELECT 1 FROM promo_uses WHERE code=? AND user_id=?', (promo['code'], message.from_user.id))
            if await cur.fetchone():
                return await message.answer('❌ Вы уже использовали этот промокод.')
            reward_type = str(promo['reward_type'] or 'money')
            amount = int(promo['reward_amount'] or promo['amount'] or 0)
            if reward_type.startswith('case:'):
                case = reward_type.split(':', 1)[1]
                if case not in ('case1', 'case2', 'donate_case'):
                    return await message.answer('❌ Некорректный кейс.')
                await db.execute('CREATE TABLE IF NOT EXISTS case_inventory(user_id INTEGER PRIMARY KEY,case1 INTEGER NOT NULL DEFAULT 0,case2 INTEGER NOT NULL DEFAULT 0,donate_case INTEGER NOT NULL DEFAULT 0)')
                await db.execute(
                    f'INSERT INTO case_inventory(user_id,{case}) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET {case}={case}+excluded.{case}',
                    (message.from_user.id, amount),
                )
                reward_text = f'📦 {case} × {amount}'
            elif reward_type.startswith('unit:'):
                unit = reward_type.split(':', 1)[1]
                if unit not in UNITS or amount <= 0:
                    return await message.answer('❌ Промокод содержит некорректную технику.')
                await db.execute(f'UPDATE users SET {unit}={unit}+? WHERE user_id=?', (amount, message.from_user.id))
                reward_text = f'{UNITS[unit]["title"]} × {amount}'
            else:
                await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?', (amount, message.from_user.id))
                reward_text = f'💵 +${app.money(amount)}'
            await db.execute('UPDATE promos SET uses=uses+1 WHERE code=?', (promo['code'],))
            await db.execute('INSERT INTO promo_uses(code,user_id) VALUES(?,?)', (promo['code'], message.from_user.id))
            await db.commit()
        finally:
            await db.close()
        return await message.answer(f'🎉 Промокод активирован!\n\nНаграда: {reward_text}')

    app.use_promo_extended = fixed_promo

    async def fixed_add_promo(message, parts):
        if not await run.admin_ok(message.from_user.id):
            return await message.answer('⛔ Нет доступа.')
        if len(parts) == 3:
            code, amount_s, max_s = parts
            reward_type = 'money'
        elif len(parts) == 4 and parts[1].lower() == 'money':
            code, _, amount_s, max_s = parts
            reward_type = 'money'
        elif len(parts) == 5 and parts[1].lower() in ('unit', 'tech', 'equipment'):
            code, _, unit, amount_s, max_s = parts
            unit = unit.lower()
            if unit not in UNITS:
                return await message.answer('❌ Неизвестная техника.')
            reward_type = 'unit:' + unit
        elif len(parts) == 5 and parts[1].lower() in ('case', 'cases'):
            code, _, case, amount_s, max_s = parts
            case = case.lower()
            if case not in ('case1', 'case2', 'donate_case'):
                return await message.answer('❌ Кейс: case1, case2 или donate_case.')
            reward_type = 'case:' + case
        else:
            return await message.answer(
                '❌ Формат:\n'
                '/addpromo КОД СУММА ЛИМИТ\n'
                '/addpromo КОД unit ТЕХНИКА КОЛИЧЕСТВО ЛИМИТ\n'
                '/addpromo КОД case КЕЙС КОЛИЧЕСТВО ЛИМИТ\n\n'
                'Кейсы: case1, case2, donate_case'
            )
        try:
            amount, max_uses = int(amount_s), int(max_s)
        except ValueError:
            return await message.answer('❌ Количество и лимит должны быть числами.')
        if amount <= 0 or max_uses <= 0:
            return await message.answer('❌ Значения должны быть больше нуля.')
        db = await app.connect()
        try:
            await db.execute(
                '''INSERT INTO promos(code,amount,uses,max_uses,reward_type,reward_amount)
                   VALUES(?,?,0,?,?,?)
                   ON CONFLICT(code) DO UPDATE SET amount=excluded.amount,max_uses=excluded.max_uses,
                   reward_type=excluded.reward_type,reward_amount=excluded.reward_amount''',
                (code, amount if reward_type == 'money' else 0, max_uses, reward_type, amount),
            )
            await db.commit()
        finally:
            await db.close()
        if reward_type == 'money':
            label = f'💵 ${app.money(amount)}'
        elif reward_type.startswith('unit:'):
            label = f'{UNITS[reward_type.split(":", 1)[1]]["title"]} × {amount}'
        else:
            label = f'📦 {reward_type.split(":", 1)[1]} × {amount}'
        return await message.answer(f'✅ Промокод создан/обновлён.\n\n🎟 {code}\n🎁 {label}\n👥 Лимит: {max_uses}')

    run.add_promo = fixed_add_promo

    async def fixed_help(message):
        return await message.answer(
            f'ℹ️ {app.BRAND} • ПОМОЩЬ\n\n'
            '🏭 ферма — открыть ферму\n'
            '🎖 армия / а — открыть армию\n'
            '🛒 шоп — открыть арсенал\n'
            '⚔️ атака / вызовы — начать атаку\n'
            '💰 заработать — задания на заработок\n'
            '📋 задания — постоянные задания\n'
            '🎁 бонус — ежедневный бонус\n'
            '🎟 промо — промокод\n'
            '🏆 ачивки — достижения\n'
            '🏆 топ — рейтинг воинов',
            reply_markup=app.home_kb(await run.admin_ok(message.from_user.id)),
        )

    async def fixed_bonus_keyword(message):
        prizes = '\n'.join(f'{p:g}% — {label}' for p, _, _, label in DAILY_BONUS_PRIZES)
        return await message.answer(
            f'🎁 {app.BRAND} • ЕЖЕДНЕВНЫЙ БОНУС\n\n{prizes}',
            reply_markup=app.kb([[('🎁 Забрать', 'daily')], [('⬅️ Назад', 'home')]]),
        )

    run._wwd_help = fixed_help
    run._wwd_bonus_keyword = fixed_bonus_keyword
    run._wwd_render_context = render_context
    run._wwd_restore_context = restore_context

    original_run_earn_kb = getattr(run, 'earn_kb', None)
    if original_run_earn_kb:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        def fixed_earn_kb(tasks, claimed):
            owner = _GROUP_RENDER_USER.get()
            rows = []
            labels = {'boost': '🚀 Буст канала / группы', 'channel': '📢 Подписка на канал', 'group': '👥 Вступление в группу'}
            for task in tasks:
                label = labels.get(task['kind'], task['kind'])
                if task['id'] in claimed:
                    rows.append([InlineKeyboardButton(text=f'☑️ {label} · награда получена', callback_data=f'{_GROUP_PREFIX}{owner}:earn_done' if owner else 'earn_done')])
                    continue
                rows.append([InlineKeyboardButton(text=f'{label} · +${app.money(task["reward"])}', url=str(task['url']).strip())])
                cb = f'earn_check:{task["kind"]}:{task["id"]}'
                if owner:
                    cb = f'{_GROUP_PREFIX}{owner}:{cb}'
                rows.append([InlineKeyboardButton(text='✅ Проверить выполнение', callback_data=cb)])
            cb_tasks = f'{_GROUP_PREFIX}{owner}:tasks' if owner else 'tasks'
            cb_home = f'{_GROUP_PREFIX}{owner}:home' if owner else 'home'
            rows.append([InlineKeyboardButton(text='📋 Задания', callback_data=cb_tasks)])
            rows.append([InlineKeyboardButton(text='⬅️ Назад', callback_data=cb_home)])
            return InlineKeyboardMarkup(inline_keyboard=rows)

        run.earn_kb = fixed_earn_kb

    original_run_callback = run.callback
    async def fixed_run_callback(c, tg_bot, *args, **kwargs):
        data = c.data or ''
        if getattr(c, 'message', None) and c.message.chat.type != 'private':
            if data.startswith(_GROUP_PREFIX):
                rest = data[len(_GROUP_PREFIX):]
                owner_s, sep, original = rest.partition(':')
                try:
                    owner = int(owner_s)
                except ValueError:
                    owner = 0
                if owner != c.from_user.id and not original.startswith(('accept:', 'decline:')):
                    return await c.answer('⛔ Это меню принадлежит другому пользователю.', show_alert=True)
                data = original
                c.data = data
            else:
                # Unprefixed menu callbacks in groups are not allowed. Battle accept/decline
                # remain protected by INVITES in bot.py and are intentionally allowed.
                if not data.startswith(('accept:', 'decline:')):
                    return await c.answer('⛔ Это меню нельзя использовать другому пользователю.', show_alert=True)
            token = render_context(c.from_user.id)
        else:
            token = render_context(None)
        try:
            return await original_run_callback(c, tg_bot, *args, **kwargs)
        finally:
            restore_context(token)

    run.callback = fixed_run_callback

    original_run_text = run.text_handler
    async def fixed_run_text(message, bot, *args, **kwargs):
        token = render_context(message.from_user.id if message.chat.type != 'private' else None)
        try:
            low = (message.text or '').strip().lower()
            if low in ('хелп', 'help', '/help', '/хелп'):
                return await fixed_help(message)
            if low in ('бонус', 'bonus', '/bonus', '/бонус'):
                return await fixed_bonus_keyword(message)
            return await original_run_text(message, bot, *args, **kwargs)
        finally:
            restore_context(token)

    run.text_handler = fixed_run_text


def _patch_run(run):
    if getattr(run, '_wwd_final_fix', False):
        return
    run._wwd_final_fix = True

    import bot as app
    from db import connect, top_users

    _patch_bot(app, run)

    # Make the achievement module use the real kill counters and keep the
    # existing progression/rewards intact. The detailed requirements are
    # handled in achievements.py.

    # Preserve the existing run callback routes while fixing the admin promo screen.
    old_callback = run.callback

    async def fixed_admin_callback(c, tg_bot, *args, **kwargs):
        data = c.data or ''
        if data == 'a_promos':
            return await app.safe(
                c,
                '🎟 ПРОМОКОДЫ\n\n'
                '/addpromo КОД СУММА ЛИМИТ\n'
                '/addpromo КОД unit ТЕХНИКА КОЛИЧЕСТВО ЛИМИТ\n'
                '/addpromo КОД case КЕЙС КОЛИЧЕСТВО ЛИМИТ\n\n'
                'Кейсы: case1, case2, donate_case',
                app.back('admin'),
            )
        return await old_callback(c, tg_bot, *args, **kwargs)

    run.callback = fixed_admin_callback


if not any(isinstance(x, _RunFixFinder) for x in sys.meta_path):
    sys.meta_path.insert(0, _RunFixFinder())
