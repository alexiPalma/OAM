import bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from db import connect, set_setting, setting, is_admin, all_user_ids


def K(rows):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=a, callback_data=b) for a,b in row] for row in rows])

def B(target='admin'):
    return K([[('⬅️ Назад', target)]])

T = {
 'start':'🏠 Главное меню','profile':'👤 Профиль','army':'🎖 Армия','shop':'🛒 Военный арсенал','farm':'🏭 Ферма','bonus':'🎁 Ежедневный бонус','cases':'📦 Кейсы','donate':'💳 Донат','top':'🏆 Топ вояк','earn':'💰 Заработать','attack':'⚔️ Атака','opponent':'🎯 Противник','battle_start':'⚔️ Бой','battle_result_win':'🏆 Победа','battle_result_loss':'💀 Поражение','help':'ℹ️ Помощь','rules':'📕 Правила',
 'admin_currency':'💰 Админ • Валюта','admin_bonus':'🎁 Админ • Бонусы','admin_cases':'📦 Админ • Кейсы','admin_promos':'🎟 Админ • Промокоды','admin_earn':'💰 Админ • Заработать','admin_donate':'💳 Админ • Донат','admin_rules':'📕 Админ • Правила','admin_admins':'👥 Админ • Админы','admin_give':'🎖 Админ • Выдать / списать','admin_broadcast':'📣 Админ • Рассылка','admin_stats':'📊 Админ • Статистика','admin_edit':'✏️ Админ • Редактировать','admin_farms':'🏭 Админ • Фермы','admin_battles':'⚔️ Админ • Бои'
}

async def _admins_text():
    db=await connect(); cur=await db.execute('SELECT user_id FROM admins ORDER BY user_id'); rows=await cur.fetchall(); await db.close()
    return '\n'.join('• '+str(r['user_id']) for r in rows) or '• нет'

async def admin_section(c,s):
    if not await bot.admin(c.from_user.id): return await c.answer('⛔ Нет доступа.',show_alert=True)
    if s=='a_currency':
        return await bot.safe(c,'💰 ВАЛЮТА\n\n/givecash @user сумма\n\nВыдача валюты работает сразу.',B())
    if s=='a_bonus':
        daily=await setting('daily_bonus','500000')
        return await bot.safe(c,f'🎁 БОНУСЫ\n\n🎁 Ежедневный бонус: ${daily}\n\n🎁 Дополнительные призы теперь поддерживают кейсы.\nСоздание кейсов/призов остаётся в разделе «Кейсы».\n\nИзменить: /setbonus daily сумма',B())
    if s=='a_cases':
        return await bot.safe(c,'📦 КЕЙСЫ\n\n📦 Кейс 1 — $45 000\n75% — 2 солдата\n10% — 10 солдат\n15% — 11 перехватчиков\n\n📦 Кейс 2 — $5 000 000\n80% — БМП\n10% — танк\n7.5% — вертолёт\n2.5% — самолёт\n\n🎖 Президентский — 50 ⭐\n90% — вертолёт\n8% — самолёт\n2% — ракета',B())
    if s=='a_promos':
        return await bot.safe(c,'🎟 ПРОМОКОДЫ\n\nСоздать денежный код:\n/addpromo КОД СУММА ЛИМИТ\n\nТехника:\n/addpromo КОД unit ТЕХНИКА КОЛИЧЕСТВО ЛИМИТ\n\nКейсы:\n/addpromo КОД case КЕЙС КОЛИЧЕСТВО ЛИМИТ\n\nКейс: case1, case2, donate_case\n\nПримеры:\n/addpromo WORLD 500000 100\n/addpromo TANK unit tank 2 10\n/addpromo CASE case case1 1 50\n\nУдалить:\n/deletepromo КОД',K([[('📋 Список промокодов','promo_list')],[('⬅️ Назад','admin')]]))
    if s=='a_earn':
        return await bot.safe(c,'💰 ЗАРАБОТАТЬ\n\nДобавляйте только эти 3 вида:',K([[('🚀 Буст канала','earn_add:boost')],[('📢 Подписка на канал','earn_add:channel')],[('👥 Подписка на группу','earn_add:group')],[('📋 Список заданий','earn_list')],[('⬅️ Назад','admin')]]))
    if s=='a_donate': return await bot.donate(c)
    if s=='a_rules': return await bot.safe(c,'📕 ПРАВИЛА\n\n/setrule новый текст',B())
    if s=='a_admins': return await bot.safe(c,f'👥 АДМИНЫ\n\n{await _admins_text()}\n\nДобавить:\n/addadmin @user\n\nУдалить:\n/deladmin @user',B())
    if s=='a_give': return await bot.safe(c,'🎖 ВЫДАТЬ / СПИСАТЬ\n\n💰 /givecash @user сумма\n🎖 /givepehot @user ID количество\n\n1 — пехота\n2 — перехватчик\n3 — БПЛА\n4 — БМП\n5 — танк\n6 — вертолёт\n7 — самолёт\n8 — ракета\n9 — артиллерия',B())
    if s=='a_broadcast': return await bot.safe(c,'📣 РАССЫЛКА\n\n/broadcast текст\n\nСообщение отправляется всем зарегистрированным игрокам.',B())
    if s=='a_stats': return await bot.safe(c,f'📊 СТАТИСТИКА\n\n👥 Игроков: {await bot.users_count()}',B())
    if s=='a_edit':
        rows=[]
        for key,title in T.items(): rows.append([(title,'editmsg:'+key)])
        rows.append([('⬅️ Назад','admin')])
        return await bot.safe(c,'✏️ РЕДАКТИРОВАТЬ\n\nВыберите ЛЮБОЙ текст. После выбора бот покажет текущую версию, затем вы отправите новый текст.',K(rows))
    if s=='a_farms': return await bot.safe(c,'🏭 ФЕРМЫ\n\nНастройки уровней находятся в config.py.\nВыплата — раз в час.\nМаксимальный налог — $1 000 000.',B())
    if s=='a_battles': return await bot.safe(c,'⚔️ БОИ\n\n⏱ КД атаки: 10 минут\n⏱ Таймер боя: 15 секунд\n📉 Проигравший: −20% армии\n💰 Победитель: 5% от стоимости уничтоженного\n💵 Проигравший: 2% от стоимости своих потерь',B())
    return await bot.safe(c,'⚙️ Раздел не найден.',B())

async def _create_promo(m,p):
    if len(p)==4 and p[2].isdigit() and p[3].isdigit():
        code=p[1].upper(); reward_type='money'; amount=int(p[2]); maxuses=int(p[3])
    elif len(p)==6 and p[2].lower()=='unit' and p[4].isdigit() and p[5].isdigit():
        code=p[1].upper(); reward_type='unit:'+p[3].lower(); amount=int(p[4]); maxuses=int(p[5])
    elif len(p)==6 and p[2].lower()=='case' and p[4].isdigit() and p[5].isdigit():
        code=p[1].upper(); reward_type='case:'+p[3].lower(); amount=int(p[4]); maxuses=int(p[5])
    else:
        return await m.answer('❌ Формат:\n/addpromo КОД СУММА ЛИМИТ\n/addpromo КОД unit ТЕХНИКА КОЛИЧЕСТВО ЛИМИТ\n/addpromo КОД case КЕЙС КОЛИЧЕСТВО ЛИМИТ')
    if amount<=0 or maxuses<=0:return await m.answer('❌ Сумма/количество и лимит должны быть больше 0.')
    if reward_type.startswith('unit:'):
        unit=reward_type.split(':',1)[1]
        if unit not in bot.UNITS:return await m.answer('❌ Неизвестная техника.')
    if reward_type.startswith('case:') and reward_type.split(':',1)[1] not in ('case1','case2','donate_case'):
        return await m.answer('❌ Кейс: case1, case2 или donate_case.')
    db=await connect()
    await db.execute('INSERT OR REPLACE INTO promos(code,amount,uses,max_uses,reward_type,reward_amount) VALUES(?,?,?,?,?,?)',(code,amount,0,maxuses,reward_type,amount))
    await db.commit();await db.close()
    return await m.answer(f'✅ Промокод {code} создан: {reward_type} × {amount} · лимит {maxuses}.')

async def text_handler(m,tg):
    text=(m.text or '').strip();p=text.split();cmd=p[0].split('@')[0].lower() if p else ''
    if cmd in ('/addpromo','/createpromo') and await bot.admin(m.from_user.id): return await _create_promo(m,p)
    if cmd=='/deletepromo' and await bot.admin(m.from_user.id) and len(p)==2:
        db=await connect();cur=await db.execute('DELETE FROM promos WHERE code=?',(p[1].upper(),));await db.commit();await db.close();return await m.answer('✅ Удалено.' if cur.rowcount else '❌ Промокод не найден.')
    if cmd=='/broadcast' and await bot.admin(m.from_user.id) and len(text.split(maxsplit=1))==2:
        msg=text.split(maxsplit=1)[1];ids=await all_user_ids();ok=0
        for uid in ids:
            try:await tg.send_message(uid,msg);ok+=1
            except Exception:pass
        return await m.answer(f'📣 Рассылка завершена: {ok}/{len(ids)}')
    if cmd=='/addadmin' and await bot.admin(m.from_user.id) and len(p)==2:
        target=await bot.find_user(p[1])
        if not target:return await m.answer('❌ Пользователь не найден. Он должен сначала открыть бота.')
        db=await connect();await db.execute('INSERT OR IGNORE INTO admins(user_id) VALUES(?)',(target['user_id'],));await db.commit();await db.close();return await m.answer('✅ Администратор добавлен.')
    if cmd=='/deladmin' and await bot.admin(m.from_user.id) and len(p)==2:
        target=await bot.find_user(p[1])
        if not target:return await m.answer('❌ Пользователь не найден.')
        db=await connect();await db.execute('DELETE FROM admins WHERE user_id=?',(target['user_id'],));await db.commit();await db.close();return await m.answer('✅ Администратор удалён.')
    if cmd=='/promo' and len(p)==2:
        # The real run.py handles /promo CODE, so do not steal it here.
        return await bot._base_text_handler(m,tg)
    st=bot.STATE.get(m.from_user.id)
    if st and st[0]=='editmsg' and await bot.admin(m.from_user.id):
        key=st[1];await set_setting('msg_'+key,text);bot.STATE.pop(m.from_user.id,None);return await m.answer('✅ Текст сохранён.')
    return await bot._base_text_handler(m,tg)

async def callback(c,tg):
    d=c.data or ''
    if d=='promo_list' and await bot.admin(c.from_user.id):
        db=await connect();cur=await db.execute('SELECT code,amount,uses,max_uses,reward_type,reward_amount FROM promos ORDER BY code');rows=await cur.fetchall();await db.close()
        txt='🎟 ПРОМОКОДЫ\n\n'+('\n'.join(f'{r["code"]} — {r["reward_type"]} × {r["reward_amount"]} · {r["uses"]}/{r["max_uses"]}' for r in rows) or 'Промокодов нет.')
        return await bot.safe(c,txt,B('a_promos'))
    if d.startswith('editmsg:') and await bot.admin(c.from_user.id):
        key=d.split(':',1)[1];title=T.get(key,key);current=await setting('msg_'+key);bot.STATE[c.from_user.id]=('editmsg',key);return await bot.safe(c,f'✏️ {title}\n\nТЕКУЩИЙ ТЕКСТ:\n\n{current or "(стандартный текст)"}\n\nОтправьте новый текст одним сообщением.',B('a_edit'))
    return await bot._base_callback(c,tg)

bot._base_text_handler=bot.text_handler
bot._base_callback=bot.callback
bot._base_admin_section=bot.admin_section
bot.admin_section=admin_section
bot.text_handler=text_handler
bot.callback=callback
