import bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from db import connect, set_setting, setting, is_admin, all_user_ids


def K(rows):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=a, callback_data=b) for a,b in row] for row in rows])

def B(target='admin'):
    return K([[('⬅️ Назад', target)]])

UNITS = bot.UNITS
UNIT_BUTTONS = [
    ('🪖 Солдаты','soldier'), ('🎯 Перехватчики','interceptor'),
    ('🛩 БПЛА','drone'), ('🚙 БМП','bmp'), ('🛡 Танки','tank'),
    ('🚁 Вертолёты','helicopter'), ('✈️ Самолёты','plane'),
    ('🚀 Ракеты','missile'), ('💥 Артиллерия','artillery')
]
CASE_BUTTONS = [('📦 Кейс 1','case1'),('📦 Кейс 2','case2'),('🎖 Президентский','donate_case')]

async def promo_menu(c):
    text = (
        '🎟 ПРОМОКОДЫ\n\n'
        'Здесь можно полностью управлять промокодами.\n\n'
        '➕ Создание — выбрать тип награды и пройти короткую настройку.\n'
        '📋 Список — посмотреть все активные коды и их лимиты.\n'
        '🗑 Удаление — выбрать код из списка и удалить его.\n\n'
        '🎁 Награды поддерживают деньги, любую технику и кейсы.'
    )
    return await bot.safe(c, text, K([
        [('➕ Создать промокод','promo_create')],
        [('📋 Все промокоды','promo_list')],
        [('🗑 Удалить промокод','promo_delete')],
        [('⬅️ Назад','admin')]
    ]))

async def promo_list(c):
    db=await connect();cur=await db.execute('SELECT code,amount,uses,max_uses,reward_type,reward_amount FROM promos ORDER BY code');rows=await cur.fetchall();await db.close()
    if not rows:
        text='🎟 ПРОМОКОДЫ\n\nПока промокодов нет.'
    else:
        lines=[]
        for r in rows:
            rt=str(r['reward_type'] or 'money')
            if rt=='money': reward=f'💰 ${int(r["reward_amount"]):,}'.replace(',',' ')
            elif rt.startswith('unit:'):
                unit=rt.split(':',1)[1]; reward=f'{UNITS.get(unit,{}).get("title",unit)} × {int(r["reward_amount"])}'
            elif rt.startswith('case:'):
                case=rt.split(':',1)[1]; names={'case1':'📦 Кейс 1','case2':'📦 Кейс 2','donate_case':'🎖 Президентский'}; reward=f'{names.get(case,case)} × {int(r["reward_amount"])}'
            else: reward=f'{rt} × {int(r["reward_amount"])}'
            lines.append(f'🎟 <b>{r["code"]}</b>\n{reward}\n📊 Активации: {r["uses"]}/{r["max_uses"]}')
        text='🎟 ПРОМОКОДЫ • СПИСОК\n\n'+'\n\n'.join(lines)
    return await bot.safe(c,text,B('a_promos'))

async def promo_delete_menu(c):
    db=await connect();cur=await db.execute('SELECT code FROM promos ORDER BY code');rows=await cur.fetchall();await db.close()
    if not rows:return await bot.safe(c,'🗑 УДАЛЕНИЕ ПРОМОКОДА\n\nПромокодов нет.',B('a_promos'))
    buttons=[[(f'🗑 {r["code"]}',f'promo_del:{r["code"]}')] for r in rows]
    buttons.append([('⬅️ Назад','a_promos')])
    return await bot.safe(c,'🗑 УДАЛИТЬ ПРОМОКОД\n\nВыберите код:',K(buttons))

async def admin_section(c, s):
    if not await bot.admin(c.from_user.id): return await c.answer('⛔ Нет доступа.',show_alert=True)
    if s=='a_currency': return await bot.safe(c,'💰 ВАЛЮТА\n\n/givecash @user сумма\n\nВыдача валюты работает сразу.',B())
    if s=='a_bonus':
        daily=await setting('daily_bonus','500000')
        return await bot.safe(c,f'🎁 БОНУСЫ\n\n🎁 Ежедневный бонус: ${daily}\n\n🎁 Дополнительные призы теперь поддерживают кейсы.\nСоздание кейсов/призов остаётся в разделе «Кейсы».\n\nИзменить: /setbonus daily сумма',B())
    if s=='a_cases': return await bot.safe(c,'📦 КЕЙСЫ\n\n📦 Кейс 1 — $45 000\n75% — 2 солдата\n10% — 10 солдат\n15% — 11 перехватчиков\n\n📦 Кейс 2 — $5 000 000\n80% — БМП\n10% — танк\n7.5% — вертолёт\n2.5% — самолёт\n\n🎖 Президентский — 50 ⭐\n90% — вертолёт\n8% — самолёт\n2% — ракета',B())
    if s=='a_promos': return await promo_menu(c)
    if s=='a_earn': return await bot.safe(c,'💰 ЗАРАБОТАТЬ\n\nДобавляйте только эти 3 вида:',K([[('🚀 Буст канала','earn_add:boost')],[('📢 Подписка на канал','earn_add:channel')],[('👥 Подписка на группу','earn_add:group')],[('📋 Список заданий','earn_list')],[('⬅️ Назад','admin')]]))
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

async def _admins_text():
    db=await connect(); cur=await db.execute('SELECT user_id FROM admins ORDER BY user_id'); rows=await cur.fetchall(); await db.close()
    return '\n'.join('• '+str(r['user_id']) for r in rows) or '• нет'

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
    if reward_type.startswith('unit:') and reward_type.split(':',1)[1] not in UNITS:return await m.answer('❌ Неизвестная техника.')
    if reward_type.startswith('case:') and reward_type.split(':',1)[1] not in ('case1','case2','donate_case'):return await m.answer('❌ Кейс: case1, case2 или donate_case.')
    db=await connect();await db.execute('INSERT OR REPLACE INTO promos(code,amount,uses,max_uses,reward_type,reward_amount) VALUES(?,?,?,?,?,?)',(code,amount,0,maxuses,reward_type,amount));await db.commit();await db.close()
    return await m.answer(f'✅ Промокод {code} создан: {reward_type} × {amount} · лимит {maxuses}.')

async def _save_promo_state(m,state):
    bot.STATE[m.from_user.id]=state
    prompts={
        'money_code':'🎟 СОЗДАНИЕ • ДЕНЬГИ\n\nВведите код промокода:',
        'money_amount':'💰 Введите сумму награды:',
        'money_limit':'🔢 Введите максимальное количество активаций:',
        'unit_code':'🎖 СОЗДАНИЕ • ТЕХНИКА\n\nВведите код промокода:',
        'unit_amount':'🔢 Введите количество техники:',
        'unit_limit':'📊 Введите максимальное количество активаций:',
        'case_code':'📦 СОЗДАНИЕ • КЕЙС\n\nВведите код промокода:',
        'case_amount':'🔢 Введите количество кейсов:',
        'case_limit':'📊 Введите максимальное количество активаций:'
    }
    return await m.answer(prompts[state[0]])

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
    if cmd=='/promo' and len(p)==2: return await bot._base_text_handler(m,tg)

    st=bot.STATE.get(m.from_user.id)
    if st and await bot.admin(m.from_user.id):
        kind=st[0]
        if kind=='promo_money_code':
            bot.STATE[m.from_user.id]=('promo_money_amount',text);return await m.answer('💰 Введите сумму награды:')
        if kind=='promo_money_amount' and text.isdigit() and int(text)>0:
            bot.STATE[m.from_user.id]=('promo_money_limit',st[1],int(text));return await m.answer('🔢 Введите максимальное количество активаций:')
        if kind=='promo_money_limit' and text.isdigit() and int(text)>0:
            code,amount=st[1],st[2];bot.STATE.pop(m.from_user.id,None);return await _create_promo(m,['/addpromo',code,str(amount),text])
        if kind=='promo_unit_code':
            bot.STATE[m.from_user.id]=('promo_unit_amount',st[1],text.upper());return await m.answer('🔢 Введите количество техники:')
        if kind=='promo_unit_amount' and text.isdigit() and int(text)>0:
            bot.STATE[m.from_user.id]=('promo_unit_limit',st[1],st[2],int(text));return await m.answer('📊 Введите максимальное количество активаций:')
        if kind=='promo_unit_limit' and text.isdigit() and int(text)>0:
            unit,code,amount=st[1],st[2],st[3];bot.STATE.pop(m.from_user.id,None);return await _create_promo(m,['/addpromo',code,'unit',unit,str(amount),text])
        if kind=='promo_case_code':
            bot.STATE[m.from_user.id]=('promo_case_amount',st[1],text.upper());return await m.answer('🔢 Введите количество кейсов:')
        if kind=='promo_case_amount' and text.isdigit() and int(text)>0:
            bot.STATE[m.from_user.id]=('promo_case_limit',st[1],st[2],int(text));return await m.answer('📊 Введите максимальное количество активаций:')
        if kind=='promo_case_limit' and text.isdigit() and int(text)>0:
            case,code,amount=st[1],st[2],st[3];bot.STATE.pop(m.from_user.id,None);return await _create_promo(m,['/addpromo',code,'case',case,str(amount),text])
        if kind=='promo_delete_code':
            code=text.upper();bot.STATE.pop(m.from_user.id,None);db=await connect();cur=await db.execute('DELETE FROM promos WHERE code=?',(code,));await db.commit();await db.close();return await m.answer('✅ Промокод удалён.' if cur.rowcount else '❌ Промокод не найден.')
        if kind=='editmsg' and await bot.admin(m.from_user.id):
            key=st[1];await set_setting('msg_'+key,text);bot.STATE.pop(m.from_user.id,None);return await m.answer('✅ Текст сохранён.')
    return await bot._base_text_handler(m,tg)

async def callback(c,tg):
    d=c.data or ''
    if d=='promo_create' and await bot.admin(c.from_user.id):
        return await bot.safe(c,'➕ СОЗДАНИЕ ПРОМОКОДА\n\nВыберите тип награды:',K([
            [('💰 Деньги','promo_type:money')],[('🎖 Техника','promo_type:unit')],[('📦 Кейс','promo_type:case')],[('⬅️ Назад','a_promos')]
        ]))
    if d=='promo_type:money' and await bot.admin(c.from_user.id):
        bot.STATE[c.from_user.id]=('promo_money_code',);return await bot.safe(c,'💰 СОЗДАНИЕ • ДЕНЬГИ\n\nВведите код промокода:',B('promo_create'))
    if d=='promo_type:unit' and await bot.admin(c.from_user.id):
        rows=[[ (a,f'promo_unit:{b}') ] for a,b in UNIT_BUTTONS];rows.append([('⬅️ Назад','promo_create')]);return await bot.safe(c,'🎖 СОЗДАНИЕ • ТЕХНИКА\n\nВыберите технику:',K(rows))
    if d.startswith('promo_unit:') and await bot.admin(c.from_user.id):
        unit=d.split(':',1)[1];bot.STATE[c.from_user.id]=('promo_unit_code',unit);return await bot.safe(c,f'🎖 {UNITS.get(unit,{}).get("title",unit)}\n\nВведите код промокода:',B('promo_type:unit'))
    if d=='promo_type:case' and await bot.admin(c.from_user.id):
        rows=[[(a,f'promo_case:{b}')] for a,b in CASE_BUTTONS];rows.append([('⬅️ Назад','promo_create')]);return await bot.safe(c,'📦 СОЗДАНИЕ • КЕЙС\n\nВыберите кейс:',K(rows))
    if d.startswith('promo_case:') and await bot.admin(c.from_user.id):
        case=d.split(':',1)[1];names={'case1':'📦 Кейс 1','case2':'📦 Кейс 2','donate_case':'🎖 Президентский'};bot.STATE[c.from_user.id]=('promo_case_code',case);return await bot.safe(c,f'{names.get(case,case)}\n\nВведите код промокода:',B('promo_type:case'))
    if d=='promo_list' and await bot.admin(c.from_user.id): return await promo_list(c)
    if d=='promo_delete' and await bot.admin(c.from_user.id): return await promo_delete_menu(c)
    if d.startswith('promo_del:') and await bot.admin(c.from_user.id):
        code=d.split(':',1)[1];db=await connect();cur=await db.execute('DELETE FROM promos WHERE code=?',(code.upper(),));await db.commit();await db.close();return await promo_delete_menu(c) if cur.rowcount else await bot.safe(c,'❌ Промокод не найден.',B('a_promos'))
    if d.startswith('editmsg:') and await bot.admin(c.from_user.id):
        key=d.split(':',1)[1];title=T.get(key,key);current=await setting('msg_'+key);bot.STATE[c.from_user.id]=('editmsg',key);return await bot.safe(c,f'✏️ {title}\n\nТЕКУЩИЙ ТЕКСТ:\n\n{current or "(стандартный текст)"}\n\nОтправьте новый текст одним сообщением.',B('a_edit'))
    return await bot._base_callback(c,tg)

bot._base_text_handler=bot.text_handler
bot._base_callback=bot.callback
bot._base_admin_section=bot.admin_section
bot.admin_section=admin_section
bot.text_handler=text_handler
bot.callback=callback
