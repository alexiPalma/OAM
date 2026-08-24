import asyncio, html, random, re
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import BOT_TOKEN, OWNER_ID, ADMIN_ID, FARMS, UNITS, DONATIONS, UNIT_BY_ID
from db import connect, init_db, ensure_user, user, top_users, users_count, all_user_ids, set_setting, is_admin
from settings import init_settings, get_int, get_str
from earn import earn_admin_keyboard, earn_player_keyboard, parse_earn_command

BRAND='WorldWarDynasty'; STATE={}

def money(v): return f'{int(v):,}'.replace(',',' ')
def esc(v): return html.escape(str(v or ''))
def now(): return datetime.now(timezone.utc)
def kb(rows): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=a,callback_data=b) for a,b in row] for row in rows])
def back(x='home'): return kb([[('⬅️ Назад',x)]])

def home_kb(is_admin=False):
    rows=[[('🏭 Ферма','farm'),('🎖 Армия','army')],[('🛒 Арсенал','shop'),('⚔️ Атака','attack')],[('💰 Заработать','earn'),('🎁 Бонус','bonus')],[('📦 Кейсы','cases'),('👤 Профиль','profile')],[('🏆 Топ вояк','top'),('💳 Донат','donate')],[('📕 Правила','rules'),('ℹ️ Помощь','help')]]
    if is_admin: rows.append([('⚙️ Админ-панель','admin')])
    return kb(rows)

def admin_kb():
    return kb([[('💰 Валюта','a_currency'),('🎁 Бонусы','a_bonus')],[('📦 Кейсы','a_cases'),('🎟 Промокоды','a_promos')],[('💰 Заработать','a_earn'),('💳 Донат','a_donate')],[('📕 Правила','a_rules'),('👥 Админы','a_admins')],[('🎖 Выдать / списать','a_give'),('📣 Рассылка','a_broadcast')],[('📊 Статистика','a_stats'),('✏️ Редактировать','a_edit')],[('🏭 Фермы','a_farms'),('⚔️ Бои','a_battles')],[('⬅️ Назад','home')]])

async def admin(uid): return await is_admin(uid,ADMIN_ID)
async def safe(c,text,markup=None):
    try: await c.message.edit_text(text,reply_markup=markup,parse_mode='HTML')
    except Exception:
        try: await c.message.answer(text,reply_markup=markup,parse_mode='HTML')
        except Exception: await c.message.answer(re.sub('<[^>]+>','',text),reply_markup=markup)
    try: await c.answer()
    except Exception: pass

def army_text(u): return '\n'.join(f"{v['title']}: <b>{u[k]}</b>" for k,v in UNITS.items())

async def start(m):
    await ensure_user(m.from_user.id,m.from_user.username); u=await user(m.from_user.id)
    await m.answer(f'⚔️ <b>{BRAND}</b>\n\n💵 Баланс: <b>${money(u["balance"])}</b>\n🏭 Ферма: <b>{u["farm_level"]}/10</b>\n💸 Налог: <b>${money(u["tax"])}</b>\n\n🛰 Центр управления войсками:',reply_markup=home_kb(await admin(m.from_user.id)),parse_mode='HTML')

async def profile(c):
    u=await user(c.from_user.id); name='@'+u['username'] if u['username'] else 'не указан'
    kills=[('🪖 Пехота','kill_soldier'),('🎯 Перехватчики','kill_interceptor'),('🛩 БПЛА','kill_drone'),('🚙 БМП','kill_bmp'),('🛡 Танки','kill_tank'),('🚁 Вертолёты','kill_helicopter'),('✈️ Самолёты','kill_plane'),('🚀 Ракеты','kill_missile'),('💥 Артиллерия','kill_artillery')]
    kt='\n'.join(f'{title}: <b>{u[col]}</b>' for title,col in kills)
    await safe(c,f'🛰 <b>{BRAND} • ЛИЧНОЕ ДОСЬЕ</b>\n\n👤 Позывной: <b>{esc(name)}</b>\n💵 Капитал: <b>${money(u["balance"])}</b>\n🏭 Ферма: <b>{u["farm_level"]}/10</b>\n🏆 Побед: <b>{u["attacks_won"]}</b>\n💀 Поражений: <b>{u["attacks_lost"]}</b>\n\n🎯 <b>УНИЧТОЖЕНО</b>\n{kt}',back())
async def army(c): await safe(c,f'🎖 <b>{BRAND} • СОСТАВ ВОЙСК</b>\n\n{army_text(await user(c.from_user.id))}',back())

async def shop(c):
    rows=[[(f'{v["title"]}  ${money(v["price"])}',f'buyq:{k}')] for k,v in UNITS.items() if k!='artillery']; rows.append([('⬅️ Назад','home')])
    await safe(c,f'🛒 <b>{BRAND} • ВОЕННЫЙ АРСЕНАЛ</b>\n\nВыберите технику. После выбора будет запрошено количество.\n\n💵 Все цены указаны в долларах.',kb(rows))
async def buyq(c,key):
    if key not in UNITS or key=='artillery': return await c.answer('Недоступно',show_alert=True)
    STATE[c.from_user.id]=('buy',key); await safe(c,f'🛒 <b>{UNITS[key]["title"]}</b>\n\nЦена: <b>${money(UNITS[key]["price"])}</b> за 1 шт.\n\nВведите количество:',back('shop'))
async def buy_confirm(c,key,q):
    if key not in UNITS or q<1 or q>1000000:return await c.answer('Некорректное количество',show_alert=True)
    price=UNITS[key]['price']*q; db=await connect(); cur=await db.execute(f'UPDATE users SET balance=balance-?,{key}={key}+? WHERE user_id=? AND balance>=?',(price,q,c.from_user.id,price)); await db.commit(); await db.close()
    if cur.rowcount!=1:return await safe(c,'❌ Недостаточно средств.',back('shop'))
    await safe(c,f'✅ <b>Покупка выполнена</b>\n\n{UNITS[key]["title"]} × <b>{q}</b>\n💵 Списано: <b>${money(price)}</b>',back('shop'))

async def farm(c):
    u=await user(c.from_user.id); f=FARMS[u['farm_level']]; status='⛔ ОСТАНОВЛЕНА' if u['tax']>=1000000 else '🟢 АКТИВНА'
    await safe(c,f'🏭 <b>{BRAND} • ФЕРМА</b>\n\nУровень: <b>{u["farm_level"]}/10</b>\nПроизводство: <b>${money(f["income"])}/час</b>\nНалог: <b>${money(u["tax"])}</b>\nСтатус: <b>{status}</b>',kb([[('💰 Получить','payout'),('⬆️ Улучшить','upgrade')],[('💸 Оплатить налог','paytax')],[('⬅️ Назад','home')]]))
async def payout(c):
    u=await user(c.from_user.id); last=datetime.fromisoformat(u['last_payout'])
    if u['tax']>=1000000:return await safe(c,'⛔ Ферма остановлена. Оплатите налог.',back('farm'))
    if u['tax']>0:return await safe(c,f'❌ Сначала оплатите налог: <b>${money(u["tax"])}</b>.',back('farm'))
    if now()-last<timedelta(hours=1):return await safe(c,'⏳ Выплата доступна раз в час.',back('farm'))
    income=FARMS[u['farm_level']]['income']; tax=random.randint(20000,50000); db=await connect(); await db.execute('UPDATE users SET balance=balance+?,last_payout=?,tax=? WHERE user_id=?',(income,now().isoformat(),tax,c.from_user.id)); await db.commit(); await db.close(); await safe(c,f'💰 Получено <b>+${money(income)}</b>\n💸 Новый налог: <b>${money(tax)}</b>.',back('farm'))
async def paytax(c):
    u=await user(c.from_user.id)
    if u['tax']<=0:return await safe(c,'✅ Налог уже оплачен.',back('farm'))
    if u['balance']<u['tax']:return await safe(c,f'❌ Нужно <b>${money(u["tax"])}</b>.',back('farm'))
    db=await connect(); await db.execute('UPDATE users SET balance=balance-tax,tax=0 WHERE user_id=?',(c.from_user.id,)); await db.commit(); await db.close(); await safe(c,'✅ Налог оплачен.',back('farm'))
async def upgrade(c):
    u=await user(c.from_user.id); lvl=u['farm_level']
    if lvl>=10:return await safe(c,'🏭 Максимальный уровень — 10.',back('farm'))
    cost=FARMS[lvl+1]['upgrade']; db=await connect(); cur=await db.execute('UPDATE users SET balance=balance-?,farm_level=? WHERE user_id=? AND balance>=?',(cost,lvl+1,c.from_user.id,cost)); await db.commit(); await db.close(); await safe(c,f'⬆️ Ферма повышена до <b>{lvl+1} уровня</b>.',back('farm')) if cur.rowcount else await safe(c,f'❌ Нужно <b>${money(cost)}</b>.',back('farm'))

async def bonus(c):
    prizes=['50% — $100 000','20% — 10 перехватчиков','10% — 2 БПЛА','5% — БМП','5% — 10 БПЛА','2.5% — танк','2.5% — $300 000','4.9% — 50 перехватчиков','0.1% — вертолёт']
    await safe(c,f'🎁 <b>{BRAND} • ЕЖЕДНЕВНЫЙ БОНУС</b>\n\n'+'\n'.join(prizes)+f'\n\n📢 Бонус за подписку: <b>${money(await get_int("subscription_bonus"))}</b>',kb([[('🎁 Забрать','daily'),('📢 За подписку','sub')],[('⬅️ Назад','home')]]))
async def daily(c):
    u=await user(c.from_user.id); today=now().date().isoformat()
    if u['daily_claim']==today:return await c.answer('Сегодня уже получено.',show_alert=True)
    amount,unit=random.choice([(100000,'money'),(10,'interceptor'),(2,'drone'),(1,'bmp'),(10,'drone'),(1,'tank'),(300000,'money'),(50,'interceptor'),(1,'helicopter')]); col='balance' if unit=='money' else unit; db=await connect(); await db.execute(f'UPDATE users SET {col}={col}+?,daily_claim=? WHERE user_id=?',(amount,today,c.from_user.id)); await db.commit(); await db.close(); result='$'+money(amount) if unit=='money' else UNITS[unit]['title']+f' × {amount}'; await safe(c,f'🎁 Вы получили <b>{result}</b>.',back('bonus'))
async def sub(c,bot):
    channel=await get_str('channel_username')
    if not channel:return await c.answer('Канал не настроен.',show_alert=True)
    try:
        member=await bot.get_chat_member(channel,c.from_user.id)
        if member.status in ('left','kicked'):raise ValueError
    except Exception:return await safe(c,'📢 Подпишитесь на канал и нажмите «Проверить».',kb([[('📢 Канал','noop')],[('🔄 Проверить','sub'),('⬅️ Назад','bonus')]]))
    u=await user(c.from_user.id)
    if u['sub_claim']:return await c.answer('Бонус уже получен.',show_alert=True)
    b=await get_int('subscription_bonus'); db=await connect(); await db.execute('UPDATE users SET balance=balance+?,sub_claim=1 WHERE user_id=?',(b,c.from_user.id)); await db.commit(); await db.close(); await safe(c,f'🎁 +<b>${money(b)}</b>',back('bonus'))

async def cases(c):
    await safe(c,f'📦 <b>{BRAND} • КЕЙСЫ</b>\n\n📦 Кейс 1 — $45 000\n75% — 2 солдата\n10% — 10 солдат\n15% — 11 перехватчиков\n\n📦 Кейс 2 — $5 000 000\n80% — БМП\n10% — танк\n7.5% — вертолёт\n2.5% — самолёт\n\n🎖 Президентский — 50 ⭐\n90% — вертолёт\n8% — самолёт\n2% — ракета',kb([[('📦 Кейс 1','case1'),('📦 Кейс 2','case2')],[('🎖 Президентский','president')],[('⬅️ Назад','home')]]))
async def case(c,cid):
    if cid=='president':return await safe(c,'🎖 Президентский кейс покупается через донат.',kb([[('💳 Донат','donate')],[('⬅️ Назад','cases')]]))
    price=45000 if cid=='case1' else 5000000; pool=[('soldier',2,75),('soldier',10,10),('interceptor',11,15)] if cid=='case1' else [('bmp',1,80),('tank',1,10),('helicopter',1,7.5),('plane',1,2.5)]; u=await user(c.from_user.id)
    if u['balance']<price:return await c.answer('Недостаточно средств.',show_alert=True)
    r=random.uniform(0,100);a=0
    for unit,amount,chance in pool:
        a+=chance
        if r<=a:break
    db=await connect(); cur=await db.execute('UPDATE users SET balance=balance-?,%s=%s+? WHERE user_id=? AND balance>=?'%(unit,unit),(price,amount,c.from_user.id,price)); await db.commit(); await db.close()
    if not cur.rowcount:return await c.answer('Недостаточно средств.',show_alert=True)
    await safe(c,f'📦 Кейс открыт!\n\n🎖 {UNITS[unit]["title"]} × <b>{amount}</b>\n🎲 Шанс: <b>{chance}%</b>',back('cases'))
async def donate(c):await safe(c,f'💳 <b>{BRAND} • ДОНАТ</b>\n\n50 ⭐ — <b>${money(DONATIONS[50])}</b>\n100 ⭐ — <b>${money(DONATIONS[100])}</b>\n500 ⭐ — <b>${money(DONATIONS[500])}</b>\n\n📨 Покупка Stars: <b>{esc(await get_str("donate_contact"))}</b>',back())
async def top(c):
    rows=await top_users(50); out=[]
    for i,r in enumerate(rows,1):
        medal=['🥇','🥈','🥉'][i-1] if i<=3 else '🎖️'; name='@'+r['username'] if r['username'] else f'ID {r["user_id"]}'; out.append(f'{medal} <b>{i}.</b> {esc(name)} — ${money(r["balance"])}')
    await safe(c,f'🏆 <b>{BRAND} • ТОП ВОЯК</b>\n\n'+('\n'.join(out) or 'Пока игроков нет.'),back())

FIXED_QUESTS=[('earn_any','🎁 Получи приз в «Заработать»','$15 000'),('buy_soldier_10','🪖 Купи 10 солдат','$250 000'),('fight_once','⚔️ Сразись хотя бы один раз','$300 000'),('buy_interceptor_50','🎯 Приобрети 50 перехватчиков','$300 000'),('buy_bmp','🚙 Приобрети БМП','🛩 5 БПЛА + 🪖 10 солдат + 🎯 10 перехватчиков')]
async def earn_any_done(uid):
    db=await connect();cur=await db.execute('SELECT COUNT(*) c FROM earn_claims WHERE user_id=?',(uid,));row=await cur.fetchone();await db.close();return row['c']>0
async def earn(c):
    await ensure_user(c.from_user.id,c.from_user.username);u=await user(c.from_user.id);db=await connect();cur=await db.execute('SELECT id,kind,url,reward FROM earn_tasks WHERE active=1 ORDER BY id');dynamic=await cur.fetchall();cur=await db.execute('SELECT quest_id FROM quest_claims WHERE user_id=?',(c.from_user.id,));claimed={r['quest_id'] for r in await cur.fetchall()};await db.close();rows=[]
    for qid,title,reward in FIXED_QUESTS:
        if qid in claimed:continue
        done=(qid=='earn_any' and await earn_any_done(c.from_user.id)) or (qid=='buy_soldier_10' and u['soldier']>=10) or (qid=='fight_once' and (u['attacks_won']+u['attacks_lost'])>=1) or (qid=='buy_interceptor_50' and u['interceptor']>=50) or (qid=='buy_bmp' and u['bmp']>=1)
        rows.append([(f'✅ Выполнить • {title}' if done else f'🔒 Не выполнено • {title}',f'quest:{qid}')])
    labels={'boost':'🚀 Буст канала / группы','channel':'📢 Подписка на канал','group':'👥 Вход в группу'}
    for x in dynamic:
        rows.append([(f'{labels[x["kind"]]} · +${money(x["reward"])}',x['url'])]);rows.append([('✅ Проверить выполнение',f'earn_check:{x["kind"]}:{x["id"]}')])
    rows.append([('⬅️ Назад','home')]);await safe(c,f'💰 <b>{BRAND} • ЗАРАБОТАТЬ</b>\n\nЗдесь находятся задания, подписки, входы и бусты.',kb(rows))
async def quest_claim(c,qid):
    db=await connect();cur=await db.execute('SELECT 1 FROM quest_claims WHERE user_id=? AND quest_id=?',(c.from_user.id,qid))
    if await cur.fetchone():await db.close();return await c.answer('Задание уже получено.',show_alert=True)
    u=await user(c.from_user.id);done=False
    if qid=='earn_any':done=await earn_any_done(c.from_user.id)
    elif qid=='buy_soldier_10':done=u['soldier']>=10
    elif qid=='fight_once':done=(u['attacks_won']+u['attacks_lost'])>=1
    elif qid=='buy_interceptor_50':done=u['interceptor']>=50
    elif qid=='buy_bmp':done=u['bmp']>=1
    if not done:await db.close();return await c.answer('❌ Условие ещё не выполнено.',show_alert=True)
    rewards={'earn_any':15000,'buy_soldier_10':250000,'fight_once':300000,'buy_interceptor_50':300000}
    if qid=='buy_bmp':await db.execute('UPDATE users SET drone=drone+5,soldier=soldier+10,interceptor=interceptor+10 WHERE user_id=?',(c.from_user.id,));reward='🛩 5 БПЛА + 🪖 10 солдат + 🎯 10 перехватчиков'
    else:amount=rewards[qid];await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(amount,c.from_user.id));reward='$'+money(amount)
    await db.execute('INSERT INTO quest_claims(user_id,quest_id) VALUES(?,?)',(c.from_user.id,qid));await db.commit();await db.close();await safe(c,f'🎉 <b>Задание выполнено!</b>\n\nНаграда: <b>{reward}</b>',back('earn'))
async def earn_check(c,kind,tid,bot):
    db=await connect();cur=await db.execute('SELECT * FROM earn_tasks WHERE id=? AND kind=? AND active=1',(tid,kind));task=await cur.fetchone()
    if not task:await db.close();return await c.answer('Задание не найдено.',show_alert=True)
    cur=await db.execute('SELECT 1 FROM earn_claims WHERE user_id=? AND task_id=?',(c.from_user.id,tid));claimed=await cur.fetchone();await db.close()
    if claimed:return await c.answer('Награда уже получена.',show_alert=True)
    m=re.match(r'https?://t\.me/([A-Za-z0-9_]+)$',task['url'].rstrip('/'))
    if not m:return await c.answer('Для проверки нужна публичная ссылка Telegram.',show_alert=True)
    try:member=await bot.get_chat_member('@'+m.group(1),c.from_user.id);ok=member.status not in ('left','kicked')
    except Exception:ok=False
    if not ok:return await c.answer('❌ Условие ещё не выполнено.',show_alert=True)
    db=await connect();await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(task['reward'],c.from_user.id));await db.execute('INSERT INTO earn_claims(user_id,task_id) VALUES(?,?)',(c.from_user.id,tid));await db.commit();await db.close();await c.answer(f'🎉 +${money(task["reward"])}',show_alert=True)
async def earn_admin(c):
    if not await admin(c.from_user.id):return await c.answer('Нет доступа',show_alert=True)
    await safe(c,f'💰 <b>{BRAND} • ЗАРАБОТАТЬ</b>\n\nТолько 3 типа динамических заданий: буст канала/группы, подписка на канал, вход в группу.',earn_admin_keyboard())
async def earn_add(c,kind):
    if not await admin(c.from_user.id):return await c.answer('Нет доступа',show_alert=True)
    STATE[c.from_user.id]=('earn_add',kind);await safe(c,f'Введите: <code>/add{kind} https://t.me/... 150000</code>',back('a_earn'))

async def admin_panel(c):
    if not await admin(c.from_user.id):return await c.answer('Нет доступа',show_alert=True)
    await safe(c,f'⚙️ <b>{BRAND} • АДМИН-ПАНЕЛЬ</b>\n\nВыберите раздел:',admin_kb())
async def admin_section(c,s):
    if not await admin(c.from_user.id):return await c.answer('Нет доступа',show_alert=True)
    if s=='a_currency':return await safe(c,'💰 <b>ВАЛЮТА</b>\n\nОсновная валюта: <b>$</b>\n/givecash @user сумма\n/setcurrency ключ число',back('admin'))
    if s=='a_bonus':return await safe(c,f'🎁 <b>БОНУСЫ</b>\n\nЕжедневный: <b>${money(await get_int("daily_bonus"))}</b>\nЗа подписку: <b>${money(await get_int("subscription_bonus"))}</b>\n/setbonus daily 500000\n/setbonus sub 1500000',back('admin'))
    if s=='a_cases':return await cases(c)
    if s=='a_promos':return await safe(c,'🎟 <b>ПРОМОКОДЫ</b>\n\nСоздать: <code>/newpromo CODE СУММА ИСПОЛЬЗОВАНИЙ</code>\nИгрок вводит: <code>/promo CODE</code>',back('admin'))
    if s=='a_earn':return await earn_admin(c)
    if s=='a_donate':return await safe(c,f'💳 <b>ДОНАТ</b>\n\n50 ⭐ — ${money(DONATIONS[50])}\n100 ⭐ — ${money(DONATIONS[100])}\n500 ⭐ — ${money(DONATIONS[500])}\nКонтакт: <b>{esc(await get_str("donate_contact"))}</b>\n/setdonate @username',back('admin'))
    if s=='a_rules':return await safe(c,f'📕 <b>ПРАВИЛА</b>\n\n{esc(await get_str("rules_text"))}\n\n/setrule новый текст',back('admin'))
    if s=='a_admins':return await safe(c,'👥 <b>АДМИНЫ</b>\n\n/addadmin ID\n/deladmin ID\n\nOWNER_ID удалить нельзя.',back('admin'))
    if s=='a_give':return await safe(c,'🎖 <b>ВЫДАТЬ / СПИСАТЬ</b>\n\n/givecash @user сумма\n/givepehot @user ID количество\n\nID: 1 пехота · 2 перехватчик · 3 БПЛА · 4 БМП · 5 танк · 6 вертолёт · 7 самолёт · 8 ракета · 9 артиллерия',back('admin'))
    if s=='a_broadcast':return await safe(c,'📣 <b>РАССЫЛКА</b>\n\n/broadcast текст',back('admin'))
    if s=='a_stats':return await safe(c,f'📊 <b>СТАТИСТИКА</b>\n\n👥 Игроков: <b>{await users_count()}</b>',back('admin'))
    if s=='a_edit':return await safe(c,'✏️ <b>РЕДАКТИРОВАТЬ</b>\n\n/setmsg help Новый текст\n/setmsg rules Новый текст\n/setmsg start Новый текст\n\nИзменения сохраняются в БД.',back('admin'))
    if s=='a_farms':
        lines=[f'{i} уровень — ${money(v["income"])}/час'+(f' · прокачка ${money(v["upgrade"])}' if i>1 else '') for i,v in FARMS.items()]
        return await safe(c,'🏭 <b>ФЕРМЫ</b>\n\n'+'\n'.join(lines)+'\n\n/setfarm уровень доход цена_прокачки',back('admin'))
    if s=='a_battles':return await safe(c,'⚔️ <b>БОИ</b>\n\nОдна атака в час.\nПосле подтверждения — 15 секунд.\nПоражение — −20% армии.\nПобедитель — 5% стоимости уничтоженного.\nПроигравший — 2% стоимости потерь.\n\n/setbattle cooldown 60\n/setbattle loss 20\n/setbattle kill 5\n/setbattle loser 2',back('admin'))

async def find_user(name):
    db=await connect();cur=await db.execute('SELECT * FROM users WHERE lower(username)=?',(name.lstrip('@').lower(),));r=await cur.fetchone();await db.close();return r
async def text_handler(m,bot):
    text=(m.text or '').strip()
    if text.startswith('/'):
        p=text.split();cmd=p[0].split('@')[0].lower()
        if cmd in ('/addboost','/addchannel','/addgroup'):
            if not await admin(m.from_user.id):return await m.answer('⛔ Нет доступа.')
            kind={'/addboost':'boost','/addchannel':'channel','/addgroup':'group'}[cmd];parsed,err=parse_earn_command(text,cmd)
            if err:return await m.answer('❌ '+err)
            url,reward=parsed;db=await connect();await db.execute('INSERT OR IGNORE INTO earn_tasks(kind,url,reward) VALUES(?,?,?)',(kind,url,reward));await db.commit();await db.close();return await m.answer('✅ Задание добавлено в «Заработать».')
        if cmd=='/givecash' and await admin(m.from_user.id) and len(p)==3:
            target=await find_user(p[1]);amount=int(p[2]) if p[2].isdigit() else 0
            if not target or amount<=0:return await m.answer('❌ Неверные данные.')
            db=await connect();await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(amount,target['user_id']));await db.commit();await db.close();return await m.answer('✅ Валюта выдана.')
        if cmd=='/givepehot' and await admin(m.from_user.id) and len(p)==4:
            target=await find_user(p[1]);uid=int(p[2]) if p[2].isdigit() else 0;q=int(p[3]) if p[3].isdigit() else 0
            if not target or uid not in UNIT_BY_ID or q<=0:return await m.answer('❌ Неверные данные.')
            unit=UNIT_BY_ID[uid];db=await connect();await db.execute(f'UPDATE users SET {unit}={unit}+? WHERE user_id=?',(q,target['user_id']));await db.commit();await db.close();return await m.answer('✅ Техника выдана.')
        if cmd=='/addadmin' and m.from_user.id==ADMIN_ID and len(p)==2 and p[1].isdigit():
            db=await connect();await db.execute('INSERT OR IGNORE INTO admins(user_id) VALUES(?)',(int(p[1]),));await db.commit();await db.close();return await m.answer('✅ Администратор добавлен.')
        if cmd=='/deladmin' and m.from_user.id==ADMIN_ID and len(p)==2 and p[1].isdigit():
            target=int(p[1])
            if target==ADMIN_ID:return await m.answer('❌ OWNER_ID удалить нельзя.')
            db=await connect();await db.execute('DELETE FROM admins WHERE user_id=?',(target,));await db.commit();await db.close();return await m.answer('✅ Администратор удалён.')
        if cmd=='/setbonus' and await admin(m.from_user.id) and len(p)==3 and p[2].isdigit():
            key={'daily':'daily_bonus','sub':'subscription_bonus'}.get(p[1])
            if not key:return await m.answer('❌ Используй daily или sub.')
            await set_setting(key,int(p[2]));return await m.answer('✅ Бонус изменён.')
        if cmd=='/setdonate' and await admin(m.from_user.id) and len(p)==2:await set_setting('donate_contact',p[1]);return await m.answer('✅ Контакт доната изменён.')
        if cmd=='/setchannel' and await admin(m.from_user.id) and len(p)==2:await set_setting('channel_username',p[1]);return await m.answer('✅ Канал сохранён.')
        if cmd=='/setrule' and await admin(m.from_user.id) and len(text.split(maxsplit=1))==2:await set_setting('rules_text',text.split(maxsplit=1)[1]);return await m.answer('✅ Правила изменены.')
        if cmd=='/setmsg' and await admin(m.from_user.id) and len(text.split(maxsplit=2))==3:
            _,key,value=text.split(maxsplit=2);await set_setting('msg_'+key,value);return await m.answer('✅ Сообщение сохранено.')
        if cmd=='/setfarm' and await admin(m.from_user.id) and len(p)==4 and all(x.isdigit() for x in p[1:]):
            level,income,upgrade=map(int,p[1:])
            if level<1 or level>10:return await m.answer('❌ Уровень 1-10.')
            FARMS[level]['income']=income
            if level>1:FARMS[level]['upgrade']=upgrade
            await set_setting(f'farm_{level}_income',income)
            if level>1:await set_setting(f'farm_{level}_upgrade',upgrade)
            return await m.answer('✅ Ферма изменена.')
        if cmd=='/setbattle' and await admin(m.from_user.id) and len(p)==3 and p[2].isdigit():
            key={'cooldown':'attack_cooldown_minutes','loss':'loss_percent','kill':'kill_reward_percent','loser':'loser_reward_percent'}.get(p[1])
            if not key:return await m.answer('❌ cooldown/loss/kill/loser')
            await set_setting(key,int(p[2]));return await m.answer('✅ Параметр боя изменён.')
        if cmd=='/newpromo' and await admin(m.from_user.id) and len(p)==4 and p[2].isdigit() and p[3].isdigit():
            db=await connect();await db.execute('INSERT OR REPLACE INTO promos(code,amount,uses,max_uses) VALUES(?,?,0,?)',(p[1].upper(),int(p[2]),int(p[3])));await db.commit();await db.close();return await m.answer('✅ Промокод создан.')
        if cmd=='/promo' and len(p)==2:
            code=p[1].upper();db=await connect();cur=await db.execute('SELECT * FROM promos WHERE code=?',(code,));promo=await cur.fetchone()
            if not promo:await db.close();return await m.answer('❌ Промокод не найден.')
            cur=await db.execute('SELECT 1 FROM promo_uses WHERE code=? AND user_id=?',(code,m.from_user.id))
            if await cur.fetchone():await db.close();return await m.answer('❌ Уже использован.')
            if promo['uses']>=promo['max_uses']:await db.close();return await m.answer('❌ Лимит исчерпан.')
            await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(promo['amount'],m.from_user.id));await db.execute('UPDATE promos SET uses=uses+1 WHERE code=?',(code,));await db.execute('INSERT INTO promo_uses(code,user_id) VALUES(?,?)',(code,m.from_user.id));await db.commit();await db.close();return await m.answer(f'🎁 +${money(promo["amount"])}')
        if cmd=='/broadcast' and await admin(m.from_user.id) and len(text.split(maxsplit=1))==2:
            body=text.split(maxsplit=1)[1];sent=0
            for uid in await all_user_ids():
                try:await bot.send_message(uid,body);sent+=1
                except Exception:pass
            return await m.answer(f'📣 Рассылка завершена: {sent}')
        return
    st=STATE.pop(m.from_user.id,None)
    if not st:return
    typ,val=st
    if typ=='buy':
        try:q=int(text)
        except:q=0
        if q<=0:return await m.answer('❌ Некорректное количество.')
        price=UNITS[val]['price']*q;await m.answer(f'🛒 {UNITS[val]["title"]} × {q}\n💵 ${money(price)}',reply_markup=kb([[('✅ Купить',f'buyok:{val}:{q}')],[('❌ Отмена','shop')]]),parse_mode='HTML')

async def callback(c,bot):
    d=c.data or ''
    if d=='home':u=await user(c.from_user.id);return await safe(c,f'⚔️ <b>{BRAND}</b>\n\n💵 Баланс: <b>${money(u["balance"])}</b>',home_kb(await admin(c.from_user.id)))
    if d=='profile':return await profile(c)
    if d=='army':return await army(c)
    if d=='shop':return await shop(c)
    if d.startswith('buyq:'):return await buyq(c,d.split(':',1)[1])
    if d.startswith('buyok:'):
        _,k,q=d.split(':');return await buy_confirm(c,k,int(q))
    if d=='farm':return await farm(c)
    if d=='payout':return await payout(c)
    if d=='paytax':return await paytax(c)
    if d=='upgrade':return await upgrade(c)
    if d=='bonus':return await bonus(c)
    if d=='daily':return await daily(c)
    if d=='sub':return await sub(c,bot)
    if d=='cases':return await cases(c)
    if d in ('case1','case2','president'):return await case(c,d)
    if d=='donate':return await donate(c)
    if d=='top':return await top(c)
    if d=='earn':return await earn(c)
    if d.startswith('quest:'):return await quest_claim(c,d.split(':',1)[1])
    if d=='help':
        text=await get_str('msg_help') or 'Используйте /start. Покупайте войска, развивайте ферму и участвуйте в боях.'
        return await safe(c,f'ℹ️ <b>{BRAND} • ПОМОЩЬ</b>\n\n{esc(text)}',back())
    if d=='rules':
        text=await get_str('msg_rules') or await get_str('rules_text')
        return await safe(c,f'📕 <b>{BRAND} • ПРАВИЛА</b>\n\n{esc(text)}',back())
    if d=='attack':return await safe(c,f'⚔️ <b>{BRAND} • АТАКА</b>\n\nБоевой раздел подключён. Здесь будут выбор противника и подтверждение боя.',back())
    if d=='admin':return await admin_panel(c)
    if d.startswith('a_'):return await admin_section(c,d)
    if d.startswith('earn_add:'):return await earn_add(c,d.split(':',1)[1])
    if d.startswith('earn_check:'):
        _,kind,tid=d.split(':');return await earn_check(c,kind,int(tid),bot)
    if d=='noop':return await c.answer()
    await c.answer('Кнопка не найдена.',show_alert=True)

async def main():
    if not BOT_TOKEN:raise RuntimeError('BOT_TOKEN is empty')
    await init_db();await init_settings(ADMIN_ID);db=await connect();await db.execute('INSERT OR IGNORE INTO admins(user_id) VALUES(?)',(ADMIN_ID,));await db.commit();await db.close()
    bot=Bot(BOT_TOKEN);dp=Dispatcher();dp.message.register(start,CommandStart());dp.message.register(text_handler,F.text);dp.callback_query.register(callback,F.data);print(f'{BRAND} started');await dp.start_polling(bot)
if __name__=='__main__':asyncio.run(main())
