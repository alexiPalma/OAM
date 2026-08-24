import asyncio, html, random, re
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import BOT_TOKEN, OWNER_ID, OWNER_ID2, OWNER_IDS, ADMIN_ID, FARMS, UNITS, DONATIONS, UNIT_BY_ID, DAILY_BONUS_PRIZES
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
def clean(text): return re.sub(r'(?i)</?b>', '', str(text or '')).replace('&lt;b&gt;','').replace('&lt;/b&gt;','')

def home_kb(is_admin=False):
    rows = [[('🏭 Ферма','farm'),('🎖 Армия','army')], [('🛒 Арсенал','shop'),('⚔️ Атака','attack')], [('💰 Заработать','earn'),('🎁 Бонус','bonus')], [('📦 Кейсы','cases'),('👤 Профиль','profile')], [('🏆 Топ вояк','top'),('💳 Донат','donate')], [('📕 Правила','rules'),('ℹ️ Помощь','help')]]
    if is_admin: rows.append([('⚙️ Админ-панель','admin')])
    return kb(rows)

def admin_kb():
    return kb([[('💰 Валюта','a_currency'),('🎁 Бонусы','a_bonus')],[('📦 Кейсы','a_cases'),('🎟 Промокоды','a_promos')],[('💰 Заработать','a_earn'),('💳 Донат','a_donate')],[('📕 Правила','a_rules'),('👥 Админы','a_admins')],[('🎖 Выдать / списать','a_give'),('📣 Рассылка','a_broadcast')],[('📊 Статистика','a_stats'),('✏️ Редактировать','a_edit')],[('🏭 Фермы','a_farms'),('⚔️ Бои','a_battles')],[('👑 Владелец 2','a_owner2')],[('⬅️ Назад','home')]])

async def admin(uid): return uid in OWNER_IDS or await is_admin(uid, ADMIN_ID)

async def safe(c, text, markup=None):
    text = clean(text)
    try: await c.message.edit_text(text, reply_markup=markup, parse_mode=None)
    except Exception:
        try: await c.message.answer(text, reply_markup=markup, parse_mode=None)
        except Exception: pass
    try: await c.answer()
    except Exception: pass

def army_text(u): return '\n'.join(f'{v["title"]}: {int(u[k])}' for k,v in UNITS.items())
def army_size(u): return sum(int(u[k]) for k in UNITS if k != 'artillery')
def cd_seconds(u):
    raw=u['last_attack'] or ''
    if not raw:return 0
    try:
        dt=datetime.fromisoformat(raw)
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        return max(0,int((dt+ATTACK_CD-now()).total_seconds()))
    except Exception:return 0
def cd_text(u):
    s=cd_seconds(u);return 'ГОТОВО' if s<=0 else f'{s//60:02d}:{s%60:02d}'

async def start(m):
    await ensure_user(m.from_user.id,m.from_user.username);u=await user(m.from_user.id)
    await m.answer(f'⚔️ {BRAND}\n\n💵 Баланс: ${money(u["balance"])}\n🏭 Ферма: {u["farm_level"]}/10\n\n🛰 Центр управления войсками:',reply_markup=home_kb(await admin(m.from_user.id)))

async def profile(c):
    u=await user(c.from_user.id);name='@'+u['username'] if u['username'] else 'не указан';kills=[('🪖 Пехота','kill_soldier'),('🎯 Перехватчики','kill_interceptor'),('🛩 БПЛА','kill_drone'),('🚙 БМП','kill_bmp'),('🛡 Танки','kill_tank'),('🚁 Вертолёты','kill_helicopter'),('✈️ Самолёты','kill_plane'),('🚀 Ракеты','kill_missile'),('💥 Артиллерия','kill_artillery')];kt='\n'.join(f'{a}: {int(u[b])}' for a,b in kills)
    await safe(c,f'👤 {BRAND} • ПРОФИЛЬ\n\n👤 Юзер: {name}\n💵 Баланс: ${money(u["balance"])}\n🏭 Ферма: {u["farm_level"]}/10\n🏆 Побед: {u["attacks_won"]}\n💀 Поражений: {u["attacks_lost"]}\n⚔️ КД атаки: {cd_text(u)}\n\n🎯 УНИЧТОЖЕНО\n{kt}',back())
async def army(c): await safe(c,f'🎖 {BRAND} • АРМИЯ\n\n{army_text(await user(c.from_user.id))}',back())
async def shop(c):
    rows=[[(f'{v["title"]} — ${money(v["price"])}',f'buyq:{k}')] for k,v in UNITS.items() if k!='artillery'];rows.append([('⬅️ Назад','home')]);await safe(c,f'🛒 {BRAND} • ВОЕННЫЙ АРСЕНАЛ\n\nВыберите единицу. Затем бот спросит количество.',kb(rows))
async def buyq(c,key):
    if key not in UNITS or key=='artillery':return await c.answer('Недоступно',show_alert=True)
    STATE[c.from_user.id]=('buy',key);await safe(c,f'🛒 {UNITS[key]["title"]}\n\nЦена: ${money(UNITS[key]["price"])}\n\nВведите количество:',back('shop'))
async def buy_confirm(c,key,q):
    if key not in UNITS or q<1 or q>1000000:return await c.answer('Некорректное количество',show_alert=True)
    price=UNITS[key]['price']*q;db=await connect();cur=await db.execute(f'UPDATE users SET balance=balance-?,{key}={key}+? WHERE user_id=? AND balance>=?',(price,q,c.from_user.id,price));await db.commit();await db.close()
    if cur.rowcount!=1:return await safe(c,'❌ Недостаточно средств.',back('shop'))
    await safe(c,f'✅ Покупка выполнена\n\n{UNITS[key]["title"]} × {q}\n💵 Списано: ${money(price)}',back('shop'))

async def farm(c):
    u=await user(c.from_user.id);f=FARMS[u['farm_level']];status='🟢 АКТИВНА' if u['farm_level']>0 else '⚪ НЕ РАЗВЁРНУТА';await safe(c,f'🏭 {BRAND} • ФЕРМА\n\nУровень: {u["farm_level"]}/10\nПроизводство: ${money(f["income"])}/час\nНалог: ${money(u["tax"])}\nСтавка налога: 25%\nСтатус: {status}',kb([[('💰 Получить','payout'),('⬆️ Улучшить','upgrade')],[('💸 Оплатить налог','paytax')],[('⬅️ Назад','home')]]))
async def payout(c):
    u=await user(c.from_user.id)
    if u['farm_level']<=0:return await safe(c,'🏭 Сначала улучшите ферму до 1 уровня за $500 000.',back('farm'))
    if u['tax']>0:return await safe(c,f'❌ Сначала оплатите налог: ${money(u["tax"])}.',back('farm'))
    try:last=datetime.fromisoformat(u['last_payout']);last=last if last.tzinfo else last.replace(tzinfo=timezone.utc)
    except Exception:last=now()-timedelta(hours=1)
    if now()-last<timedelta(hours=1):return await safe(c,'⏳ Выплата доступна раз в час.',back('farm'))
    income=int(FARMS[u['farm_level']]['income']);tax=int(income*0.25);db=await connect();await db.execute('UPDATE users SET balance=balance+?,last_payout=?,tax=? WHERE user_id=?',(income,now().isoformat(),tax,c.from_user.id));await db.commit();await db.close();await safe(c,f'💰 Получено +${money(income)}\n💸 Налог 25%: ${money(tax)}.',back('farm'))
async def paytax(c):
    u=await user(c.from_user.id)
    if u['tax']<=0:return await safe(c,'✅ Налог уже оплачен.',back('farm'))
    if u['balance']<u['tax']:return await safe(c,f'❌ Нужно ${money(u["tax"])}.',back('farm'))
    db=await connect();await db.execute('UPDATE users SET balance=balance-tax,tax=0 WHERE user_id=?',(c.from_user.id,));await db.commit();await db.close();await safe(c,'✅ Налог оплачен.',back('farm'))
async def upgrade(c):
    u=await user(c.from_user.id);lvl=u['farm_level']
    if lvl>=10:return await safe(c,'🏭 Максимальный уровень — 10.',back('farm'))
    cost=FARMS[lvl+1]['upgrade'];db=await connect();cur=await db.execute('UPDATE users SET balance=balance-?,farm_level=? WHERE user_id=? AND balance>=?',(cost,lvl+1,c.from_user.id,cost));await db.commit();await db.close();await safe(c,f'⬆️ Ферма повышена до {lvl+1} уровня.\n💵 Списано: ${money(cost)}',back('farm')) if cur.rowcount else await safe(c,f'❌ Нужно ${money(cost)}.',back('farm'))

async def bonus(c):
    prizes=[f'{p:g}% — {label}' for p,unit,amount,label in DAILY_BONUS_PRIZES];await safe(c,f'🎁 {BRAND} • ЕЖЕДНЕВНЫЙ БОНУС\n\n'+'\n'.join(prizes),kb([[('🎁 Забрать','daily')],[('⬅️ Назад','home')]]))
async def daily(c):
    u=await user(c.from_user.id);today=now().date().isoformat()
    if u['daily_claim']==today:return await c.answer('Сегодня уже получено.',show_alert=True)
    r=random.uniform(0,100);acc=0
    for chance,unit,amount,label in DAILY_BONUS_PRIZES:
        acc+=chance
        if r<acc:break
    col='balance' if unit=='money' else unit;db=await connect();await db.execute(f'UPDATE users SET {col}={col}+?,daily_claim=? WHERE user_id=?',(amount,today,c.from_user.id));await db.commit();await db.close();await safe(c,f'🎁 Вы получили: {label}.',back('bonus'))

async def cases(c):
    await safe(c,f'📦 {BRAND} • КЕЙСЫ\n\n📦 Кейс 1 — $45 000\n75% — 2 солдата\n15% — 11 перехватчиков\n10% — 10 солдат\n\n📦 Кейс 2 — $5 000 000\n80% — БМП\n10% — танк\n7.5% — вертолёт\n2.5% — самолёт\n\n🎖 Президентский — 50 ⭐\n90% — вертолёт\n8% — самолёт\n2% — ракета',kb([[('📦 Кейс 1','case1'),('📦 Кейс 2','case2')],[('🎖 Президентский','president')],[('⬅️ Назад','home')]]))
async def case(c,cid):
    if cid=='president':return await safe(c,'🎖 Президентский кейс покупается через донат.',kb([[('💳 Донат','donate')],[('⬅️ Назад','cases')]]))
    price=45000 if cid=='case1' else 5000000;pool=[('soldier',2,75),('interceptor',11,15),('soldier',10,10)] if cid=='case1' else [('bmp',1,80),('tank',1,10),('helicopter',1,7.5),('plane',1,2.5)]
    u=await user(c.from_user.id)
    if u['balance']<price:return await c.answer('Недостаточно средств.',show_alert=True)
    r=random.uniform(0,100);acc=0
    for unit,amount,chance in pool:
        acc+=chance
        if r<acc:break
    db=await connect();cur=await db.execute('UPDATE users SET balance=balance-?,%s=%s+? WHERE user_id=? AND balance>=?'%(unit,unit),(price,amount,c.from_user.id,price));await db.commit();await db.close()
    if not cur.rowcount:return await c.answer('Недостаточно средств.',show_alert=True)
    await safe(c,f'📦 Кейс открыт!\n\n{UNITS[unit]["title"]} × {amount}\n🎲 Шанс: {chance}%',back('cases'))

async def donate(c): await safe(c,f'💳 {BRAND} • ДОНАТ\n\n50 ⭐ — ${money(DONATIONS[50])}\n100 ⭐ — ${money(DONATIONS[100])}\n500 ⭐ — ${money(DONATIONS[500])}\n\n📨 {esc(await get_str("donate_contact"))}',back())
async def top(c):
    rows=await top_users(50);out=[]
    for i,r in enumerate(rows,1):medal=['🥇','🥈','🥉'][i-1] if i<=3 else '🎖️';name='@'+r['username'] if r['username'] else f'ID {r["user_id"]}';out.append(f'{medal} {i}. {esc(name)} — ${money(r["balance"])}')
    await safe(c,f'🏆 {BRAND} • ТОП ВОЯК\n\n'+('\n'.join(out) or 'Пока игроков нет.'),back())

# The rest of the original handlers remain in this module in the repository.
