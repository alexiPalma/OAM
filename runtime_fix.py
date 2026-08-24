import asyncio
import bot
from db import connect, is_admin
from config import ADMIN_ID, FARMS, UNITS, UNIT_BY_ID
from datetime import datetime, timedelta, timezone

async def _admin(uid):
    return await is_admin(uid, ADMIN_ID)

def _money(v):
    return f'{int(v):,}'.replace(',', ' ')

def _now():
    return datetime.now(timezone.utc)

def _tax_for(income):
    # Exact farm tax: 25% of the farm's hourly income, for every level 1-10.
    return int(income * 0.25)

async def farm(c):
    u=await bot.user(c.from_user.id)
    lvl=max(0,min(10,int(u['farm_level'])))
    f=FARMS[lvl]
    tax=int(u['tax'])
    status='🟢 АКТИВНА' if lvl>0 else '⚪ НЕ РАЗВЁРНУТА'
    await bot.safe(c,
        f'🏭 {bot.BRAND} • ФЕРМА\n\n'
        f'Уровень: {lvl}/10\n'
        f'Производство: ${_money(f["income"])}/час\n'
        f'Налог к оплате: ${_money(tax)}\n'
        f'Ставка налога: 25%\n'
        f'Статус: {status}',
        bot.kb([[('💰 Получить','payout'),('⬆️ Улучшить','upgrade')],
                [('💸 Оплатить налог','paytax')],
                [('⬅️ Назад','home')]]))

async def payout(c):
    u=await bot.user(c.from_user.id)
    lvl=int(u['farm_level'])
    if lvl<=0:
        return await bot.safe(c,'🏭 Сначала улучшите ферму до 1 уровня за $500 000.',bot.back('farm'))
    if int(u['tax'])>0:
        return await bot.safe(c,f'❌ Сначала оплатите налог: ${_money(u["tax"])}.',bot.back('farm'))
    try:
        last=datetime.fromisoformat(u['last_payout'])
        if last.tzinfo is None: last=last.replace(tzinfo=timezone.utc)
    except Exception:
        last=_now()-timedelta(hours=1)
    if _now()-last<timedelta(hours=1):
        return await bot.safe(c,'⏳ Выплата доступна один раз в час.',bot.back('farm'))
    income=int(FARMS[lvl]['income'])
    tax=_tax_for(income)
    db=await connect()
    await db.execute('UPDATE users SET balance=balance+?,last_payout=?,tax=? WHERE user_id=?',(income,_now().isoformat(),tax,c.from_user.id))
    await db.commit(); await db.close()
    await bot.safe(c,f'💰 Получено: +${_money(income)}\n💸 Налог 25%: ${_money(tax)}\n\nСледующая выплата — через 1 час.',bot.back('farm'))

async def paytax(c):
    u=await bot.user(c.from_user.id); tax=int(u['tax'])
    if tax<=0:
        return await bot.safe(c,'✅ Налог к оплате отсутствует.',bot.back('farm'))
    if int(u['balance'])<tax:
        return await bot.safe(c,f'❌ Недостаточно средств. Нужно ${_money(tax)}.',bot.back('farm'))
    db=await connect(); await db.execute('UPDATE users SET balance=balance-?,tax=0 WHERE user_id=?',(tax,c.from_user.id)); await db.commit(); await db.close()
    await bot.safe(c,f'✅ Налог ${_money(tax)} оплачен.',bot.back('farm'))

async def upgrade(c):
    u=await bot.user(c.from_user.id); lvl=int(u['farm_level'])
    if lvl>=10:return await bot.safe(c,'🏭 Ферма уже на максимальном 10 уровне.',bot.back('farm'))
    cost=int(FARMS[lvl+1]['upgrade'])
    db=await connect();cur=await db.execute('UPDATE users SET balance=balance-?,farm_level=? WHERE user_id=? AND balance>=?',(cost,lvl+1,c.from_user.id,cost));await db.commit();await db.close()
    if cur.rowcount!=1:return await bot.safe(c,f'❌ Для {lvl+1} уровня нужно ${_money(cost)}.',bot.back('farm'))
    await bot.safe(c,f'⬆️ Ферма улучшена: {lvl} → {lvl+1} уровень.\n💵 Списано: ${_money(cost)}',bot.back('farm'))

async def admin_section(c,s):
    if not await _admin(c.from_user.id): return await c.answer('Нет доступа.',show_alert=True)
    if s=='a_promos': return await bot.safe(c,'🎟 ПРОМОКОДЫ\n\nСоздать:\n/createpromo КОД СУММА ЛИМИТ\nУдалить:\n/deletepromo КОД\n\nИгрок активирует:\n/promo КОД',bot.back('admin'))
    if s=='a_admins': return await bot.safe(c,'👥 АДМИНЫ\n\n/addadmin @user\n/deladmin @user',bot.back('admin'))
    if s=='a_broadcast': return await bot.safe(c,'📣 РАССЫЛКА\n\n/broadcast текст',bot.back('admin'))
    if s=='a_farms': return await bot.safe(c,'🏭 ФЕРМЫ\n\n0 уровень — старт\n1 уровень — $500 000\n2 уровень — $900 000\n3 уровень — $1 000 000\n4 уровень — $2 000 000\n5 уровень — $3 000 000\n6 уровень — $6 000 000\n7 уровень — $9 000 000\n8 уровень — $11 000 000\n9 уровень — $18 000 000\n10 уровень — $30 000 000\n\nНалог: ровно 25% от часового дохода.',bot.back('admin'))
    return await bot._original_admin_section(c,s)

async def text_handler(m,tg_bot):
    text=(m.text or '').strip();p=text.split();cmd=p[0].split('@')[0].lower() if p else ''
    if cmd=='/promo' and len(p)==2:
        await bot.ensure_user(m.from_user.id,m.from_user.username)
        db=await connect();cur=await db.execute('SELECT code,amount,uses,max_uses FROM promos WHERE lower(code)=lower(?)',(p[1],));pr=await cur.fetchone()
        if not pr: await db.close();return await m.answer('❌ Промокод не найден.')
        used=await db.execute('SELECT 1 FROM promo_uses WHERE code=? AND user_id=?',(pr['code'],m.from_user.id));already=await used.fetchone()
        if already: await db.close();return await m.answer('❌ Вы уже использовали этот промокод.')
        if pr['uses']>=pr['max_uses']: await db.close();return await m.answer('❌ Лимит активаций исчерпан.')
        await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(pr['amount'],m.from_user.id));await db.execute('UPDATE promos SET uses=uses+1 WHERE code=?',(pr['code'],));await db.execute('INSERT INTO promo_uses(code,user_id) VALUES(?,?)',(pr['code'],m.from_user.id));await db.commit();await db.close();return await m.answer(f'🎉 Промокод активирован! +${bot.money(pr["amount"])}')
    if await _admin(m.from_user.id):
        if cmd=='/createpromo' and len(p)==4 and p[2].isdigit() and p[3].isdigit():
            db=await connect();await db.execute('INSERT OR REPLACE INTO promos(code,amount,max_uses,uses) VALUES(?,?,?,0)',(p[1],int(p[2]),int(p[3])));await db.commit();await db.close();return await m.answer('✅ Промокод создан.')
        if cmd=='/deletepromo' and len(p)==2:
            db=await connect();await db.execute('DELETE FROM promos WHERE lower(code)=lower(?)',(p[1],));await db.execute('DELETE FROM promo_uses WHERE lower(code)=lower(?)',(p[1],));await db.commit();await db.close();return await m.answer('✅ Промокод удалён.')
        if cmd=='/addadmin' and len(p)==2:
            target=await bot.find_user(p[1]);
            if not target:return await m.answer('❌ Пользователь не найден. Он должен сначала открыть бота.')
            db=await connect();await db.execute('INSERT OR IGNORE INTO admins(user_id) VALUES(?)',(target['user_id'],));await db.commit();await db.close();return await m.answer('✅ Админ добавлен.')
        if cmd=='/deladmin' and len(p)==2:
            target=await bot.find_user(p[1]);
            if not target:return await m.answer('❌ Пользователь не найден.')
            db=await connect();await db.execute('DELETE FROM admins WHERE user_id=?',(target['user_id'],));await db.commit();await db.close();return await m.answer('✅ Админ удалён.')
        if cmd=='/broadcast' and len(p)>1:
            ids=await bot.all_user_ids();sent=0
            for uid in ids:
                try: await tg_bot.send_message(uid,text.split(maxsplit=1)[1]);sent+=1
                except Exception: pass
            return await m.answer(f'📣 Рассылка завершена: {sent}/{len(ids)}')
    return await bot._original_text_handler(m,tg_bot)

async def callback(c,tg_bot):
    d=c.data or ''
    try:
        # Hard-route the farm callbacks to the corrected 0-10/25% implementation.
        if d=='farm': return await farm(c)
        if d=='payout': return await payout(c)
        if d=='paytax': return await paytax(c)
        if d=='upgrade': return await upgrade(c)
        # Everything else uses the original, known-good callback router.
        return await bot._original_callback(c,tg_bot)
    except Exception as e:
        try: await c.answer('Произошла ошибка. Попробуйте ещё раз.',show_alert=True)
        except Exception: pass
        print('callback error:',repr(e))

def install():
    # Keep the original handlers exactly once; runtime patches only the parts that need overriding.
    if not hasattr(bot,'_original_admin_section'):
        bot._original_admin_section=bot.admin_section
        bot._original_text_handler=bot.text_handler
        bot._original_callback=bot.callback
    bot.admin_section=admin_section
    bot.text_handler=text_handler
    bot.callback=callback
    bot.farm=farm
    bot.payout=payout
    bot.paytax=paytax
    bot.upgrade=upgrade
