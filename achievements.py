import math
import bot as app
from db import connect, user
from config import UNITS

# Achievements are earned from DESTROYED enemy units, never from owned units.
# Artillery starts on exactly the same achievement level as BMP, with a
# requirement equal to BMP requirement +15% (rounded up).
ACHIEVEMENTS = [
    ('recruit', '🪖 Рекрут', (100, 50, 15, 20, 1, 0, 0, 200), [('money', 50_000)]),
    ('soldier', '🎖 Солдат', (200, 75, 20, 30, 2, 0, 0, 300), [('money', 100_000)]),
    ('senior_soldier', '🎖 Старший солдат', (500, 100, 30, 45, 2, 1, 0, 500), [('money', 200), ('case1', 2)]),
    ('junior_sergeant', '🎗 Младший сержант', (1100, 150, 70, 100, 5, 2, 0, 1000), [('money', 400), ('soldier', 50), ('interceptor', 5), ('money', 75_000)]),
    ('sergeant', '🎗 Сержант', (2000, 400, 130, 300, 8, 3, 0, 1900), [('money', 800), ('money', 100_000), ('drone', 10), ('tank', 5), ('soldier', 100)]),
    ('senior_sergeant', '🎗 Старший сержант', (5000, 600, 180, 320, 10, 5, 0, 4000), [('money', 200_000), ('helicopter', 1), ('interceptor', 150)]),
    ('junior_lieutenant', '⭐ Младший лейтенант', (10000, 800, 220, 400, 12, 6, 0, 8500), [('money', 500_000), ('helicopter', 2), ('tank', 1), ('bmp', 3), ('interceptor', 100)]),
    ('lieutenant', '⭐ Лейтенант', (15000, 850, 250, 430, 15, 8, 1, 12000), [('plane', 1), ('drone', 50)]),
    ('senior_lieutenant', '⭐ Старший лейтенант', (22222, 925, 300, 450, 17, 9, 2, 15000), [('plane', 1), ('helicopter', 1), ('tank', 10), ('soldier', 5000)]),
    ('captain', '⭐ Капитан', (30000, 1025, 350, 500, 19, 10, 3, 18000), [('money', 1_000_000), ('soldier', 5000), ('drone', 20), ('bmp', 30), ('interceptor', 400)]),
    ('major', '⭐ Майор', (40000, 1100, 400, 540, 20, 12, 5, 22000), [('money', 1_000_000), ('missile', 2), ('helicopter', 1), ('tank', 1), ('soldier', 3000)]),
    ('lieutenant_colonel', '⭐ Подполковник', (80000, 1200, 470, 600, 25, 15, 8, 26000), [('missile', 4), ('soldier', 15000), ('interceptor', 1000), ('drone', 350)]),
    ('colonel', '🏅 Полковник', (300000, 2000, 700, 1000, 60, 50, 35, 50000), [('donate_case', 3), ('case2', 5), ('missile', 10), ('plane', 3), ('helicopter', 5), ('soldier', 25000)]),
]

REQ_KEYS = ('kill_soldier', 'kill_drone', 'kill_tank', 'kill_bmp', 'kill_artillery', 'kill_helicopter', 'kill_plane', 'kill_missile', 'kill_interceptor')
REQ_NAMES = ('🪖 Уничтожено солдат', '🛩 Уничтожено БПЛА', '🛡 Уничтожено танков', '🚙 Уничтожено БМП', '💥 Уничтожено артиллерии', '🚁 Уничтожено вертолётов', '✈️ Уничтожено самолётов', '🚀 Уничтожено ракет', '🎯 Уничтожено перехватчиков')
REWARD_NAMES = {
    'soldier': '🪖 солдат', 'interceptor': '🎯 перехватчиков', 'drone': '🛩 БПЛА',
    'bmp': '🚙 БМП', 'artillery': '💥 артиллерии', 'tank': '🛡 танк',
    'helicopter': '🚁 вертолёт', 'plane': '✈️ самолёт', 'missile': '🚀 ракет',
    'case1': '📦 кейс №1', 'case2': '📦 кейс №2', 'donate_case': '⭐ донат-кейсов',
}


def requirements_for(requirements):
    """Keep old achievement tuples intact; derive artillery from the BMP goal."""
    values=list(requirements)
    bmp_need=int(values[3]) if len(values) > 3 else 0
    artillery_need=math.ceil(bmp_need * 1.15) if bmp_need > 0 else 0
    return tuple(values[:4] + [artillery_need] + values[4:])


async def init_achievements():
    db = await connect()
    try:
        await db.execute('CREATE TABLE IF NOT EXISTS achievements(user_id INTEGER,achievement_id TEXT,completed INTEGER NOT NULL DEFAULT 0,claimed INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(user_id,achievement_id))')
        await db.execute('CREATE TABLE IF NOT EXISTS achievement_inventory(user_id INTEGER PRIMARY KEY,case1 INTEGER NOT NULL DEFAULT 0,case2 INTEGER NOT NULL DEFAULT 0,donate_case INTEGER NOT NULL DEFAULT 0)')
        await db.execute('CREATE TABLE IF NOT EXISTS case_inventory(user_id INTEGER PRIMARY KEY,case1 INTEGER NOT NULL DEFAULT 0,case2 INTEGER NOT NULL DEFAULT 0,donate_case INTEGER NOT NULL DEFAULT 0)')
        await db.commit()
    finally:
        await db.close()


def reward_text(rewards):
    out = []
    for kind, amount in rewards:
        amount = int(amount)
        if kind == 'money':
            out.append(f'💵 ${amount:,}'.replace(',', ' '))
        else:
            out.append(f'{REWARD_NAMES.get(kind, kind)} × {amount:,}'.replace(',', ' '))
    return '\n'.join(out)


def met(row, requirements):
    requirements=requirements_for(requirements)
    return all(int(row[key] or 0) >= needed for key, needed in zip(REQ_KEYS, requirements))


async def check(uid, bot=None, notify=True):
    row = await user(uid)
    if not row:
        return []
    db = await connect()
    new = []
    try:
        for aid, title, requirements, _rewards in ACHIEVEMENTS:
            cur = await db.execute('SELECT completed FROM achievements WHERE user_id=? AND achievement_id=?', (uid, aid))
            old = await cur.fetchone()
            if old and int(old['completed']):
                continue
            if met(row, requirements):
                await db.execute(
                    'INSERT INTO achievements(user_id,achievement_id,completed,claimed) VALUES(?,?,1,0) '
                    'ON CONFLICT(user_id,achievement_id) DO UPDATE SET completed=1',
                    (uid, aid),
                )
                new.append(title)
        await db.commit()
    finally:
        await db.close()
    if bot is not None and notify:
        for title in new:
            try:
                await bot.send_message(uid, f'🏆 Вы выполнили ачивку «{title}»!\n\n🎁 Заберите награду в разделе «Ачивки».')
            except Exception:
                pass
    return new


async def menu(c):
    await check(c.from_user.id, c.bot)
    db = await connect()
    try:
        cur = await db.execute('SELECT achievement_id,completed,claimed FROM achievements WHERE user_id=?', (c.from_user.id,))
        states = {r['achievement_id']: (int(r['completed']), int(r['claimed'])) for r in await cur.fetchall()}
    finally:
        await db.close()
    rows = []
    for aid, title, _req, _rew in ACHIEVEMENTS:
        done, claimed = states.get(aid, (0, 0))
        mark = '☑️' if claimed else ('✅' if done else '🔒')
        rows.append([(f'{mark} {title}', f'ach:{aid}')])
    rows.append([('⬅️ Назад', 'home')])
    await app.safe(c, f'🏆 {app.BRAND} • АЧИВКИ\n\nАчивки выдаются за количество уничтоженной техники, а не за наличие своей армии.\nНажмите на ачивку для подробностей.', app.kb(rows))


async def detail(c, aid):
    item = next((x for x in ACHIEVEMENTS if x[0] == aid), None)
    if item is None:
        return await c.answer('Ачивка не найдена.', show_alert=True)
    _, title, requirements, rewards = item
    await check(c.from_user.id, c.bot, False)
    row = await user(c.from_user.id)
    db = await connect()
    try:
        cur = await db.execute('SELECT completed,claimed FROM achievements WHERE user_id=? AND achievement_id=?', (c.from_user.id, aid))
        state = await cur.fetchone()
    finally:
        await db.close()
    req_values=requirements_for(requirements)
    req = '\n'.join(
        f'{REQ_NAMES[i]}: {int(row[k] or 0)}/{need}'
        for i, (k, need) in enumerate(zip(REQ_KEYS, req_values))
        if need
    ) or 'Нет требований.'
    done = bool(state and int(state['completed']))
    claimed = bool(state and int(state['claimed']))
    buttons = []
    if done and not claimed:
        buttons.append([('🎁 Забрать награду', f'ach_claim:{aid}')])
    buttons.append([('⬅️ Назад', 'achievements')])
    status = '☑️ Награда получена' if claimed else ('✅ Выполнено' if done else '🔒 Не выполнено')
    await app.safe(c, f'🏆 {title}\n\n📋 Требования:\n{req}\n\n🎁 Награда:\n{reward_text(rewards)}\n\nСтатус: {status}', app.kb(buttons))


async def claim(c, aid):
    item = next((x for x in ACHIEVEMENTS if x[0] == aid), None)
    if item is None:
        return await c.answer('Ачивка не найдена.', show_alert=True)
    _, title, _requirements, rewards = item
    await check(c.from_user.id, c.bot, False)
    db = await connect()
    try:
        cur = await db.execute('SELECT completed,claimed FROM achievements WHERE user_id=? AND achievement_id=?', (c.from_user.id, aid))
        state = await cur.fetchone()
        if not state or not int(state['completed']):
            return await c.answer('Ачивка ещё не выполнена.', show_alert=True)
        if int(state['claimed']):
            return await c.answer('Награда уже получена.', show_alert=True)

        balance = 0
        units = {k: 0 for k in UNITS}
        cases = {'case1': 0, 'case2': 0, 'donate_case': 0}
        for kind, amount in rewards:
            if kind == 'money':
                balance += int(amount)
            elif kind in units:
                units[kind] += int(amount)
            elif kind in cases:
                cases[kind] += int(amount)

        sets = []
        params = []
        if balance:
            sets.append('balance=balance+?')
            params.append(balance)
        for k, value in units.items():
            if value:
                sets.append(f'{k}={k}+?')
                params.append(value)
        if sets:
            params.append(c.from_user.id)
            await db.execute(f'UPDATE users SET {",".join(sets)} WHERE user_id=?', params)

        await db.execute(
            'INSERT INTO case_inventory(user_id,case1,case2,donate_case) VALUES(?,?,?,?) '
            'ON CONFLICT(user_id) DO UPDATE SET case1=case1+excluded.case1,case2=case2+excluded.case2,donate_case=donate_case+excluded.donate_case',
            (c.from_user.id, cases['case1'], cases['case2'], cases['donate_case']),
        )
        await db.execute(
            'INSERT INTO achievement_inventory(user_id,case1,case2,donate_case) VALUES(?,?,?,?) '
            'ON CONFLICT(user_id) DO UPDATE SET case1=case1+excluded.case1,case2=case2+excluded.case2,donate_case=donate_case+excluded.donate_case',
            (c.from_user.id, cases['case1'], cases['case2'], cases['donate_case']),
        )
        await db.execute('UPDATE achievements SET claimed=1 WHERE user_id=? AND achievement_id=?', (c.from_user.id, aid))
        await db.commit()
    finally:
        await db.close()
    await app.safe(c, f'🎁 Награда за «{title}» получена!\n\n{reward_text(rewards)}', app.kb([[('⬅️ К ачивкам', 'achievements')]]))


def install_sync():
    return None
