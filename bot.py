import asyncio, html, random, re
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import BOT_TOKEN, OWNER_ID, OWNER_ID2, OWNER_IDS, ADMIN_ID, FARMS, UNITS, DONATIONS, UNIT_BY_ID, DAILY_BONUS_PRIZES
from db import connect, init_db, ensure_user, user, top_users, users_count, all_user_ids, set_setting, setting, is_admin
from settings import init_settings, get_int, get_str
from combat import resolve

BRAND='WorldWarDynasty'; STATE={}; PENDING={}; INVITES={}; ATTACK_CD=timedelta(minutes=10)
EDIT_FIELDS={
'profile':('Профиль','{username} — юзер; {balance} — баланс; {farm} — ферма; {wins} — победы; {losses} — поражения; {battle_cd} — КД; {kills} — список убийств'),
'army':('Армия','{username}; {soldier}; {interceptor}; {drone}; {bmp}; {tank}; {helicopter}; {plane}; {missile}; {artillery} — количества всех единиц'),
'farm':('Ферма','{level}; {income}; {tax}; {status}'),
'bonus':('Бонус','{prizes} — список шансов'),
'cases':('Кейсы','{case1}; {case2}; {president}'),
'donate':('Донат','{donate50}; {donate100}; {donate500}; {contact}'),
'top':('Топ вояк','{top} — топ-50 по количеству техники; {position}'),
'earn':('Заработать','{balance}; {tasks}'),
'attack':('Атака','{count}; {page}; {pages}'),
'opponent':('Противник','{username}; {army} — полная армия'),
'battle_invite':('Входящий бой','{attacker}; {army}'),
'battle_line':('Фраза боя','{attacker}; {defender}'),
'win':('Победа','{winner}; {reward}; {kills}'),
'loss':('Поражение','{winner}; {loss}; {reward}; {kills}'),
'decline':('Отказ','{username}; {loss}'),
'help':('Помощь','{username}'),
'rules':('Правила','{username}')}

def money(v): return f'{int(v):,}'.replace(',',' ')
def esc(v): return html.escape(str(v or ''))
def now(): return datetime.now(timezone.utc)
def kb(rows): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=a,callback_data=b) for a,b in row] for row in rows])
def back(x='home'): return kb([[('⬅️ Назад',x)]])
def clean(text): return re.sub(r'(?i)</?b>','',str(text or '')).replace('&lt;b&gt;','').replace('&lt;/b&gt;','')
async def tpl(key,default,**kw):
    raw=await setting('msg_'+key,default)
    try:return clean(raw).format(**kw)
    except Exception:return clean(default)
def home_kb(a=False):
    rows=[[('🏭 Ферма','farm'),('🎖 Армия','army')],[('🛒 Арсенал','shop'),('⚔️ Атака','attack')],[('💰 Заработать','earn'),('🎁 Бонус','bonus')],[('🎟 Промокод','promo'),('📦 Кейсы','cases')],[('👤 Профиль','profile'),('🏆 Топ вояк','top')],[('💳 Донат','donate'),('📕 Правила','rules')],[('ℹ️ Помощь','help')]]
    if a: rows.append([('⚙️ Админ-панель','admin')])
    return kb(rows)
def admin_kb(): return kb([[('💰 Валюта','a_currency'),('🎁 Бонусы','a_bonus')],[('📦 Кейсы','a_cases'),('🎟 Промокоды','a_promos')],[('💰 Заработать','a_earn'),('💳 Донат','a_donate')],[('📕 Правила','a_rules'),('👥 Админы','a_admins')],[('🎖 Выдать','a_give'),('➖ Списать технику','a_takeunit')],[('📣 Рассылка','a_broadcast'),('📊 Статистика','a_stats')],[('✏️ Редактировать','a_edit'),('🏭 Фермы','a_farms')],[('⚔️ Бои','a_battles'),('👑 Владелец 2','a_owner2')],[('⬅️ Назад','home')]])
async def admin(uid): return uid in OWNER_IDS or await is_admin(uid,ADMIN_ID)
async def safe(c,text,markup=None):
    text=clean(text)
    try: await c.message.edit_text(text,reply_markup=markup,parse_mode=None)
    except Exception:
        try: await c.message.answer(text,reply_markup=markup,parse_mode=None)
        except Exception: pass
    try: await c.answer()
    except Exception: pass
def army_text(u): return '\n'.join(f'{v["title"]}: {int(u[k])}' for k,v in UNITS.items())
def army_size(u): return sum(int(u[k]) for k in UNITS if k!='artillery')
def cd_seconds(u):
    raw=u['last_attack'] or ''
    if not raw:return 0
    try:
        d=datetime.fromisoformat(raw);d=d if d.tzinfo else d.replace(tzinfo=timezone.utc);return max(0,int((d+ATTACK_CD-now()).total_seconds()))
    except Exception:return 0
def cd_text(u):
    s=cd_seconds(u);return 'ГОТОВО' if s<=0 else f'{s//60:02d}:{s%60:02d}'
async def start(m):
    await ensure_user(m.from_user.id,m.from_user.username);u=await user(m.from_user.id);n='@'+m.from_user.username if m.from_user.username else 'не указан';t=await tpl('start',f'⚔️ {BRAND}\n\n👤 {n}\n💵 Баланс: ${money(u["balance"])}\n🏭 Ферма: {u["farm_level"]}/10\n\n🛰 Центр управления войсками:',username=n,balance=money(u['balance']),farm=u['farm_level']);await m.answer(t,reply_markup=home_kb(await admin(m.from_user.id)))
async def profile(c):
    u=await user(c.from_user.id); name='@'+u['username'] if u['username'] else 'не указан'
    kills=[('🪖 Пехота','kill_soldier'),('🎯 Перехватчики','kill_interceptor'),('🛩 БПЛА','kill_drone'),('🚙 БМП','kill_bmp'),('🛡 Танки','kill_tank'),('🚁 Вертолёты','kill_helicopter'),('✈️ Самолёты','kill_plane'),('🚀 Ракеты','kill_missile'),('💥 Артиллерия','kill_artillery')]
    kt='\n'.join(f'{title}: {int(u[col])}' for title,col in kills)
    await safe(c,f'🛰 {BRAND} • ЛИЧНОЕ ДОСЬЕ\n\n👤 Позывной: {name}\n💵 Капитал: ${money(u["balance"])}\n🏭 Ферма: {u["farm_level"]}/10\n🏆 Побед: {u["attacks_won"]}\n💀 Поражений: {u["attacks_lost"]}\n\n🎯 УНИЧТОЖЕНО\n{kt}',back())
async def army(c):
    u=await user(c.from_user.id);kw={k:int(u[k]) for k in UNITS};kw['username']='@'+u['username'] if u['username'] else 'не указан';await safe(c,await tpl('army',f'🎖 {BRAND} • АРМИЯ\n\n{army_text(u)}',**kw),back())
async def balance_from_message(m):
    await ensure_user(m.from_user.id,m.from_user.username);u=await user(m.from_user.id);await m.answer(f'💵 {BRAND} • БАЛАНС\n\n💰 Капитал: ${money(u["balance"])}',reply_markup=home_kb(await admin(m.from_user.id)))
async def shop(c):
    items='\n'.join(f'{v["title"]} — ${money(v["price"])}' for k,v in UNITS.items());rows=[[(f'{v["title"]} — ${money(v["price"])}',f'buyq:{k}')] for k,v in UNITS.items()];rows.append([('⬅️ Назад','home')]);await safe(c,f'🛒 {BRAND} • ВОЕННЫЙ АРСЕНАЛ\n\n{items}\n\nВыберите единицу и введите количество.',kb(rows))
async def buyq(c,k):
    if k not in UNITS:return await c.answer('Недоступно',show_alert=True)
    STATE[c.from_user.id]=('buy',k);await safe(c,f'🛒 {UNITS[k]["title"]}\n\nЦена: ${money(UNITS[k]["price"])}\n\nВведите количество:',back('shop'))
async def buy_confirm(c,k,q):
    if k not in UNITS or q<1 or q>1000000:return await c.answer('Некорректное количество',show_alert=True)
    price=UNITS[k]['price']*q;db=await connect();cur=await db.execute(f'UPDATE users SET balance=balance-?,{k}={k}+? WHERE user_id=? AND balance>=?',(price,q,c.from_user.id,price));await db.commit();await db.close()
    if cur.rowcount!=1:return await safe(c,'❌ Недостаточно средств.',back('shop'))
    await safe(c,f'✅ Покупка выполнена\n\n{UNITS[k]["title"]} × {q}\n💵 Списано: ${money(price)}',back('shop'))
async def farm(c):
    u=await user(c.from_user.id);f=FARMS[int(u['farm_level'])];status='🟢 АКТИВНА' if int(u['farm_level'])>0 else '⚪ НЕ РАЗВЁРНУТА';await safe(c,await tpl('farm',f'🏭 {BRAND} • ФЕРМА\n\nУровень: {u["farm_level"]}/10\nПроизводство: ${money(f["income"])}/час\nНалог: ${money(u["tax"])}\nСтавка налога: 25%\nСтатус: {status}',level=u['farm_level'],income=money(f['income']),tax=money(u['tax']),status=status),kb([[('💰 Получить','payout'),('⬆️ Улучшить','upgrade')],[('💸 Оплатить налог','paytax')],[('⬅️ Назад','home')]]))
async def payout(c):
    u=await user(c.from_user.id);lvl=int(u['farm_level'])
    if lvl<=0:return await safe(c,'🏭 Сначала улучшите ферму до 1 уровня за $500 000.',back('farm'))
    if int(u['tax'])>0:return await safe(c,f'❌ Сначала оплатите налог: ${money(u["tax"])}.',back('farm'))
    try:last=datetime.fromisoformat(u['last_payout']);last=last if last.tzinfo else last.replace(tzinfo=timezone.utc)
    except Exception:last=now()-timedelta(hours=1)
    if now()-last<timedelta(hours=1):return await safe(c,'⏳ Выплата доступна раз в час.',back('farm'))
    income=int(FARMS[lvl]['income']);tax=int(income*.25);db=await connect();await db.execute('UPDATE users SET balance=balance+?,last_payout=?,tax=? WHERE user_id=?',(income,now().isoformat(),tax,c.from_user.id));await db.commit();await db.close();await safe(c,f'💰 Получено +${money(income)}\n💸 Налог 25%: ${money(tax)}.',back('farm'))
async def paytax(c):
    u=await user(c.from_user.id)
    if int(u['tax'])<=0:return await safe(c,'✅ Налог уже оплачен.',back('farm'))
    if int(u['balance'])<int(u['tax']):return await safe(c,f'❌ Нужно ${money(u["tax"])}.',back('farm'))
    db=await connect();await db.execute('UPDATE users SET balance=balance-tax,tax=0 WHERE user_id=?',(c.from_user.id,));await db.commit();await db.close();await safe(c,'✅ Налог оплачен.',back('farm'))
async def upgrade(c):
    u=await user(c.from_user.id);lvl=int(u['farm_level'])
    if lvl>=10:return await safe(c,'🏭 Максимальный уровень — 10.',back('farm'))
    cost=int(FARMS[lvl+1]['upgrade']);db=await connect();cur=await db.execute('UPDATE users SET balance=balance-?,farm_level=? WHERE user_id=? AND balance>=?',(cost,lvl+1,c.from_user.id,cost));await db.commit();await db.close();await safe(c,f'⬆️ Ферма повышена до {lvl+1} уровня.\n💵 Списано: ${money(cost)}',back('farm')) if cur.rowcount else await safe(c,f'❌ Нужно ${money(cost)}.',back('farm'))
async def bonus(c):
    prizes='\n'.join(f'{p:g}% — {label}' for p,_,_,label in DAILY_BONUS_PRIZES);await safe(c,await tpl('bonus',f'🎁 {BRAND} • ЕЖЕДНЕВНЫЙ БОНУС\n\n{prizes}',prizes=prizes),kb([[('🎁 Забрать','daily')],[('⬅️ Назад','home')]]))
async def daily(c):
    u=await user(c.from_user.id);today=now().date().isoformat()
    if u['daily_claim']==today:return await c.answer('Сегодня уже получено.',show_alert=True)
    r=random.uniform(0,100);acc=0
    for chance,unit,amount,label in DAILY_BONUS_PRIZES:
        acc+=chance
        if r<acc:break
    col='balance' if unit=='money' else unit;db=await connect();await db.execute(f'UPDATE users SET {col}={col}+?,daily_claim=? WHERE user_id=?',(amount,today,c.from_user.id));await db.commit();await db.close();await safe(c,f'🎁 Вы получили: {label}.',back('bonus'))
async def cases(c):
    c1='75% — 2 солдата\n15% — 11 перехватчиков\n10% — 10 солдат';c2='80% — БМП\n10% — танк\n7.5% — вертолёт\n2.5% — самолёт';pr='90% — вертолёт\n8% — самолёт\n2% — ракета';t=await tpl('cases',f'📦 {BRAND} • КЕЙСЫ\n\n📦 Кейс 1 — $45 000\n{c1}\n\n📦 Кейс 2 — $5 000 000\n{c2}\n\n🎖 Президентский — 50 ⭐\n{pr}',case1=c1,case2=c2,president=pr);await safe(c,t,kb([[('📦 Кейс 1','case1'),('📦 Кейс 2','case2')],[('🎖 Президентский','president')],[('⬅️ Назад','home')]]))
async def case(c,cid):
    if cid=='president':return await safe(c,'🎖 Президентский кейс покупается через донат.',kb([[('💳 Донат','donate')],[('⬅️ Назад','cases')]]))
    price=45000 if cid=='case1' else 5000000;pool=[('soldier',2,75),('interceptor',11,15),('soldier',10,10)] if cid=='case1' else [('bmp',1,80),('tank',1,10),('helicopter',1,7.5),('plane',1,2.5)];u=await user(c.from_user.id)
    if int(u['balance'])<price:return await c.answer('Недостаточно средств.',show_alert=True)
    r=random.uniform(0,100);acc=0
    for unit,amount,chance in pool:
        acc+=chance
        if r<acc:break
    col=unit;db=await connect();cur=await db.execute(f'UPDATE users SET balance=balance-?,{col}={col}+? WHERE user_id=? AND balance>=?',(price,amount,c.from_user.id,price));await db.commit();await db.close()
    if not cur.rowcount:return await c.answer('Недостаточно средств.',show_alert=True)
    await safe(c,f'📦 Кейс открыт!\n\n{UNITS[unit]["title"]} × {amount}\n🎲 Шанс: {chance}%',back('cases'))
async def donate(c):
    contact=await get_str('donate_contact');t=await tpl('donate',f'💳 {BRAND} • ДОНАТ\n\n50 ⭐ — ${money(DONATIONS[50])}\n100 ⭐ — ${money(DONATIONS[100])}\n500 ⭐ — ${money(DONATIONS[500])}\n\n📨 {contact}',donate50=money(DONATIONS[50]),donate100=money(DONATIONS[100]),donate500=money(DONATIONS[500]),contact=contact);await safe(c,t,back())
async def top(c):
    rows=await top_users(50);out=[]
    for i,r in enumerate(rows,1):
        medal=['🥇','🥈','🥉'][i-1] if i<=3 else '🎖️';name='@'+r['username'] if r['username'] else f'ID {r["user_id"]}';out.append(f'{medal} {i}. {esc(name)} — 🎖 {int(r["army_total"]):,}'.replace(',',' '))
    await safe(c,await tpl('top',f'🏆 {BRAND} • ТОП ВОЯК\n\n'+('\\n'.join(out) or 'Пока игроков нет.'),top='\n'.join(out),position='—'),back())
FIXED_QUESTS=[('earn_any','🎁 Получи приз в «Заработать»','$15 000'),('buy_soldier_10','🪖 Купи 10 солдат','$250 000'),('fight_once','⚔️ Сразись','$300 000'),('buy_interceptor_50','🎯 Приобрети 50 перехватчиков','$300 000'),('buy_bmp','🚙 Приобрети БМП','🛩 5 БПЛА + 🪖 10 солдат + 🎯 10 перехватчиков')]
async def earn(c):
    u=await user(c.from_user.id);db=await connect();cur=await db.execute('SELECT id,kind,url,reward FROM earn_tasks WHERE active=1 ORDER BY id');dyn=await cur.fetchall();cur=await db.execute('SELECT quest_id FROM quest_claims WHERE user_id=?',(c.from_user.id,));claimed={r['quest_id'] for r in await cur.fetchall()};await db.close();rows=[]
    for qid,title,reward in FIXED_QUESTS:
        if qid in claimed:continue
        done=(qid=='earn_any' and await earn_any_done(c.from_user.id)) or (qid=='buy_soldier_10' and u['soldier']>=10) or (qid=='fight_once' and u['attacks_won']+u['attacks_lost']>=1) or (qid=='buy_interceptor_50' and u['interceptor']>=50) or (qid=='buy_bmp' and u['bmp']>=1);rows.append([(f'✅ {title}' if done else f'🔒 {title}',f'quest:{qid}')])
    labels={'boost':'🚀 Буст канала / группы','channel':'📢 Подписка на канал','group':'👥 Вход в группу'}
    for x in dyn:rows.append([(f'{labels.get(x["kind"],x["kind"])} · +${money(x["reward"])}',x['url'])]);rows.append([('✅ Проверить',f'earn_check:{x["kind"]}:{x["id"]}')])
    rows.append([('⬅️ Назад','home')]);await safe(c,await tpl('earn',f'💰 {BRAND} • ЗАРАБОТАТЬ\n\nЗадания и награды:',balance=money(u['balance']),tasks='\n'.join(a for _,a,_ in FIXED_QUESTS)),kb(rows))
async def earn_any_done(uid):
    db=await connect();cur=await db.execute('SELECT COUNT(*) c FROM earn_claims WHERE user_id=?',(uid,));r=await cur.fetchone();await db.close();return r['c']>0
async def quest_claim(c,qid):
    db=await connect();cur=await db.execute('SELECT 1 FROM quest_claims WHERE user_id=? AND quest_id=?',(c.from_user.id,qid))
    if await cur.fetchone():await db.close();return await c.answer('Уже получено.',show_alert=True)
    u=await user(c.from_user.id);done={'earn_any':await earn_any_done(c.from_user.id),'buy_soldier_10':u['soldier']>=10,'fight_once':u['attacks_won']+u['attacks_lost']>=1,'buy_interceptor_50':u['interceptor']>=50,'buy_bmp':u['bmp']>=1}.get(qid,False)
    if not done:await db.close();return await c.answer('❌ Условие ещё не выполнено.',show_alert=True)
    rewards={'earn_any':15000,'buy_soldier_10':250000,'fight_once':300000,'buy_interceptor_50':300000}
    if qid=='buy_bmp':await db.execute('UPDATE users SET drone=drone+5,soldier=soldier+10,interceptor=interceptor+10 WHERE user_id=?',(c.from_user.id,));reward='🛩 5 БПЛА + 🪖 10 солдат + 🎯 10 перехватчиков'
    else:reward='$'+money(rewards[qid]);await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(rewards[qid],c.from_user.id))
    await db.execute('INSERT INTO quest_claims(user_id,quest_id) VALUES(?,?)',(c.from_user.id,qid));await db.commit();await db.close();await safe(c,f'🎉 Задание выполнено!\n\nНаграда: {reward}',back('earn'))
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
async def attack(c,page=0):
    me=await user(c.from_user.id);left=cd_seconds(me)
    if left:return await safe(c,f'⚔️ {BRAND} • АТАКА\n\n⏳ КД: {left//60:02d}:{left%60:02d}',back())
    db=await connect();cur=await db.execute('SELECT * FROM users WHERE user_id!=? ORDER BY balance DESC',(c.from_user.id,));allrows=await cur.fetchall();await db.close();players=[r for r in allrows if army_size(r)>0 and r['user_id'] not in INVITES.values()];per=10;pages=max(1,(len(players)+per-1)//per);page=max(0,min(page,pages-1));items=players[page*per:(page+1)*per];rows=[]
    for p in items:
        n='@'+p['username'] if p['username'] else f'ID {p["user_id"]}';rows.append([(f'⚔️ {n} · {army_size(p)} ед.',f'opp:{p["user_id"]}')])
    if not items:rows.append([('🔄 Обновить','attack')])
    nav=[]
    if page>0:nav.append(('⬅️ Назад',f'attack_page:{page-1}'))
    if page<pages-1:nav.append(('➡️ Далее',f'attack_page:{page+1}'))
    if nav:rows.append(nav)
    rows.append([('⬅️ Назад','home')]);await safe(c,await tpl('attack',f'⚔️ {BRAND} • ВЫБОР ПРОТИВНИКА\n\nДоступно: {len(players)}\nСтраница {page+1}/{pages}\n\nВыберите противника:',count=len(players),page=page+1,pages=pages),kb(rows))
async def opponent(c,uid):
    uid=int(uid);me=await user(c.from_user.id);opp=await user(uid)
    if not opp or uid==c.from_user.id:return await c.answer('Игрок недоступен.',show_alert=True)
    if cd_seconds(me):return await c.answer('Ваш бой ещё на КД.',show_alert=True)
    if army_size(opp)<=0:return await c.answer('Этот игрок сейчас недоступен.',show_alert=True)
    PENDING[c.from_user.id]=uid;n='@'+opp['username'] if opp['username'] else f'ID {uid}';await safe(c,await tpl('opponent',f'🎯 {BRAND} • ПРОТИВНИК\n\n👤 {n}\n\n{army_text(opp)}',username=n,army=army_text(opp)),kb([[('⚔️ НАПАСТЬ','battle_confirm')],[('⬅️ Назад','attack')]]))
BATTLE_LINES=['⚔️ Идёт бой','💥 Гремят взрывы','🪖 Пехота зачищает посадки','🔥 Раздаются выстрелы','🌫 Над полем боя поднимается дым','⚡ Ударная волна проходит по позиции','🪖 Подразделения продвигаются вперёд','💥 На линии фронта новый взрыв','🏴 Позиции сторон меняются','⚔️ Бой продолжается']
async def battle_confirm(c,bot):
    uid=PENDING.pop(c.from_user.id,None)
    if not uid:return await c.answer('Сначала выберите противника.',show_alert=True)
    me=await user(c.from_user.id);opp=await user(uid)
    if not opp or cd_seconds(me) or cd_seconds(opp) or army_size(opp)<=0:return await c.answer('Бой сейчас недоступен.',show_alert=True)
    INVITES[c.from_user.id]=uid;att='@'+me['username'] if me['username'] else f'ID {c.from_user.id}';text=await tpl('battle_invite',f'⚔️ {BRAND} • НА ВАС НАПАЛИ\n\n👤 Нападающий: {att}\n\n{army_text(me)}\n\nПримите бой или откажитесь.',attacker=att,army=army_text(me))
    try:await bot.send_message(uid,text,reply_markup=kb([[('⚔️ ПРИНЯТЬ БОЙ',f'accept:{c.from_user.id}')],[('🏳️ ОТКАЗАТЬСЯ',f'decline:{c.from_user.id}')]]))
    except Exception:INVITES.pop(c.from_user.id,None);return await c.answer('Не удалось отправить приглашение.',show_alert=True)
    await safe(c,'⏳ Запрос на бой отправлен противнику. Ожидаем решения...',back('attack'))
async def decline_loss(u):
    r={}
    for k in UNITS:
        n=int(u[k]);
        if n<=0:continue
        if k in ('soldier','interceptor'):r[k]=max(1,int(n*(.05 if n<=100000 else .03)))
        elif k=='bmp':r[k]=max(1,int(n*(.05 if n<=100 else .03)))
        elif k=='tank':r[k]=max(1,int(n*(.05 if n<=75 else .03)))
        elif k in ('plane','helicopter','missile'):r[k]=1 if random.random()<.5 else 0
    return r
async def battle_accept(c,attacker_id,bot):
    attacker_id=int(attacker_id);defender_id=c.from_user.id
    if INVITES.get(attacker_id)!=defender_id:return await c.answer('Приглашение уже недействительно.',show_alert=True)
    INVITES.pop(attacker_id,None);me=await user(attacker_id);opp=await user(defender_id)
    if not me or not opp or cd_seconds(me):return await c.answer('Бой уже недоступен.',show_alert=True)
    await c.message.edit_text('⚔️ БОЙ НАЧИНАЕТСЯ...')
    for i in range(15):
        line=random.choice(BATTLE_LINES)
        try:await c.message.edit_text(f'⚔️ {BRAND} • БОЙ\n\n{line}\n\n⏱ {15-i} сек.')
        except Exception:pass
        await asyncio.sleep(1)
    a_after,d_after,winner,events,kills_a,kills_d=resolve(me,opp,with_kills=True);winner_id=attacker_id if winner=='attacker' else defender_id;loser_id=defender_id if winner=='attacker' else attacker_id;winner_arm=a_after if winner=='attacker' else d_after;loser_raw=d_after if winner=='attacker' else a_after;loser_arm={k:int(loser_raw[k])*80//100 for k in UNITS};winner_k=kills_a if winner=='attacker' else kills_d;reward=int(sum(winner_k[k]*UNITS[k]['price'] for k in UNITS)*.05);loser_reward=int(sum((int((opp if winner=='attacker' else me)[k])-loser_arm[k])*UNITS[k]['price'] for k in UNITS)*.02)
    db=await connect();sets=','.join(f'{k}=?' for k in UNITS);ksets=','.join(f'kill_{k}=kill_{k}+?' for k in UNITS);await db.execute(f'UPDATE users SET {sets},attacks_won=attacks_won+1,last_attack=? WHERE user_id=?',[winner_arm[k] for k in UNITS]+[now().isoformat(),winner_id]);await db.execute(f'UPDATE users SET {sets},attacks_lost=attacks_lost+1,last_attack=? WHERE user_id=?',[loser_arm[k] for k in UNITS]+[now().isoformat(),loser_id]);await db.execute(f'UPDATE users SET {ksets} WHERE user_id=?',[winner_k[k] for k in UNITS]+[winner_id]);await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(reward,winner_id));await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(loser_reward,loser_id));await db.commit();await db.close()
    wn=await user(winner_id);winner_name='@'+wn['username'] if wn['username'] else f'ID {winner_id}';kills_w='\n'.join(f'{UNITS[k]["title"]}: {winner_k[k]}' for k in UNITS);loser_k=kills_d if winner=='attacker' else kills_a;kills_l='\n'.join(f'{UNITS[k]["title"]}: {loser_k[k]}' for k in UNITS);wintext=await tpl('win',f'🏆 WIN\n\nПобедитель: {winner_name}\n💰 Награда: ${money(reward)}\n\n🎯 Уничтожено:\n{kills_w}',winner=winner_name,reward=money(reward),kills=kills_w);losstext=f'💀 LOSS\n\n🏆 Победитель: {winner_name}\n📉 Твоя армия: −20%\n💵 Компенсация: ${money(loser_reward)}\n\n🎯 Уничтожено:\n{kills_l}';await bot.send_message(winner_id,wintext,reply_markup=back());await bot.send_message(loser_id,losstext,reply_markup=back())
async def battle_decline(c,attacker_id,bot):
    attacker_id=int(attacker_id);defender_id=c.from_user.id
    if INVITES.get(attacker_id)!=defender_id:return await c.answer('Приглашение уже недействительно.',show_alert=True)
    INVITES.pop(attacker_id,None);u=await user(defender_id);losses=await decline_loss(u);sets=','.join(f'{k}={k}-?' for k in losses);vals=[losses[k] for k in losses]
    if sets:
        db=await connect();await db.execute(f'UPDATE users SET {sets} WHERE user_id=?',vals+[defender_id]);await db.commit();await db.close()
    lost='\n'.join(f'{UNITS[k]["title"]}: −{v}' for k,v in losses.items() if v);text=await tpl('decline',f'🏳️ Вы отказались от боя.\n\nПотери:\n{lost or "Нет потерь"}',username='@'+u['username'] if u['username'] else f'ID {defender_id}',loss=lost);await c.message.edit_text(text,reply_markup=back());await bot.send_message(attacker_id,f'🏳️ Противник отказался от боя.\n\nЕго потери:\n{lost or "Нет потерь"}',reply_markup=back())
async def promo(c): STATE[c.from_user.id]=('promo',None);await safe(c,'🎟 ПРОМО\n\nВведите промокод:',back())
async def use_promo(m,code):
    db=await connect();cur=await db.execute('SELECT * FROM promos WHERE lower(code)=lower(?)',(code.strip(),));p=await cur.fetchone()
    if not p:await db.close();return await m.answer('❌ Промокод не найден.')
    if int(p['uses'])>=int(p['max_uses']):await db.close();return await m.answer('❌ Промокод больше недоступен.')
    cur=await db.execute('SELECT 1 FROM promo_uses WHERE code=? AND user_id=?',(p['code'],m.from_user.id))
    if await cur.fetchone():await db.close();return await m.answer('❌ Вы уже использовали этот промокод.')
    await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(p['amount'],m.from_user.id));await db.execute('UPDATE promos SET uses=uses+1 WHERE code=?',(p['code'],));await db.execute('INSERT INTO promo_uses(code,user_id) VALUES(?,?)',(p['code'],m.from_user.id));await db.commit();await db.close();await m.answer(f'🎉 Промокод активирован! +${money(p["amount"])}')
async def admin_panel(c):
    if not await admin(c.from_user.id):return await c.answer('Нет доступа.',show_alert=True)
    await safe(c,f'⚙️ {BRAND} • АДМИН-ПАНЕЛЬ\n\nВыберите раздел:',admin_kb())
async def edit_menu(c):
    items=list(EDIT_FIELDS.items());rows=[]
    for i in range(0,len(items),2):rows.append([(f'✏️ {items[i][1][0]}',f'editmsg:{items[i][0]}')]+([(f'✏️ {items[i+1][1][0]}',f'editmsg:{items[i+1][0]}')] if i+1<len(items) else []))
    rows.append([('⬅️ Назад','admin')]);await safe(c,'✏️ РЕДАКТИРОВАТЬ\n\nВыберите сообщение. Бот покажет ВСЕ доступные переменные для выбранного текста.',kb(rows))
async def edit_start(c,key):
    if key not in EDIT_FIELDS:return await c.answer('Раздел не найден.',show_alert=True)
    title,docs=EDIT_FIELDS[key];STATE[c.from_user.id]=('editmsg',key);await safe(c,f'✏️ {title}\n\nДоступные параметры:\n{docs}\n\n⚠️ Используй параметры точно в таком виде.\n\nОтправь новый текст одним сообщением.',kb([[('↩️ Назад','a_edit')]]))
async def admin_section(c,s):
    if not await admin(c.from_user.id):return await c.answer('Нет доступа.',show_alert=True)
    if s=='a_edit':return await edit_menu(c)
    if s=='a_currency':return await safe(c,'💰 ВАЛЮТА\n\n/givecash @user сумма',back('admin'))
    if s=='a_bonus':return await safe(c,'🎁 БОНУСЫ\n\n50% — $100 000\n20% — 10 перехватчиков\n10% — 2 БПЛА\n5% — БМП\n5% — 10 БПЛА\n4.9% — 50 перехватчиков\n2.5% — танк\n2.5% — $300 000\n0.1% — вертолёт',back('admin'))
    if s=='a_earn':return await safe(c,'💰 ЗАРАБОТАТЬ\n\n🚀 Буст канала / группы\n📢 Подписка на канал\n👥 Вход в группу',kb([[('🚀 Буст канала / группы','earn_add:boost')],[('📢 Подписка на канал','earn_add:channel')],[('👥 Вход в группу','earn_add:group')],[('⬅️ Назад','admin')]]))
    if s=='a_donate':return await donate(c)
    if s=='a_cases':return await cases(c)
    if s=='a_promos':return await safe(c,'🎟 ПРОМОКОДЫ\n\n/addpromo КОД СУММА КОЛИЧЕСТВО',back('admin'))
    if s=='a_give':return await safe(c,'🎖 ВЫДАТЬ\n\n/givecash @user сумма\n/givepehot @user ID количество\n\n1 пехота · 2 перехватчик · 3 БПЛА · 4 БМП · 5 танк · 6 вертолёт · 7 самолёт · 8 ракета · 9 артиллерия',back('admin'))
    if s=='a_battles':return await safe(c,'⚔️ БОИ\n\nКД: 10 минут.\nПосле принятия: 15 секунд.\nПри победе: проигравший −20% армии.\nПри отказе: солдаты/перехватчики до 100 000 = −5%, больше = −3%; БМП до 100 = −5%, больше = −3%; танки до 75 = −5%, больше = −3%; самолёт/вертолёт/ракета — случайно 0 или 1.',back('admin'))
    if s=='a_owner2':return await safe(c,f'👑 ВЛАДЕЛЕЦ 2\n\nID: {OWNER_ID2 or "не задан"}\n\n.env:\nOWNER_ID=первый_ID\nOWNER_ID2=второй_ID',back('admin'))
    return await safe(c,f'⚙️ {s}\n\nРаздел открыт.',back('admin'))
async def earn_add(c,kind):
    if not await admin(c.from_user.id):return await c.answer('Нет доступа.',show_alert=True)
    STATE[c.from_user.id]=('earn_add',kind);await safe(c,f'Введите: /add{kind} https://t.me/... 150000',back('a_earn'))
async def find_user(name):
    db=await connect();cur=await db.execute('SELECT * FROM users WHERE lower(username)=?',(name.lstrip('@').lower(),));r=await cur.fetchone();await db.close();return r
async def text_handler(m,bot):
    text=(m.text or '').strip();p=text.split();cmd=p[0].split('@')[0].lower() if p else '';low=text.lower()
    if not text.startswith('/'):
        if low in ('a','армия'):return await army_from_message(m)
        if low=='ферма':return await farm_from_message(m)
        if low in ('б','баланс'):return await balance_from_message(m)
        if low=='донат':return await donate_from_message(m)
        if low=='шоп':return await shop_from_message(m)
        if low=='правила':return await rules_from_message(m)
        if low=='вызовы':return await attack_from_message(m)
        if low=='атака':return await attack_from_message(m)
        if p and p[0].lower() in ('атака','атак') and len(p)>=2:return await attack_by_username(m,p[1])
        if low.startswith('промокод ') or low.startswith('промо ') or low.startswith('promo '):return await use_promo(m,p[1])
        if low in ('промо','промокод','promo'):STATE[m.from_user.id]=('promo',None);return await m.answer('🎟 Введите промокод:')
    if text.startswith('/'):
        if cmd in ('/promo','/промо','/промокод'):
            if len(p)>=2:return await use_promo(m,p[1])
            STATE[m.from_user.id]=('promo',None);return await m.answer('🎟 Введите промокод:')
        if cmd in ('/attack','/atack'):
            if len(p)>=2:return await attack_by_username(m,p[1])
            return await attack_from_message(m)
        if cmd in ('/addboost','/addchannel','/addgroup') and await admin(m.from_user.id) and len(p)==3:
            url=p[1];reward=int(p[2]) if p[2].isdigit() else 0
            if not url.startswith(('https://t.me/','http://t.me/')) or reward<=0:return await m.answer(f'❌ Формат: {cmd} https://t.me/... 150000')
            kind={'/addboost':'boost','/addchannel':'channel','/addgroup':'group'}[cmd];db=await connect();await db.execute('INSERT OR IGNORE INTO earn_tasks(kind,url,reward) VALUES(?,?,?)',(kind,url,reward));await db.commit();await db.close();return await m.answer('✅ Добавлено в «Заработать».')
        if cmd=='/addpromo' and await admin(m.from_user.id) and len(p)==4:
            code=p[1];amount=int(p[2]) if p[2].isdigit() else 0;maxuses=int(p[3]) if p[3].isdigit() else 0
            if not code or amount<=0 or maxuses<=0:return await m.answer('❌ Формат: /addpromo КОД СУММА КОЛИЧЕСТВО')
            db=await connect();await db.execute('INSERT INTO promos(code,amount,max_uses) VALUES(?,?,?) ON CONFLICT(code) DO UPDATE SET amount=excluded.amount,max_uses=excluded.max_uses',(code,amount,maxuses));await db.commit();await db.close();return await m.answer('✅ Промокод создан.')
        if cmd=='/givecash' and await admin(m.from_user.id) and len(p)==3:
            target=await find_user(p[1]);amount=int(p[2]) if p[2].isdigit() else 0
            if not target or amount<=0:return await m.answer('❌ Неверные данные.')
            db=await connect();await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(amount,target['user_id']));await db.commit();await db.close();return await m.answer('✅ Валюта выдана.')
        if cmd=='/givepehot' and await admin(m.from_user.id) and len(p)==4:
            target=await find_user(p[1]);uid=int(p[2]) if p[2].isdigit() else 0;q=int(p[3]) if p[3].isdigit() else 0
            if not target or uid not in UNIT_BY_ID or q<=0:return await m.answer('❌ Неверные данные.')
            unit=UNIT_BY_ID[uid];db=await connect();await db.execute(f'UPDATE users SET {unit}={unit}+? WHERE user_id=?',(q,target['user_id']));await db.commit();await db.close();return await m.answer('✅ Выдано.')
        if cmd=='/setmsg' and await admin(m.from_user.id) and len(text.split(maxsplit=2))==3:
            _,key,value=text.split(maxsplit=2);await set_setting('msg_'+key,value);return await m.answer('✅ Изменено.')
        return
    st=STATE.pop(m.from_user.id,None)
    if not st:return
    typ,val=st
    if typ=='buy':
        try:q=int(text)
        except:q=0
        if q<=0:return await m.answer('❌ Некорректное количество.')
        price=UNITS[val]['price']*q;await m.answer(f'🛒 {UNITS[val]["title"]} × {q}\n💵 ${money(price)}',reply_markup=kb([[('✅ Купить',f'buyok:{val}:{q}')],[('❌ Отмена','shop')]]))
    elif typ=='promo':return await use_promo(m,text)
    elif typ=='editmsg':await set_setting('msg_'+val,text);return await m.answer('✅ Текст сохранён в редакторе.')
    elif typ=='earn_add':return await m.answer(f'Используйте /add{val} https://t.me/... 150000')
async def army_from_message(m):
    await ensure_user(m.from_user.id,m.from_user.username);await m.answer(f'🎖 {BRAND} • АРМИЯ\n\n{army_text(await user(m.from_user.id))}',reply_markup=back())
async def farm_from_message(m): await m.answer('🏭 Ферма',reply_markup=home_kb(await admin(m.from_user.id)))
async def balance_from_message(m):
    await ensure_user(m.from_user.id,m.from_user.username);u=await user(m.from_user.id);await m.answer(f'💵 {BRAND} • БАЛАНС\n\n💰 Капитал: ${money(u["balance"])}',reply_markup=home_kb(await admin(m.from_user.id)))
async def donate_from_message(m):
    contact=await get_str('donate_contact');await m.answer(f'💳 {BRAND} • ДОНАТ\n\n50 ⭐ — ${money(DONATIONS[50])}\n100 ⭐ — ${money(DONATIONS[100])}\n500 ⭐ — ${money(DONATIONS[500])}\n\n📨 {contact}',reply_markup=back())
async def shop_from_message(m):
    items='\n'.join(f'{v["title"]} — ${money(v["price"])}' for k,v in UNITS.items());rows=[[(f'{v["title"]} — ${money(v["price"])}',f'buyq:{k}')] for k,v in UNITS.items()];rows.append([('⬅️ Назад','home')]);await m.answer(f'🛒 {BRAND} • ВОЕННЫЙ АРСЕНАЛ\n\n{items}\n\nВыберите единицу.',reply_markup=kb(rows))
async def rules_from_message(m): await m.answer(f'📕 {BRAND} • ПРАВИЛА\n\n1. Развивайте армию.\n2. Атаки имеют КД 10 минут.',reply_markup=back())
async def attack_from_message(m):
    await ensure_user(m.from_user.id,m.from_user.username);u=await user(m.from_user.id);left=cd_seconds(u)
    if left:return await m.answer(f'⚔️ {BRAND} • ВЫЗОВЫ\n\n⏳ Ваш КД: {left//60:02d}:{left%60:02d}')
    db=await connect();cur=await db.execute('SELECT * FROM users WHERE user_id!=? ORDER BY balance DESC',(m.from_user.id,));rows=await cur.fetchall();await db.close();players=[r for r in rows if not cd_seconds(r) and army_size(r)>0];out=[]
    for p in players[:10]:
        n='@'+p['username'] if p['username'] else f'ID {p["user_id"]}';out.append([(f'⚔️ {n} · {army_size(p)} ед.',f'opp:{p["user_id"]}')])
    if not out:return await m.answer('⚔️ Сейчас нет доступных противников.',reply_markup=back())
    out.append([('⬅️ Назад','home')]);await m.answer(f'⚔️ {BRAND} • ВЫБОР ПРОТИВНИКА\n\nВыберите игрока:',reply_markup=kb(out))
async def attack_by_username(m,name):
    target=await find_user(name)
    if not target:return await m.answer('❌ Игрок не найден.')
    me=await user(m.from_user.id);opp=await user(target['user_id'])
    if cd_seconds(me) or army_size(opp)<=0:return await m.answer('❌ Игрок сейчас недоступен.')
    PENDING[m.from_user.id]=target['user_id'];n='@'+opp['username'] if opp['username'] else f'ID {opp["user_id"]}';await m.answer(f'🎯 ПРОТИВНИК\n\n👤 {n}\n\n{army_text(opp)}',reply_markup=kb([[('⚔️ НАПАСТЬ','battle_confirm')],[('⬅️ Назад','home')]]))
async def callback(c,bot):
    d=c.data or ''
    if d=='home':u=await user(c.from_user.id);return await safe(c,f'⚔️ {BRAND}\n\n💵 Баланс: ${money(u["balance"])}',home_kb(await admin(c.from_user.id)))
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
    if d=='cases':return await cases(c)
    if d in ('case1','case2','president'):return await case(c,d)
    if d=='donate':return await donate(c)
    if d=='top':return await top(c)
    if d=='earn':return await earn(c)
    if d=='promo':return await promo(c)
    if d.startswith('quest:'):return await quest_claim(c,d.split(':',1)[1])
    if d.startswith('earn_check:'):
        _,kind,tid=d.split(':');return await earn_check(c,kind,int(tid),bot)
    if d=='help':return await safe(c,await tpl('help',f'ℹ️ {BRAND} • ПОМОЩЬ\n\nРазвивайте ферму, покупайте армию и участвуйте в боях.',username='@'+c.from_user.username if c.from_user.username else 'не указан'),back())
    if d=='rules':return await safe(c,await tpl('rules',f'📕 {BRAND} • ПРАВИЛА\n\n1. Развивайте армию.\n2. Атаки имеют КД.',username='@'+c.from_user.username if c.from_user.username else 'не указан'),back())
    if d=='attack':return await attack(c,0)
    if d.startswith('attack_page:'):return await attack(c,int(d.split(':',1)[1]))
    if d.startswith('opp:'):return await opponent(c,int(d.split(':',1)[1]))
    if d=='battle_confirm':return await battle_confirm(c,bot)
    if d.startswith('accept:'):return await battle_accept(c,int(d.split(':',1)[1]),bot)
    if d.startswith('decline:'):return await battle_decline(c,int(d.split(':',1)[1]),bot)
    if d=='admin':return await admin_panel(c)
    if d=='a_edit':return await edit_menu(c)
    if d.startswith('editmsg:'):return await edit_start(c,d.split(':',1)[1])
    if d.startswith('a_'):return await admin_section(c,d)
    if d.startswith('earn_add:'):return await earn_add(c,d.split(':',1)[1])
    await c.answer('Кнопка не найдена.',show_alert=True)
async def main():
    if not BOT_TOKEN:raise RuntimeError('BOT_TOKEN is empty')
    await init_db();await init_settings(ADMIN_ID);db=await connect();await db.execute('INSERT OR IGNORE INTO admins(user_id) VALUES(?)',(ADMIN_ID,));
    if OWNER_ID2:await db.execute('INSERT OR IGNORE INTO admins(user_id) VALUES(?)',(OWNER_ID2,))
    await db.commit();await db.close();tg=Bot(BOT_TOKEN);dp=Dispatcher();dp.message.register(start,CommandStart());dp.message.register(text_handler,F.text);dp.callback_query.register(callback,F.data);print(f'{BRAND} started');await dp.start_polling(tg)
if __name__=='__main__':asyncio.run(main())
