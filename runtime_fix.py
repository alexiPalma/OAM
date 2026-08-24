import bot
from db import connect, is_admin
from config import ADMIN_ID, UNIT_BY_ID

async def _admin(uid): return await is_admin(uid, ADMIN_ID)

async def admin_section(c,s):
    if not await _admin(c.from_user.id): return await c.answer('Нет доступа.',show_alert=True)
    if s=='a_promos': return await bot.safe(c,'🎟 ПРОМОКОДЫ\n\nСоздание:\n/createpromo КОД СУММА ЛИМИТ\nУдаление:\n/deletepromo КОД\n\nИгрок активирует: /promo КОД',bot.back('admin'))
    if s=='a_admins': return await bot.safe(c,'👥 АДМИНЫ\n\n/addadmin @user\n/deladmin @user',bot.back('admin'))
    if s=='a_broadcast': return await bot.safe(c,'📣 РАССЫЛКА\n\n/broadcast текст',bot.back('admin'))
    if s=='a_farms': return await bot.safe(c,'🏭 ФЕРМЫ\n\n0 уровень — старт\n1 уровень — $500 000\n2 уровень — $900 000\n3 уровень — $1 000 000\n4 уровень — $2 000 000\n5 уровень — $3 000 000\n6 уровень — $6 000 000\n7 уровень — $9 000 000\n8 уровень — $11 000 000\n9 уровень — $18 000 000\n10 уровень — $30 000 000',bot.back('admin'))
    return await bot._original_admin_section(c,s)

async def text_handler(m,tg_bot):
    text=(m.text or '').strip();p=text.split();cmd=p[0].split('@')[0].lower() if p else ''
    if cmd=='/promo' and len(p)==2:
        await bot.ensure_user(m.from_user.id,m.from_user.username)
        db=await connect();cur=await db.execute('SELECT amount,uses,max_uses FROM promos WHERE lower(code)=lower(?)',(p[1],));pr=await cur.fetchone()
        if not pr: await db.close();return await m.answer('❌ Промокод не найден.')
        used=await db.execute('SELECT 1 FROM promo_uses WHERE code=(SELECT code FROM promos WHERE lower(code)=lower(?)) AND user_id=?',(p[1],m.from_user.id));already=await used.fetchone()
        if already: await db.close();return await m.answer('❌ Вы уже использовали этот промокод.')
        if pr['uses']>=pr['max_uses']: await db.close();return await m.answer('❌ Лимит активаций исчерпан.')
        await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(pr['amount'],m.from_user.id));await db.execute('UPDATE promos SET uses=uses+1 WHERE lower(code)=lower(?)',(p[1],));await db.execute('INSERT INTO promo_uses(code,user_id) SELECT code,? FROM promos WHERE lower(code)=lower(?)',(m.from_user.id,p[1]));await db.commit();await db.close();return await m.answer(f'🎉 Промокод активирован! +${bot.money(pr["amount"])}')
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

async def callback(c,tg_bot): return await bot._original_callback(c,tg_bot)

def install():
    bot._original_admin_section=bot.admin_section
    bot._original_text_handler=bot.text_handler
    bot._original_callback=bot.callback
    bot.admin_section=admin_section
    bot.text_handler=text_handler
    bot.callback=callback
