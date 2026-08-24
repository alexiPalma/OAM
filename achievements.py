import bot as app
from db import connect, user
from config import UNITS
from aiogram import F

# Requirements are ordered exactly as:
# soldiers / UAVs / tanks / BMP / helicopters / planes / missiles / interceptors.
ACHIEVEMENTS = [
    ('recruit', '🪖 Рекрут', (100, 50, 15, 20, 1, 0, 0, 200), [('money', 50000)]),
    ('soldier', '🎖 Солдат', (200, 75, 20, 30, 2, 0, 0, 300), [('money', 100), ('money', 100000)]),
    ('senior_soldier', '🎖 Старший солдат', (500, 100, 30, 45, 2, 1, 0, 500), [('money', 200), ('case1', 2)]),
    ('junior_sergeant', '🎗 Младший сержант', (1100, 150, 70, 100, 5, 2, 0, 1000), [('money', 400), ('soldier', 50), ('interceptor', 5), ('money', 75000)]),
    ('sergeant', '🎗 Сержант', (2000, 400, 130, 300, 8, 3, 0, 1900), [('money', 800), ('money', 100000), ('drone', 10), ('tank', 5), ('soldier', 100)]),
    ('senior_sergeant', '🎗 Старший сержант', (5000, 600, 180, 320, 10, 5, 0, 4000), [('money', 200000), ('helicopter', 1), ('interceptor', 150)]),
    ('junior_lieutenant', '⭐ Младший лейтенант', (10000, 800, 220, 400, 12, 6, 0, 8500), [('money', 500000), ('helicopter', 2), ('tank', 1), ('bmp', 3), ('interceptor', 100)]),
    ('lieutenant', '⭐ Лейтенант', (15000, 850, 250, 430, 15, 8, 1, 12000), [('plane', 1), ('drone', 50)]),
    ('senior_lieutenant', '⭐ Старший лейтенант', (22222, 925, 300, 450, 17, 9, 2, 15000), [('plane', 1), ('helicopter', 1), ('tank', 10), ('soldier', 5000)]),
    ('captain', '⭐ Капитан', (30000, 1025, 350, 500, 19, 10, 3, 18000), [('money', 1000000), ('soldier', 5000), ('drone', 20), ('bmp', 30), ('interceptor', 400)]),
    ('major', '⭐ Майор', (40000, 1100, 400, 540, 20, 12, 5, 22000), [('money', 1000000), ('missile', 2), ('helicopter', 1), ('tank', 1), ('soldier', 3000)]),
    ('lieutenant_colonel', '⭐ Подполковник', (80000, 1200, 470, 600, 25, 15, 8, 26000), [('missile', 4), ('soldier', 15000), ('interceptor', 1000), ('drone', 350)]),
    ('colonel', '🏅 Полковник', (300000, 2000, 700, 1000, 60, 50, 35, 50000), [('donate_case', 3), ('case2', 5), ('missile', 10), ('plane', 3), ('helicopter', 5), ('soldier', 25000), ('legend_prefix', 1)]),
]

REQ_KEYS = ('soldier', 'drone', 'tank', 'bmp', 'helicopter', 'plane', 'missile', 'interceptor')
REQ_NAMES = ('🪖 Солдаты', '🛩 БПЛА', '🛡 Танки', '🚙 БМП', '🚁 Вертолёты', '✈️ Самолёты', '🚀 Ракеты', '🎯 Перехватчики')
REWARD_NAMES = {
    'soldier': '🪖 солдат',
    'interceptor': '🎯 перехватчиков',
    'drone': '🛩 БПЛА',
    'bmp': '🚙 БМП',
    'tank': '🛡 танк',
    'helicopter': '🚁 вертолёт',
    'plane': '✈️ самолёт',
    'missile': '🚀 ракет',
    'case1': '📦 кейс №1',
    'case2': '📦 кейсов №2',
    'donate_case': '⭐ донат-кейсов',
    'legend_prefix': '👑 префикс «Легенда»',
}

async def init_achievements():
    db = await connect()
    await db.execute('''CREATE TABLE IF NOT EXISTS achievements(
        user_id INTEGER,
        achievement_id TEXT,
        completed INTEGER NOT NULL DEFAULT 0,
        claimed INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(user_id, achievement_id)
    )''')
    await db.execute('''CREATE TABLE IF NOT EXISTS achievement_inventory(
        user_id INTEGER PRIMARY KEY,
        case1 INTEGER NOT NULL DEFAULT 0,
        case2 INTEGER NOT NULL DEFAULT 0,
        donate_case INTEGER NOT NULL DEFAULT 0,
        legend_prefix INTEGER NOT NULL DEFAULT 0
    )''')
    await db.commit()
    await db.close()


def reward_text(rewards):
    out = []
    for typ, amount in rewards:
        if typ == 'money':
            out.append(f'💵 ${int(amount):,}'.replace(',', ' '))
        else:
            out.append(f'{REWARD_NAMES.get(typ, typ)} × {int(amount):,}'.replace(',', ' '))
    return '\n'.join(out)


def met(row, req):
    return all(int(row[key]) >= needed for key, needed in zip(REQ_KEYS, req))


async def check(uid, bot=None, notify=True):
    """Mark newly completed achievements and optionally notify the user once."""
    row = await user(uid)
    if not row:
        return []

    db = await connect()
    newly_completed = []
    try:
        for aid, title, requirements, _rewards in ACHIEVEMENTS:
            cur = await db.execute(
                'SELECT completed FROM achievements WHERE user_id=? AND achievement_id=?',
                (uid, aid),
            )
            old = await cur.fetchone()
            if old and int(old['completed']):
                continue
            if met(row, requirements):
                await db.execute(
                    '''INSERT INTO achievements(user_id,achievement_id,completed,claimed)
                       VALUES(?,?,1,0)
                       ON CONFLICT(user_id,achievement_id)
                       DO UPDATE SET completed=1''',
                    (uid, aid),
                )
                newly_completed.append(title)
        await db.commit()
    finally:
        await db.close()

    if bot is not None and notify:
        for title in newly_completed:
            try:
                await bot.send_message(
                    uid,
                    f'🏆 Вы выполнили ачивку «{title}»!\n\n'
                    f'🎁 Заберите вашу награду в разделе «Ачивки».',
                )
            except Exception:
                pass
    return newly_completed


async def menu(c):
    await check(c.from_user.id, c.bot)
    db = await connect()
    try:
        cur = await db.execute(
            'SELECT achievement_id,completed,claimed FROM achievements WHERE user_id=?',
            (c.from_user.id,),
        )
        states = {
            row['achievement_id']: (int(row['completed']), int(row['claimed']))
            for row in await cur.fetchall()
        }
    finally:
        await db.close()

    rows = []
    for aid, title, _req, _rewards in ACHIEVEMENTS:
        completed, claimed = states.get(aid, (0, 0))
        mark = '☑️' if claimed else ('✅' if completed else '🔒')
        rows.append([(f'{mark} {title}', f'ach:{aid}')])
    rows.append([('⬅️ Назад', 'home')])
    await app.safe(
        c,
        f'🏆 {app.BRAND} • АЧИВКИ\n\n'
        'Нажмите на любую ачивку, чтобы посмотреть требования и награду.',
        app.kb(rows),
    )


async def detail(c, aid):
    item = next((item for item in ACHIEVEMENTS if item[0] == aid), None)
    if item is None:
        return await c.answer('Ачивка не найдена.', show_alert=True)

    _, title, requirements, rewards = item
    await check(c.from_user.id, c.bot, False)
    db = await connect()
    try:
        cur = await db.execute(
            'SELECT completed,claimed FROM achievements WHERE user_id=? AND achievement_id=?',
            (c.from_user.id, aid),
        )
        state = await cur.fetchone()
    finally:
        await db.close()

    row = await user(c.from_user.id)
    completed = bool(state and int(state['completed']))
    claimed = bool(state and int(state['claimed']))
    requirement_text = '\n'.join(
        f'{REQ_NAMES[index]}: {int(row[key])}/{needed}'
        for index, (key, needed) in enumerate(zip(REQ_KEYS, requirements))
        if needed
    ) or 'Нет требований.'

    buttons = []
    if completed and not claimed:
        buttons.append([('🎁 Забрать награду', f'ach_claim:{aid}')])
    buttons.append([('⬅️ Назад', 'achievements')])
    status = '☑️ Награда получена' if claimed else ('✅ Выполнено' if completed else '🔒 Не выполнено')

    await app.safe(
        c,
        f'🏆 {title}\n\n'
        f'📋 Требования:\n{requirement_text}\n\n'
        f'🎁 Награда:\n{reward_text(rewards)}\n\n'
        f'Статус: {status}',
        app.kb(buttons),
    )


async def claim(c, aid):
    item = next((item for item in ACHIEVEMENTS if item[0] == aid), None)
    if item is None:
        return await c.answer('Ачивка не найдена.', show_alert=True)

    _, title, _requirements, rewards = item
    await check(c.from_user.id, c.bot, False)
    db = await connect()
    try:
        cur = await db.execute(
            'SELECT completed,claimed FROM achievements WHERE user_id=? AND achievement_id=?',
            (c.from_user.id, aid),
        )
        state = await cur.fetchone()
        if not state or not int(state['completed']):
            await db.rollback()
            return await c.answer('Ачивка ещё не выполнена.', show_alert=True)
        if int(state['claimed']):
            await db.rollback()
            return await c.answer('Награда уже получена.', show_alert=True)

        balance_delta = 0
        unit_deltas = {unit: 0 for unit in UNITS}
        inventory = {'case1': 0, 'case2': 0, 'donate_case': 0, 'legend_prefix': 0}
        for reward_type, amount in rewards:
            amount = int(amount)
            if reward_type == 'money':
                balance_delta += amount
            elif reward_type in UNITS:
                unit_deltas[reward_type] += amount
            elif reward_type in inventory:
                inventory[reward_type] += amount

        assignments = []
        params = []
        if balance_delta:
            assignments.append('balance=balance+?')
            params.append(balance_delta)
        for unit, amount in unit_deltas.items():
            if amount:
                assignments.append(f'{unit}={unit}+?')
                params.append(amount)
        if assignments:
            params.append(c.from_user.id)
            await db.execute(
                f'UPDATE users SET {",".join(assignments)} WHERE user_id=?',
                params,
            )

        await db.execute(
            '''INSERT INTO achievement_inventory(user_id,case1,case2,donate_case,legend_prefix)
               VALUES(?,?,?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET
                 case1=case1+excluded.case1,
                 case2=case2+excluded.case2,
                 donate_case=donate_case+excluded.donate_case,
                 legend_prefix=legend_prefix+excluded.legend_prefix''',
            (
                c.from_user.id,
                inventory['case1'],
                inventory['case2'],
                inventory['donate_case'],
                inventory['legend_prefix'],
            ),
        )
        await db.execute(
            'UPDATE achievements SET claimed=1 WHERE user_id=? AND achievement_id=?',
            (c.from_user.id, aid),
        )
        await db.commit()
    finally:
        await db.close()

    await app.safe(
        c,
        f'🎁 Награда за «{title}» получена!\n\n{reward_text(rewards)}',
        app.kb([[('⬅️ К ачивкам', 'achievements')]]),
    )


def install_sync():
    """Install achievement UI without replacing the main bot callback handler."""
    if getattr(app, '_achievements_installed', False):
        return
    app._achievements_installed = True

    # Add the button to the existing main menu.
    old_home = app.home_kb
    def home_with_achievements(is_admin=False):
        markup = old_home(is_admin)
        rows = [list(row) for row in markup.inline_keyboard]
        insert_at = max(0, len(rows) - 1)
        rows.insert(insert_at, [app.InlineKeyboardButton(text='🏆 Ачивки', callback_data='achievements')])
        return app.InlineKeyboardMarkup(inline_keyboard=rows)
    app.home_kb = home_with_achievements

    # Register a dedicated observer; never replace app.callback itself.
    target = getattr(app, 'dp', None)
    if target is not None and hasattr(target, 'callback_query'):
        async def achievement_callback(c):
            data = c.data or ''
            if data == 'achievements':
                return await menu(c)
            if data.startswith('ach:'):
                return await detail(c, data.split(':', 1)[1])
            if data.startswith('ach_claim:'):
                return await claim(c, data.split(':', 1)[1])
        target.callback_query.register(achievement_callback, F.data.startswith('ach'))

    # Check after common reward-producing operations.
    for name in ('buy_confirm', 'daily'):
        original = getattr(app, name, None)
        if original is None or getattr(original, '_achievement_wrapper', False):
            continue

        async def wrapped(*args, _original=original, **kwargs):
            result = await _original(*args, **kwargs)
            try:
                callback = args[0]
                await check(callback.from_user.id, callback.bot, True)
            except Exception:
                pass
            return result

        wrapped._achievement_wrapper = True
        setattr(app, name, wrapped)

    # Also check after any callback that uses the bot's common safe() renderer.
    original_safe = getattr(app, 'safe', None)
    if original_safe is not None and not getattr(original_safe, '_achievement_wrapper', False):
        async def safe_with_achievement_check(*args, **kwargs):
            result = await original_safe(*args, **kwargs)
            try:
                callback = args[0]
                await check(callback.from_user.id, callback.bot, True)
            except Exception:
                pass
            return result
        safe_with_achievement_check._achievement_wrapper = True
        app.safe = safe_with_achievement_check
