"""Final runtime feature patch for WorldWarDynasty.

This file is loaded by usercustomize.py so the requested features are applied
at startup to the real bot, not just left in unused helper modules.
"""
import importlib.abc
import importlib.machinery
import sys

RATING = {
    'soldier': 1, 'interceptor': 1, 'drone': 3, 'bmp': 7,
    'artillery': 8, 'tank': 10, 'helicopter': 15, 'plane': 25,
    'missile': 50,
}


def patch_core():
    import config
    import db
    import bot as app

    # Exact shop/rating order: artillery is immediately after BMP.
    ordered = {}
    for key, rating in RATING.items():
        item = dict(config.UNITS[key])
        item['rating'] = rating
        if key == 'artillery':
            item['price'] = 2_500_000
        ordered[key] = item
    config.UNITS = ordered
    config.UNIT_BY_ID = {v['id']: k for k, v in ordered.items()}
    app.UNITS = config.UNITS

    async def top_users(limit=50):
        conn = await db.connect()
        try:
            expr = ' + '.join(f'COALESCE({k},0)*{w}' for k,w in RATING.items())
            cur = await conn.execute(
                f'SELECT user_id,username,balance,farm_level,{expr} AS army_total '
                'FROM users ORDER BY army_total DESC, attacks_won DESC, user_id ASC LIMIT ?',
                (max(1, min(50, int(limit))),),
            )
            return await cur.fetchall()
        finally:
            await conn.close()
    db.RATING_WEIGHTS = dict(RATING)
    db.top_users = top_users

    async def top(c):
        rows = await top_users(50)
        lines = []
        for i, row in enumerate(rows, 1):
            medal = ('🥇','🥈','🥉')[i-1] if i <= 3 else '🎖️'
            name = '@' + row['username'] if row['username'] else f"ID {row['user_id']}"
            equipment = ', '.join(
                f"{ordered[k]['title']} × {int(row[k])}" for k in ordered if int(row[k])
            ) or 'нет техники'
            lines.append(f"{medal} {i}. {app.esc(name)} — 🏆 {int(row['army_total'])} рейтинга\n   {equipment}")
        text = f"🏆 {app.BRAND} • ТОП ВОЯК\n\n" + ('\n'.join(lines) or 'Пока игроков нет.')
        return await app.safe(c, text, app.back())
    app.top = top

    async def shop(c):
        rows = [[(f'{v["title"]} — ${app.money(v["price"])}', f'buyq:{k}')] for k,v in ordered.items()]
        rows.append([('⬅️ Назад','home')])
        items = '\n'.join(f'{v["title"]} — ${app.money(v["price"])}' for v in ordered.values())
        return await app.safe(c, f'🛒 {app.BRAND} • ВОЕННЫЙ АРСЕНАЛ\n\n{items}\n\nВыберите единицу и введите количество.', app.kb(rows))
    app.shop = shop

    async def buyq(c, key):
        if key not in ordered:
            return await c.answer('Недоступно', show_alert=True)
        app.STATE[c.from_user.id] = ('buy', key)
        v = ordered[key]
        return await app.safe(c, f'{v["title"]}\n\nЦена: ${app.money(v["price"])}\n\nВведите количество:', app.back('shop'))
    app.buyq = buyq

    # Achievements are based on destroyed units, never owned units.
    try:
        import achievements
        keys = ('soldier','drone','tank','bmp','helicopter','plane','missile','interceptor')
        achievements.REQ_KEYS = tuple('kill_' + k for k in keys)
        achievements.REQ_NAMES = tuple('💀 Уничтожено ' + n for n in (
            'солдат','БПЛА','танков','БМП','вертолётов','самолётов','ракет','перехватчиков'))
    except Exception:
        pass

    # Rockets are independent weapons: there is deliberately no crew check.
    try:
        import combat
        app.resolve = combat.resolve
    except Exception:
        pass


def patch_run(run):
    if getattr(run, '_wwd_final_requirements', False):
        return
    run._wwd_final_requirements = True
    import bot as app
    from config import UNITS, OWNER_IDS, OWNER_ID2, ADMIN_ID
    from db import connect, is_admin

    async def admin_ok(uid):
        if uid in OWNER_IDS or (OWNER_ID2 and uid == OWNER_ID2):
            return True
        return bool(await is_admin(uid, ADMIN_ID))
    run.admin_ok = admin_ok

    async def add_promo(message, parts):
        if not await admin_ok(message.from_user.id):
            return await message.answer('⛔ Нет доступа.')
        if len(parts) == 3:
            code, amount_s, max_s = parts; reward_type = 'money'
        elif len(parts) == 5 and parts[1].lower() in ('unit','tech','equipment'):
            code, _, unit, amount_s, max_s = parts
            if unit.lower() not in UNITS:
                return await message.answer('❌ Неизвестная техника.')
            reward_type = 'unit:' + unit.lower()
        elif len(parts) == 5 and parts[1].lower() in ('case','cases','кейс'):
            code, _, case, amount_s, max_s = parts
            case = {'1':'case1','2':'case2','3':'donate_case','case1':'case1','case2':'case2','donate_case':'donate_case','president':'donate_case'}.get(case.lower())
            if not case:
                return await message.answer('❌ Кейс: case1, case2 или donate_case.')
            reward_type = 'case:' + case
        else:
            return await message.answer('❌ Формат: /addpromo КОД СУММА ЛИМИТ или /addpromo КОД case КЕЙС КОЛИЧЕСТВО ЛИМИТ')
        try:
            amount, max_uses = int(amount_s), int(max_s)
        except ValueError:
            return await message.answer('❌ Количество и лимит должны быть числами.')
        if amount <= 0 or max_uses <= 0:
            return await message.answer('❌ Значения должны быть больше нуля.')
        db = await connect()
        try:
            await db.execute(
                'INSERT INTO promos(code,amount,uses,max_uses,reward_type,reward_amount) VALUES(?,?,0,?,?,?) '
                'ON CONFLICT(code) DO UPDATE SET amount=excluded.amount,uses=0,max_uses=excluded.max_uses,reward_type=excluded.reward_type,reward_amount=excluded.reward_amount',
                (code, amount if reward_type == 'money' else 0, max_uses, reward_type, amount))
            await db.commit()
        finally:
            await db.close()
        return await message.answer(f'✅ Промокод создан/обновлён\n🎟 {code}\n🎁 {reward_type} × {amount}\n👥 Лимит: {max_uses}')
    run.add_promo = add_promo

    async def use_promo_extended(message, code):
        db = await connect()
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
            kind = str(promo['reward_type'] or 'money')
            amount = int(promo['reward_amount'] or promo['amount'] or 0)
            if kind.startswith('case:'):
                case = kind.split(':',1)[1]
                await db.execute('CREATE TABLE IF NOT EXISTS case_inventory(user_id INTEGER PRIMARY KEY,case1 INTEGER NOT NULL DEFAULT 0,case2 INTEGER NOT NULL DEFAULT 0,donate_case INTEGER NOT NULL DEFAULT 0)')
                await db.execute(f'INSERT INTO case_inventory(user_id,{case}) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET {case}={case}+excluded.{case}', (message.from_user.id, amount))
                reward = f'📦 {case} × {amount}'
            elif kind.startswith('unit:'):
                unit = kind.split(':',1)[1]
                if unit not in UNITS: return await message.answer('❌ Некорректная техника.')
                await db.execute(f'UPDATE users SET {unit}={unit}+? WHERE user_id=?', (amount, message.from_user.id))
                reward = f'{UNITS[unit]["title"]} × {amount}'
            else:
                await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?', (amount, message.from_user.id))
                reward = f'💵 +${app.money(amount)}'
            await db.execute('UPDATE promos SET uses=uses+1 WHERE code=?', (promo['code'],))
            await db.execute('INSERT INTO promo_uses(code,user_id) VALUES(?,?)', (promo['code'], message.from_user.id))
            await db.commit()
        finally:
            await db.close()
        return await message.answer(f'🎉 Промокод активирован!\n\nНаграда: {reward}')
    run.use_promo_extended = use_promo_extended

    # Ensure help/bonus are recognized even when the old text dispatcher wins.
    old_text = run.text_handler
    async def text_handler(message, bot, *args, **kwargs):
        low = (message.text or '').strip().lower()
        if low in ('хелп','help','/help','/хелп'):
            return await message.answer('ℹ️ Помощь\n\n🎖 армия\n🛒 шоп\n⚔️ атака\n🎁 бонус\n🎟 промо\n🏆 ачивки\n🏆 топ')
        if low in ('бонус','bonus','/bonus','/бонус'):
            return await message.answer('🎁 Бонус\n\n' + '\n'.join(f'{p:g}% — {label}' for p,_,_,label in __import__('config').DAILY_BONUS_PRIZES))
        return await old_text(message, bot, *args, **kwargs)
    run.text_handler = text_handler

    old_callback = run.callback
    async def callback(c, bot, *args, **kwargs):
        data = str(c.data or '')
        # Group ownership is also enforced by sitecustomize; this is a second layer.
        if getattr(c, 'message', None) and c.message.chat.type in ('group','supergroup'):
            if not data.startswith(('accept:','decline:')):
                return await c.answer('🔒 Это меню принадлежит другому пользователю.', show_alert=True)
        return await old_callback(c, bot, *args, **kwargs)
    run.callback = callback

    old_admin_callback = run.callback
    async def admin_callback(c, bot, *args, **kwargs):
        if c.data == 'a_promos':
            return await app.safe(c, '🎟 ПРОМОКОДЫ\n\n/addpromo КОД СУММА ЛИМИТ\n/addpromo КОД unit ТЕХНИКА КОЛИЧЕСТВО ЛИМИТ\n/addpromo КОД case КЕЙС КОЛИЧЕСТВО ЛИМИТ\n\nКейсы: case1, case2, donate_case', app.back('admin'))
        return await old_admin_callback(c, bot, *args, **kwargs)
    run.callback = admin_callback


class Loader(importlib.abc.Loader):
    def __init__(self, loader): self.loader = loader
    def create_module(self, spec):
        fn = getattr(self.loader, 'create_module', None)
        return fn(spec) if fn else None
    def exec_module(self, module):
        self.loader.exec_module(module)
        patch_run(module)

class Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname != 'run': return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec and spec.loader and not isinstance(spec.loader, Loader): spec.loader = Loader(spec.loader)
        return spec

try:
    patch_core()
except Exception as exc:
    print(f'[WWD final patch] {exc}')
if not any(isinstance(x, Finder) for x in sys.meta_path):
    sys.meta_path.insert(0, Finder())
