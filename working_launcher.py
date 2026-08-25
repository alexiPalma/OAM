"""Clean production launcher for OAM.

This launcher intentionally does NOT use config.py's runtime patcher.  It imports
run normally, then owns the dispatcher registration itself.  That avoids nested
callback wrappers which were causing Telegram callback exceptions.
"""
import asyncio
import contextvars

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart

import run
import bot as app
from config import BOT_TOKEN, ADMIN_ID, OWNER_IDS, UNITS
from db import connect, init_db, is_admin, top_users
from settings import init_settings
import achievements

OWNER = contextvars.ContextVar("menu_owner", default=None)
PROMO_WAIT = set()
CODES = {
    1: "soldier", 2: "interceptor", 3: "drone", 4: "bmp", 5: "tank",
    6: "helicopter", 7: "plane", 8: "missile", 9: "artillery",
}
CASES = ("case1", "case2", "donate_case")


def scoped_kb(rows):
    owner = OWNER.get()
    if not owner:
        return app.kb(rows)
    scoped = []
    for row in rows:
        new = []
        for item in row:
            if isinstance(item, (tuple, list)) and len(item) == 2:
                text, data = item
                data = str(data)
                if not data.startswith(("accept:", "decline:", "g:")):
                    data = f"g:{owner}:{data}"
                new.append((text, data))
            else:
                new.append(item)
        scoped.append(new)
    return app.kb(scoped)


def unit_codes_text():
    names = {
        1:"🪖 Пехота",2:"🎯 Перехватчик",3:"🛩 БПЛА",4:"🚙 БМП",5:"🛡 Танк",
        6:"🚁 Вертолёт",7:"✈️ Самолёт",8:"🚀 Ракета",9:"💥 Артиллерия"
    }
    return "КОДЫ ТЕХНИКИ:\n\n" + "\n".join(f"{i} — {n}" for i,n in names.items()) + \
        "\n\nВыдача:\n/givepehot @username КОД КОЛИЧЕСТВО\n\nПример:\n/givepehot @macrasoft 1 100"


async def admin_access(uid):
    return uid in OWNER_IDS or bool(await is_admin(uid, ADMIN_ID))


async def help_cmd(m):
    return await m.answer(
        "ℹ️ ПОМОЩЬ\n\n"
        "хелп / help — помощь\nбонус / bonus — ежедневный бонус\n"
        "армия / а — армия\nшоп — магазин\nатака / вызовы — бой\n"
        "промо — промокод\nачивки — достижения\nтоп — рейтинг"
    )


async def bonus_keyword(m):
    return await m.answer(
        "🎁 ЕЖЕДНЕВНЫЙ БОНУС\n\nНажмите кнопку ниже, чтобы открыть бонус.",
        reply_markup=scoped_kb([[('🎁 Открыть бонус', 'bonus')], [('⬅️ Назад', 'home')]])
    )


async def codes(m):
    if not await admin_access(m.from_user.id):
        return await m.answer("⛔ Нет доступа.")
    return await m.answer(unit_codes_text())


async def give(m, parts):
    if not await admin_access(m.from_user.id):
        return await m.answer("⛔ Нет доступа.")
    if len(parts) != 3:
        return await m.answer("❌ Формат:\n/givepehot @username КОД КОЛИЧЕСТВО\n\n" + unit_codes_text())
    target = await app.find_user(parts[0])
    try:
        code, amount = int(parts[1]), int(parts[2])
    except ValueError:
        return await m.answer("❌ Код и количество должны быть числами.")
    if not target or code not in CODES or amount <= 0:
        return await m.answer("❌ Неверные данные.\n\n" + unit_codes_text())
    unit = CODES[code]
    db = await connect()
    try:
        await db.execute(f"UPDATE users SET {unit}={unit}+? WHERE user_id=?", (amount, target['user_id']))
        await db.commit()
    finally:
        await db.close()
    return await m.answer(f"✅ Выдано: {UNITS[unit]['title']} × {amount}\n\nКод: {code}")


async def addpromo(m, p):
    if not await admin_access(m.from_user.id):
        return await m.answer("⛔ Нет доступа.")
    if len(p) == 3:
        code, amount_s, limit_s = p; reward_type = 'money'
    elif len(p) == 5 and p[1].lower() in ('unit','tech','equipment'):
        code, _, unit, amount_s, limit_s = p; unit = unit.lower()
        if unit not in UNITS: return await m.answer("❌ Неизвестная техника.\n\n" + unit_codes_text())
        reward_type = 'unit:' + unit
    elif len(p) == 5 and p[1].lower() in ('case','cases'):
        code, _, case, amount_s, limit_s = p; case = case.lower()
        if case not in CASES: return await m.answer("❌ Кейс: case1, case2, donate_case")
        reward_type = 'case:' + case
    else:
        return await m.answer(
            "/addpromo КОД СУММА ЛИМИТ\n"
            "/addpromo КОД unit ТЕХНИКА КОЛИЧЕСТВО ЛИМИТ\n"
            "/addpromo КОД case КЕЙС КОЛИЧЕСТВО ЛИМИТ\n\n"
            "Техника: soldier, interceptor, drone, bmp, artillery, tank, helicopter, plane, missile\n"
            "Кейсы: case1, case2, donate_case"
        )
    try: amount, limit = int(amount_s), int(limit_s)
    except ValueError: return await m.answer("❌ Количество и лимит должны быть числами.")
    if amount <= 0 or limit <= 0: return await m.answer("❌ Значения должны быть больше нуля.")
    db = await connect()
    try:
        await db.execute(
            """INSERT INTO promos(code,amount,uses,max_uses,reward_type,reward_amount)
               VALUES(?,?,0,?,?,?)
               ON CONFLICT(code) DO UPDATE SET amount=excluded.amount,max_uses=excluded.max_uses,
               reward_type=excluded.reward_type,reward_amount=excluded.reward_amount""",
            (code, amount if reward_type == 'money' else 0, limit, reward_type, amount)
        )
        await db.commit()
    finally: await db.close()
    return await m.answer(f"✅ Промокод создан: {code}\n🎁 {reward_type} × {amount}\n👥 Лимит: {limit}")


async def usepromo(m, code):
    db = await connect()
    try:
        cur = await db.execute("SELECT * FROM promos WHERE lower(code)=lower(?)", (code.strip(),)); p = await cur.fetchone()
        if not p: return await m.answer("❌ Промокод не найден.")
        if int(p['uses']) >= int(p['max_uses']): return await m.answer("❌ Промокод больше недоступен.")
        cur = await db.execute("SELECT 1 FROM promo_uses WHERE code=? AND user_id=?", (p['code'], m.from_user.id))
        if await cur.fetchone(): return await m.answer("❌ Вы уже использовали этот промокод.")
        rt = str(p['reward_type'] or 'money'); amount = int(p['reward_amount'] or p['amount'] or 0)
        if rt == 'money':
            await db.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, m.from_user.id)); reward=f"💵 +${app.money(amount)}"
        elif rt.startswith('unit:'):
            unit=rt[5:]
            if unit not in UNITS: return await m.answer("❌ Неизвестная техника.")
            await db.execute(f"UPDATE users SET {unit}={unit}+? WHERE user_id=?", (amount,m.from_user.id)); reward=f"{UNITS[unit]['title']} × {amount}"
        elif rt.startswith('case:'):
            case=rt[5:]
            if case not in CASES: return await m.answer("❌ Неизвестный кейс.")
            await db.execute("CREATE TABLE IF NOT EXISTS case_inventory(user_id INTEGER PRIMARY KEY,case1 INTEGER NOT NULL DEFAULT 0,case2 INTEGER NOT NULL DEFAULT 0,donate_case INTEGER NOT NULL DEFAULT 0)")
            vals=(amount if case=='case1' else 0, amount if case=='case2' else 0, amount if case=='donate_case' else 0)
            await db.execute("INSERT INTO case_inventory(user_id,case1,case2,donate_case) VALUES(?,?,?,?,?)".replace('VALUES(?,?,?,?,?)','VALUES(?,?,?,?)')+" ON CONFLICT(user_id) DO UPDATE SET case1=case1+excluded.case1,case2=case2+excluded.case2,donate_case=donate_case+excluded.donate_case", (m.from_user.id,*vals)); reward=f"📦 {case} × {amount}"
        else: return await m.answer("❌ Неизвестный тип награды.")
        await db.execute("UPDATE promos SET uses=uses+1 WHERE code=?", (p['code'],)); await db.execute("INSERT INTO promo_uses(code,user_id) VALUES(?,?)", (p['code'],m.from_user.id)); await db.commit()
    finally: await db.close()
    return await m.answer(f"🎉 Промокод активирован!\n\nНаграда: {reward}")


async def callback(c, tg_bot):
    data = c.data or ''
    group = bool(c.message and c.message.chat.type != 'private')
    if group and data.startswith('g:'):
        _, owner_s, real = data.split(':', 2)
        if int(owner_s) != c.from_user.id and not real.startswith(('accept:','decline:')):
            return await c.answer("⛔ Это меню принадлежит другому пользователю.", show_alert=True)
        c.data = real; data = real
    elif group and not data.startswith(('accept:','decline:')):
        return await c.answer("⛔ Это меню нельзя использовать другому пользователю.", show_alert=True)
    if data == 'shop':
        return await shop(c)
    if data.startswith('buyq:'):
        return await buyq(c, data[5:])
    if data == 'top':
        return await top(c)
    if data == 'help':
        return await help_cmd(c.message)
    return await run.callback(c, tg_bot)


async def shop(c):
    token=OWNER.set(c.from_user.id if c.message and c.message.chat.type!='private' else None)
    try:
        rows=[]
        for k,v in UNITS.items(): rows.append([(f"{v['title']} — ${app.money(v['price'])}",f"buyq:{k}")])
        rows.append([('⬅️ Назад','home')])
        return await app.safe(c, '🛒 АРСЕНАЛ\n\n'+'\n'.join(f"{v['title']} — ${app.money(v['price'])}" for v in UNITS.values()), scoped_kb(rows))
    finally: OWNER.reset(token)


async def buyq(c,k):
    if k not in UNITS: return await c.answer('Недоступно',show_alert=True)
    app.STATE[c.from_user.id]=('buy',k)
    return await app.safe(c, f"🛒 {UNITS[k]['title']}\n\nЦена: ${app.money(UNITS[k]['price'])}\n\nВведите количество:", app.back('shop'))


async def top(c):
    rows=await top_users(50); out=[]
    for i,r in enumerate(rows,1):
        medal=('🥇','🥈','🥉')[i-1] if i<=3 else '🎖️'; name='@'+r['username'] if r['username'] else f"ID {r['user_id']}"
        out.append(f"{medal} {i}. {name} — 🎖 {int(r['army_total'])}")
    return await app.safe(c,'🏆 ТОП ВОЯК\n\n'+('\n'.join(out) or 'Пока игроков нет.')+'\n\nРейтинг: 1/1/3/7/8/10/15/25/50', app.back())


async def text_handler(m, tg_bot):
    text=(m.text or '').strip(); low=text.lower(); p=text.split(); cmd=p[0].split('@')[0].lower() if p else ''
    if low in ('хелп','help','/help','/хелп'): return await help_cmd(m)
    if low in ('бонус','bonus','/bonus','/бонус'): return await bonus_keyword(m)
    if cmd in ('/коды','/codes','коды','codes'): return await codes(m)
    if cmd=='/givepehot': return await give(m,p[1:])
    if cmd=='/addpromo': return await addpromo(m,p[1:])
    if cmd in ('/promo','/промо','/промокод') and len(p)>1: return await usepromo(m,p[1])
    if low in ('промо','промокод','promo','/promo','/промо','/промокод'):
        PROMO_WAIT.add(m.from_user.id); return await m.answer('🎟 Введите промокод:')
    if m.from_user.id in PROMO_WAIT and not text.startswith('/'):
        PROMO_WAIT.discard(m.from_user.id); return await usepromo(m,text)
    return await run.text_handler(m,tg_bot)


async def main():
    if not BOT_TOKEN: raise RuntimeError('BOT_TOKEN is empty')
    await init_db(); await init_settings(ADMIN_ID)
    db=await connect()
    try:
        await db.execute('INSERT OR IGNORE INTO admins(user_id) VALUES(?)',(ADMIN_ID,)); await db.commit()
    finally: await db.close()
    await achievements.init_achievements()
    tg=Bot(BOT_TOKEN); dp=Dispatcher()
    dp.message.register(run.start_wrapper, CommandStart())
    dp.message.register(text_handler, F.text)
    dp.callback_query.register(callback, F.data)
    print('OAM working launcher started')
    await dp.start_polling(tg)

if __name__=='__main__': asyncio.run(main())
