import asyncio, html, random, re
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import BOT_TOKEN, OWNER_ID, ADMIN_ID, FARMS, UNITS, DONATIONS, UNIT_BY_ID
from db import connect, init_db, ensure_user, user, top_users, users_count, all_user_ids, set_setting, setting, is_admin
from settings import init_settings, get_int, get_str
from combat import resolve

BRAND = 'WorldWarDynasty'
STATE = {}
ATTACK_CD = timedelta(minutes=10)
PENDING = {}


def money(v): return f'{int(v):,}'.replace(',', ' ')
def esc(v): return html.escape(str(v or ''))
def now(): return datetime.now(timezone.utc)
def kb(rows): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=a, callback_data=b) for a,b in row] for row in rows])
def back(x='home'): return kb([[('⬅️ Назад', x)]])
def clean(text):
    return re.sub(r'(?i)</?b>', '', str(text or '')).replace('&lt;b&gt;','').replace('&lt;/b&gt;','')


def home_kb(is_admin=False):
    rows = [[('🏭 Ферма','farm'),('🎖 Армия','army')], [('🛒 Арсенал','shop'),('⚔️ Атака','attack')], [('💰 Заработать','earn'),('🎁 Бонус','bonus')], [('📦 Кейсы','cases'),('👤 Профиль','profile')], [('🏆 Топ вояк','top'),('💳 Донат','donate')], [('📕 Правила','rules'),('ℹ️ Помощь','help')]]
    if is_admin: rows.append([('⚙️ Админ-панель','admin')])
    return kb(rows)

def admin_kb():
    return kb([[('💰 Валюта','a_currency'),('🎁 Бонусы','a_bonus')],[('📦 Кейсы','a_cases'),('🎟 Промокоды','a_promos')],[('💰 Заработать','a_earn'),('💳 Донат','a_donate')],[('📕 Правила','a_rules'),('👥 Админы','a_admins')],[('🎖 Выдать / списать','a_give'),('📣 Рассылка','a_broadcast')],[('📊 Статистика','a_stats'),('✏️ Редактировать','a_edit')],[('🏭 Фермы','a_farms'),('⚔️ Бои','a_battles')],[('⬅️ Назад','home')]])

async def admin(uid): return await is_admin(uid, ADMIN_ID)

async def safe(c, text, markup=None):
    text = clean(text)
    try: await c.message.edit_text(text, reply_markup=markup, parse_mode=None)
    except Exception:
        try: await c.message.answer(text, reply_markup=markup, parse_mode=None)
        except Exception: pass
    try: await c.answer()
    except Exception: pass


def army_text(u):
    return '\n'.join(f'{v["title"]}: {int(u[k])}' for k,v in UNITS.items())

def army_size(u): return sum(int(u[k]) for k in UNITS if k != 'artillery')

def cd_seconds(u):
    raw = u['last_attack'] or ''
    if not raw: return 0
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return max(0, int((dt + ATTACK_CD - now()).total_seconds()))
    except Exception: return 0

def cd_text(u):
    s=cd_seconds(u)
    return 'ГОТОВО' if s<=0 else f'{s//60:02d}:{s%60:02d}'

async def start(m):
    await ensure_user(m.from_user.id, m.from_user.username)
    u=await user(m.from_user.id)
    await m.answer(f'⚔️ {BRAND}\n\n💵 Баланс: ${money(u["balance"])}\n🏭 Ферма: {u["farm_level"]}/10\n\n🛰 Центр управления войсками:', reply_markup=home_kb(await admin(m.from_user.id)))

async def profile(c):
    u=await user(c.from_user.id); name='@'+u['username'] if u['username'] else 'не указан'
    kills=[('🪖 Пехота','kill_soldier'),('🎯 Перехватчики','kill_interceptor'),('🛩 БПЛА','kill_drone'),('🚙 БМП','kill_bmp'),('🛡 Танки','kill_tank'),('🚁 Вертолёты','kill_helicopter'),('✈️ Самолёты','kill_plane'),('🚀 Ракеты','kill_missile'),('💥 Артиллерия','kill_artillery')]
    kt='\n'.join(f'{a}: {int(u[b])}' for a,b in kills)
    await safe(c, f'👤 {BRAND} • ПРОФИЛЬ\n\n👤 Юзер: {name}\n💵 Баланс: ${money(u["balance"])}\n🏭 Ферма: {u["farm_level"]}/10\n🏆 Побед: {u["attacks_won"]}\n💀 Поражений: {u["attacks_lost"]}\n⚔️ КД атаки: {cd_text(u)}\n\n🎯 УНИЧТОЖЕНО\n{kt}', back())

async def army(c): await safe(c, f'🎖 {BRAND} • АРМИЯ\n\n{army_text(await user(c.from_user.id))}', back())

async def shop(c):
    rows=[[(f'{v["title"]} — ${money(v["price"])}',f'buyq:{k}')] for k,v in UNITS.items() if k!='artillery']; rows.append([('⬅️ Назад','home')])
    await safe(c, f'🛒 {BRAND} • ВОЕННЫЙ АРСЕНАЛ\n\nВыберите единицу. Затем бот спросит количество.', kb(rows))

async def buyq(c,key):
    if key not in UNITS or key=='artillery': return await c.answer('Недоступно',show_alert=True)
    STATE[c.from_user.id]=('buy',key); await safe(c,f'🛒 {UNITS[key]["title"]}\n\nЦена: ${money(UNITS[key]["price"])}\n\nВведите количество:',back('shop'))

async def buy_confirm(c,key,q):
    if key not in UNITS or q<1 or q>1000000:return await c.answer('Некорректное количество',show_alert=True)
    price=UNITS[key]['price']*q; db=await connect(); cur=await db.execute(f'UPDATE users SET balance=balance-?,{key}={key}+? WHERE user_id=? AND balance>=?',(price,q,c.from_user.id,price)); await db.commit(); await db.close()
    if cur.rowcount!=1:return await safe(c,'❌ Недостаточно средств.',back('shop'))
    await safe(c,f'✅ Покупка выполнена\n\n{UNITS[key]["title"]} × {q}\n💵 Списано: ${money(price)}',back('shop'))

async def farm(c):
    u=await user(c.from_user.id); f=FARMS[u['farm_level']]; status='⛔ ОСТАНОВЛЕНА' if u['tax']>=1000000 else '🟢 АКТИВНА'
    await safe(c,f'🏭 {BRAND} • ФЕРМА\n\nУровень: {u["farm_level"]}/10\nПроизводство: ${money(f["income"])}/час\nНалог: ${money(u["tax"])}\nСтатус: {status}',kb([[('💰 Получить','payout'),('⬆️ Улучшить','upgrade')],[('💸 Оплатить налог','paytax')],[('⬅️ Назад','home')]]))

async def payout(c):
    u=await user(c.from_user.id); last=datetime.fromisoformat(u['last_payout'])
    if u['tax']>=1000000:return await safe(c,'⛔ Ферма остановлена. Оплатите налог.',back('farm'))
    if u['tax']>0:return await safe(c,f'❌ Сначала оплатите налог: ${money(u["tax"])}.',back('farm'))
    if now()-last<timedelta(hours=1):return await safe(c,'⏳ Выплата доступна раз в час.',back('farm'))
    income=FARMS[u['farm_level']]['income']; tax=random.randint(20000,50000); db=await connect(); await db.execute('UPDATE users SET balance=balance+?,last_payout=?,tax=? WHERE user_id=?',(income,now().isoformat(),tax,c.from_user.id)); await db.commit(); await db.close(); await safe(c,f'💰 Получено +${money(income)}\n💸 Новый налог: ${money(tax)}.',back('farm'))

async def paytax(c):
    u=await user(c.from_user.id)
    if u['tax']<=0:return await safe(c,'✅ Налог уже оплачен.',back('farm'))
    if u['balance']<u['tax']:return await safe(c,f'❌ Нужно ${money(u["tax"])}.',back('farm'))
    db=await connect(); await db.execute('UPDATE users SET balance=balance-tax,tax=0 WHERE user_id=?',(c.from_user.id,)); await db.commit(); await db.close(); await safe(c,'✅ Налог оплачен.',back('farm'))

async def upgrade(c):
    u=await user(c.from_user.id); lvl=u['farm_level']
    if lvl>=10:return await safe(c,'🏭 Максимальный уровень — 10.',back('farm'))
    cost=FARMS[lvl+1]['upgrade']; db=await connect(); cur=await db.execute('UPDATE users SET balance=balance-?,farm_level=? WHERE user_id=? AND balance>=?',(cost,lvl+1,c.from_user.id,cost)); await db.commit(); await db.close(); await safe(c,f'⬆️ Ферма повышена до {lvl+1} уровня.',back('farm')) if cur.rowcount else await safe(c,f'❌ Нужно ${money(cost)}.',back('farm'))

async def bonus(c):
    prizes=['50% — $100 000','20% — 10 перехватчиков','10% — 2 БПЛА','5% — БМП','5% — 10 БПЛА','2.5% — танк','2.5% — $300 000','4.9% — 50 перехватчиков','0.1% — вертолёт']
    await safe(c, f'🎁 {BRAND} • ЕЖЕДНЕВНЫЙ БОНУС\n\n'+'\n'.join(prizes), kb([[('🎁 Забрать','daily')],[('⬅️ Назад','home')]]))

async def daily(c):
    u=await user(c.from_user.id); today=now().date().isoformat()
    if u['daily_claim']==today:return await c.answer('Сегодня уже получено.',show_alert=True)
    amount,unit=random.choice([(100000,'money'),(10,'interceptor'),(2,'drone'),(1,'bmp'),(10,'drone'),(1,'tank'),(300000,'money'),(50,'interceptor'),(1,'helicopter')]); col='balance' if unit=='money' else unit
    db=await connect(); await db.execute(f'UPDATE users SET {col}={col}+?,daily_claim=? WHERE user_id=?',(amount,today,c.from_user.id)); await db.commit(); await db.close(); result='$'+money(amount) if unit=='money' else UNITS[unit]['title']+f' × {amount}'; await safe(c,f'🎁 Вы получили {result}.',back('bonus'))

async def cases(c):
    await safe(c,f'📦 {BRAND} • КЕЙСЫ\n\n📦 Кейс 1 — $45 000\n75% — 2 солдата\n10% — 10 солдат\n15% — 11 перехватчиков\n\n📦 Кейс 2 — $5 000 000\n80% — БМП\n10% — танк\n7.5% — вертолёт\n2.5% — самолёт\n\n🎖 Президентский — 50 ⭐\n90% — вертолёт\n8% — самолёт\n2% — ракета',kb([[('📦 Кейс 1','case1'),('📦 Кейс 2','case2')],[('🎖 Президентский','president')],[('⬅️ Назад','home')]]))

async def case(c,cid):
    if cid=='president':return await safe(c,'🎖 Президентский кейс покупается через донат.',kb([[('💳 Донат','donate')],[('⬅️ Назад','cases')]]))
    price=45000 if cid=='case1' else 5000000; pool=[('soldier',2,75),('soldier',10,10),('interceptor',11,15)] if cid=='case1' else [('bmp',1,80),('tank',1,10),('helicopter',1,7.5),('plane',1,2.5)]
    u=await user(c.from_user.id)
    if u['balance']<price:return await c.answer('Недостаточно средств.',show_alert=True)
    r=random.uniform(0,100); acc=0
    for unit,amount,chance in pool:
        acc+=chance
        if r<=acc:break
    db=await connect(); cur=await db.execute('UPDATE users SET balance=balance-?,%s=%s+? WHERE user_id=? AND balance>=?'%(unit,unit),(price,amount,c.from_user.id,price)); await db.commit(); await db.close()
    if not cur.rowcount:return await c.answer('Недостаточно средств.',show_alert=True)
    await safe(c,f'📦 Кейс открыт!\n\n{UNITS[unit]["title"]} × {amount}\n🎲 Шанс: {chance}%',back('cases'))

async def donate(c): await safe(c,f'💳 {BRAND} • ДОНАТ\n\n50 ⭐ — ${money(DONATIONS[50])}\n100 ⭐ — ${money(DONATIONS[100])}\n500 ⭐ — ${money(DONATIONS[500])}\n\n📨 {esc(await get_str("donate_contact"))}',back())

async def top(c):
    rows=await top_users(50); out=[]
    for i,r in enumerate(rows,1):
        medal=['🥇','🥈','🥉'][i-1] if i<=3 else '🎖️'; name='@'+r['username'] if r['username'] else f'ID {r["user_id"]}'; out.append(f'{medal} {i}. {esc(name)} — ${money(r["balance"])}')
    await safe(c,f'🏆 {BRAND} • ТОП ВОЯК\n\n'+('\n'.join(out) or 'Пока игроков нет.'),back())

FIXED_QUESTS=[('earn_any','🎁 Получи приз в «Заработать»','$15 000'),('buy_soldier_10','🪖 Купи 10 солдат','$250 000'),('fight_once','⚔️ Сразись','$300 000'),('buy_interceptor_50','🎯 Приобрети 50 перехватчиков','$300 000'),('buy_bmp','🚙 Приобрети БМП','🛩 5 БПЛА + 🪖 10 солдат + 🎯 10 перехватчиков')]

async def earn(c):
    u=await user(c.from_user.id); db=await connect(); cur=await db.execute('SELECT id,kind,url,reward FROM earn_tasks WHERE active=1 ORDER BY id'); dyn=await cur.fetchall(); cur=await db.execute('SELECT quest_id FROM quest_claims WHERE user_id=?',(c.from_user.id,)); claimed={r['quest_id'] for r in await cur.fetchall()}; await db.close(); rows=[]
    for qid,title,reward in FIXED_QUESTS:
        if qid in claimed: continue
        done=(qid=='earn_any' and await earn_any_done(c.from_user.id)) or (qid=='buy_soldier_10' and u['soldier']>=10) or (qid=='fight_once' and u['attacks_won']+u['attacks_lost']>=1) or (qid=='buy_interceptor_50' and u['interceptor']>=50) or (qid=='buy_bmp' and u['bmp']>=1)
        rows.append([(f'✅ {title}' if done else f'🔒 {title}',f'quest:{qid}')])
    labels={'boost':'🚀 Буст канала / группы','channel':'📢 Подписка на канал','group':'👥 Вход в группу'}
    for x in dyn:
        rows.append([(f'{labels.get(x["kind"],x["kind"])} · +${money(x["reward"])}',x['url'])]); rows.append([('✅ Проверить',f'earn_check:{x["kind"]}:{x["id"]}')])
    rows.append([('⬅️ Назад','home')]); await safe(c,f'💰 {BRAND} • ЗАРАБОТАТЬ\n\nЗадания и награды:',kb(rows))

async def earn_any_done(uid):
    db=await connect();cur=await db.execute('SELECT COUNT(*) c FROM earn_claims WHERE user_id=?',(uid,));r=await cur.fetchone();await db.close();return r['c']>0

async def quest_claim(c,qid):
    db=await connect();cur=await db.execute('SELECT 1 FROM quest_claims WHERE user_id=? AND quest_id=?',(c.from_user.id,qid));
    if await cur.fetchone():await db.close();return await c.answer('Уже получено.',show_alert=True)
    u=await user(c.from_user.id);done={'earn_any':await earn_any_done(c.from_user.id),'buy_soldier_10':u['soldier']>=10,'fight_once':u['attacks_won']+u['attacks_lost']>=1,'buy_interceptor_50':u['interceptor']>=50,'buy_bmp':u['bmp']>=1}.get(qid,False)
    if not done:await db.close();return await c.answer('❌ Условие ещё не выполнено.',show_alert=True)
    rewards={'earn_any':15000,'buy_soldier_10':250000,'fight_once':300000,'buy_interceptor_50':300000}
    if qid=='buy_bmp':await db.execute('UPDATE users SET drone=drone+5,soldier=soldier+10,interceptor=interceptor+10 WHERE user_id=?',(c.from_user.id,)); reward='🛩 5 БПЛА + 🪖 10 солдат + 🎯 10 перехватчиков'
    else: reward='$'+money(rewards[qid]); await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(rewards[qid],c.from_user.id))
    await db.execute('INSERT INTO quest_claims(user_id,quest_id) VALUES(?,?)',(c.from_user.id,qid));await db.commit();await db.close();await safe(c,f'🎉 Задание выполнено!\n\nНаграда: {reward}',back('earn'))

async def earn_check(c,kind,tid,bot):
    db=await connect();cur=await db.execute('SELECT * FROM earn_tasks WHERE id=? AND kind=? AND active=1',(tid,kind));task=await cur.fetchone();
    if not task:await db.close();return await c.answer('Задание не найдено.',show_alert=True)
    cur=await db.execute('SELECT 1 FROM earn_claims WHERE user_id=? AND task_id=?',(c.from_user.id,tid));claimed=await cur.fetchone();await db.close()
    if claimed:return await c.answer('Награда уже получена.',show_alert=True)
    m=re.match(r'https?://t\.me/([A-Za-z0-9_]+)$',task['url'].rstrip('/'))
    if not m:return await c.answer('Для проверки нужна публичная ссылка Telegram.',show_alert=True)
    try: member=await bot.get_chat_member('@'+m.group(1),c.from_user.id); ok=member.status not in ('left','kicked')
    except Exception: ok=False
    if not ok:return await c.answer('❌ Условие ещё не выполнено.',show_alert=True)
    db=await connect();await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(task['reward'],c.from_user.id));await db.execute('INSERT INTO earn_claims(user_id,task_id) VALUES(?,?)',(c.from_user.id,tid));await db.commit();await db.close();await c.answer(f'🎉 +${money(task["reward"])}',show_alert=True)

async def attack(c,page=0):
    me=await user(c.from_user.id); left=cd_seconds(me)
    if left:return await safe(c,f'⚔️ {BRAND} • АТАКА\n\n⏳ КД: {left//60:02d}:{left%60:02d}',back())
    db=await connect();cur=await db.execute('SELECT * FROM users WHERE user_id!=? ORDER BY balance DESC',(c.from_user.id,));allrows=await cur.fetchall();await db.close(); players=[r for r in allrows if not cd_seconds(r) and army_size(r)>0]
    per=10; pages=max(1,(len(players)+per-1)//per); page=max(0,min(page,pages-1)); items=players[page*per:(page+1)*per]; rows=[]
    for p in items:
        name='@'+p['username'] if p['username'] else f'ID {p["user_id"]}'; rows.append([(f'⚔️ {name} · {army_size(p)} ед.',f'opp:{p["user_id"]}')])
    if not items: rows.append([('🔄 Обновить','attack')])
    nav=[]
    if page>0:nav.append(('⬅️ Назад',f'attack_page:{page-1}'))
    if page<pages-1:nav.append(('➡️ Далее',f'attack_page:{page+1}'))
    if nav:rows.append(nav)
    rows.append([('⬅️ Назад','home')]);await safe(c,f'⚔️ {BRAND} • ВЫБОР ПРОТИВНИКА\n\nДоступно: {len(players)}\nСтраница {page+1}/{pages}\n\nВыберите противника:',kb(rows))

async def opponent(c,uid):
    uid=int(uid);me=await user(c.from_user.id);opp=await user(uid)
    if not opp or uid==c.from_user.id:return await c.answer('Игрок недоступен.',show_alert=True)
    if cd_seconds(me):return await c.answer('Ваш бой ещё на КД.',show_alert=True)
    if cd_seconds(opp) or army_size(opp)<=0:return await c.answer('Этот игрок сейчас недоступен.',show_alert=True)
    PENDING[c.from_user.id]=uid;name='@'+opp['username'] if opp['username'] else f'ID {uid}'
    await safe(c,f'🎯 {BRAND} • ПРОТИВНИК\n\n👤 {name}\n\n{army_text(opp)}',kb([[('⚔️ НАПАСТЬ','battle_confirm')],[('⬅️ Назад','attack')]]))

async def battle_confirm(c,bot):
    uid=PENDING.pop(c.from_user.id,None)
    if not uid:return await c.answer('Сначала выберите противника.',show_alert=True)
    me=await user(c.from_user.id);opp=await user(uid)
    if not opp or cd_seconds(me) or cd_seconds(opp) or army_size(opp)<=0:return await c.answer('Бой сейчас недоступен.',show_alert=True)
    await safe(c,'⚔️ БОЙ НАЧАЛСЯ\n\n🛰 Разведка завершена...');await asyncio.sleep(5);await safe(c,'⚔️ БОЙ\n\n🛩 БПЛА в воздухе...\n🎯 Перехватчики работают...\n🚀 Ракетный удар...');await asyncio.sleep(5);await safe(c,'⚔️ БОЙ\n\n💥 Артиллерия работает...\n🪖 Пехота вступила в бой...\n🚙 БМП атакуют...');await asyncio.sleep(5)
    a_after,d_after,winner,events,kills_a,kills_d=resolve(me,opp,with_kills=True)
    winner_id=c.from_user.id if winner=='attacker' else uid;loser_id=uid if winner=='attacker' else c.from_user.id
    winner_arm=a_after if winner=='attacker' else d_after; loser_arm=d_after if winner=='attacker' else a_after; loser_arm={k:int(loser_arm[k])*80//100 for k in UNITS}
    winner_k=kills_a if winner=='attacker' else kills_d; loser_k=kills_d if winner=='attacker' else kills_a
    reward=int(sum(winner_k[k]*UNITS[k]['price'] for k in UNITS)*0.05); loser_reward=int(sum((int((opp if winner=='attacker' else me)[k])-loser_arm[k])*UNITS[k]['price'] for k in UNITS)*0.02)
    db=await connect();sets=','.join(f'{k}=?' for k in UNITS);ksets=','.join(f'kill_{k}=kill_{k}+?' for k in UNITS)
    await db.execute(f'UPDATE users SET {sets},attacks_won=attacks_won+1,last_attack=? WHERE user_id=?',[winner_arm[k] for k in UNITS]+[now().isoformat(),winner_id])
    await db.execute(f'UPDATE users SET {sets},attacks_lost=attacks_lost+1,last_attack=? WHERE user_id=?',[loser_arm[k] for k in UNITS]+[now().isoformat(),loser_id])
    await db.execute(f'UPDATE users SET {ksets} WHERE user_id=?',[winner_k[k] for k in UNITS]+[winner_id]);await db.execute(f'UPDATE users SET {ksets} WHERE user_id=?',[loser_k[k] for k in UNITS]+[loser_id])
    await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(reward,winner_id));await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(loser_reward,loser_id));await db.execute('INSERT INTO battle_log(attacker,defender,winner,report,created_at) VALUES(?,?,?,?,?)',(c.from_user.id,uid,winner_id,'\n'.join(events[-25:]),now().isoformat()));await db.commit();await db.close()
    report='\n'.join(events[-25:]) or 'Бой завершён.'
    if winner=='attacker': result=f'🏆 WIN\n\n💰 Победитель получил: ${money(reward)}\n📉 Армия проигравшего: −20%\n💵 Проигравшему: +${money(loser_reward)}\n\n{report}'
    else: result=f'💀 LOSS\n\n📉 Твоя армия: −20%\n💵 Компенсация: +${money(loser_reward)}\n\n{report}'
    await safe(c,result,back())

async def admin_panel(c):
    if not await admin(c.from_user.id):return await c.answer('Нет доступа.',show_alert=True)
    await safe(c,f'⚙️ {BRAND} • АДМИН-ПАНЕЛЬ\n\nВыберите раздел:',admin_kb())

async def admin_section(c,s):
    if not await admin(c.from_user.id):return await c.answer('Нет доступа.',show_alert=True)
    if s=='a_currency':return await safe(c,'💰 ВАЛЮТА\n\n/givecash @user сумма',back('admin'))
    if s=='a_bonus':return await safe(c,f'🎁 БОНУСЫ\n\nЕжедневный: ${money(await get_int("daily_bonus"))}\nПодписочный бонус настраивается отдельно, но в ежедневном бонусе его НЕТ.\n/setbonus daily 500000\n/setbonus sub 1500000',back('admin'))
    if s=='a_earn':return await safe(c,'💰 ЗАРАБОТАТЬ\n\nТолько 3 типа:\n🚀 Буст канала\n📢 Подписка на канал\n👥 Подписка на группу',kb([[('🚀 Буст канала','earn_add:boost')],[('📢 Подписка на канал','earn_add:channel')],[('👥 Подписка на группу','earn_add:group')],[('⬅️ Назад','admin')]]))
    if s=='a_donate':return await donate(c)
    if s=='a_cases':return await cases(c)
    if s=='a_stats':return await safe(c,f'📊 СТАТИСТИКА\n\nИгроков: {await users_count()}',back('admin'))
    if s=='a_give':return await safe(c,'🎖 ВЫДАТЬ\n\n/givecash @user сумма\n/givepehot @user ID количество\n\n1 пехота · 2 перехватчик · 3 БПЛА · 4 БМП · 5 танк · 6 вертолёт · 7 самолёт · 8 ракета · 9 артиллерия',back('admin'))
    if s=='a_rules':return await safe(c,'📕 ПРАВИЛА\n\n/setrule текст',back('admin'))
    if s=='a_edit':return await safe(c,'✏️ РЕДАКТИРОВАТЬ\n\n/setmsg help текст\n/setmsg rules текст',back('admin'))
    if s=='a_battles':return await safe(c,'⚔️ БОИ\n\nКД атаки: 10 минут.\nПосле подтверждения: 15 секунд.\nПроигравший: −20% армии.',back('admin'))
    return await safe(c,f'⚙️ {s}\n\nРаздел открыт.',back('admin'))

async def earn_add(c,kind):
    if not await admin(c.from_user.id):return await c.answer('Нет доступа.',show_alert=True)
    STATE[c.from_user.id]=('earn_add',kind);await safe(c,f'Введите команду:\n/add{kind} https://t.me/... 150000',back('a_earn'))

async def find_user(name):
    db=await connect();cur=await db.execute('SELECT * FROM users WHERE lower(username)=?',(name.lstrip('@').lower(),));r=await cur.fetchone();await db.close();return r

async def text_handler(m,bot):
    text=(m.text or '').strip(); p=text.split(); cmd=p[0].split('@')[0].lower() if p else ''
    if text.startswith('/'):
        if cmd in ('/addboost','/addchannel','/addgroup') and await admin(m.from_user.id) and len(p)==3:
            url=p[1]; reward=int(p[2]) if p[2].isdigit() else 0
            if not url.startswith(('https://t.me/','http://t.me/')) or reward<=0:return await m.answer('❌ Формат: /addboost https://t.me/... 150000')
            kind={'/addboost':'boost','/addchannel':'channel','/addgroup':'group'}[cmd];db=await connect();await db.execute('INSERT OR IGNORE INTO earn_tasks(kind,url,reward) VALUES(?,?,?)',(kind,url,reward));await db.commit();await db.close();return await m.answer('✅ Добавлено в «Заработать».')
        if cmd=='/givecash' and await admin(m.from_user.id) and len(p)==3:
            target=await find_user(p[1]); amount=int(p[2]) if p[2].isdigit() else 0
            if not target or amount<=0:return await m.answer('❌ Неверные данные.')
            db=await connect();await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(amount,target['user_id']));await db.commit();await db.close();return await m.answer('✅ Валюта выдана.')
        if cmd=='/givepehot' and await admin(m.from_user.id) and len(p)==4:
            target=await find_user(p[1]);uid=int(p[2]) if p[2].isdigit() else 0;q=int(p[3]) if p[3].isdigit() else 0
            if not target or uid not in UNIT_BY_ID or q<=0:return await m.answer('❌ Неверные данные.')
            unit=UNIT_BY_ID[uid];db=await connect();await db.execute(f'UPDATE users SET {unit}={unit}+? WHERE user_id=?',(q,target['user_id']));await db.commit();await db.close();return await m.answer('✅ Выдано.')
        if cmd=='/setbonus' and await admin(m.from_user.id) and len(p)==3 and p[2].isdigit():
            key={'daily':'daily_bonus','sub':'subscription_bonus'}.get(p[1]);
            if not key:return await m.answer('❌ daily или sub')
            await set_setting(key,int(p[2]));return await m.answer('✅ Изменено.')
        if cmd=='/setdonate' and await admin(m.from_user.id) and len(p)==2:await set_setting('donate_contact',p[1]);return await m.answer('✅ Изменено.')
        if cmd=='/setchannel' and await admin(m.from_user.id) and len(p)==2:await set_setting('channel_username',p[1]);return await m.answer('✅ Изменено.')
        if cmd=='/setrule' and await admin(m.from_user.id) and len(p)>1:await set_setting('rules_text',text.split(maxsplit=1)[1]);return await m.answer('✅ Изменено.')
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
    elif typ=='earn_add': await m.answer('Используйте команду /add'+val+' https://t.me/... 150000')

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
    if d.startswith('quest:'):return await quest_claim(c,d.split(':',1)[1])
    if d.startswith('earn_check:'):
        _,kind,tid=d.split(':');return await earn_check(c,kind,int(tid),bot)
    if d=='help':return await safe(c,f'ℹ️ {BRAND} • ПОМОЩЬ\n\n{esc(await get_str("msg_help") or "Покупайте войска, развивайте ферму и участвуйте в боях.")}',back())
    if d=='rules':return await safe(c,f'📕 {BRAND} • ПРАВИЛА\n\n{esc(await get_str("msg_rules") or await get_str("rules_text"))}',back())
    if d=='attack':return await attack(c,0)
    if d.startswith('attack_page:'):return await attack(c,int(d.split(':',1)[1]))
    if d.startswith('opp:'):return await opponent(c,int(d.split(':',1)[1]))
    if d=='battle_confirm':return await battle_confirm(c,bot)
    if d=='admin':return await admin_panel(c)
    if d.startswith('a_'):return await admin_section(c,d)
    if d.startswith('earn_add:'):return await earn_add(c,d.split(':',1)[1])
    await c.answer('Кнопка не найдена.',show_alert=True)

async def main():
    if not BOT_TOKEN:raise RuntimeError('BOT_TOKEN is empty')
    await init_db();await init_settings(ADMIN_ID)
    db=await connect();await db.execute('INSERT OR IGNORE INTO admins(user_id) VALUES(?)',(ADMIN_ID,));await db.commit();await db.close()
    tg=Bot(BOT_TOKEN);dp=Dispatcher();dp.message.register(start,CommandStart());dp.message.register(text_handler,F.text);dp.callback_query.register(callback,F.data)
    print(f'{BRAND} started');await dp.start_polling(tg)

if __name__=='__main__':asyncio.run(main())
