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
'loss':('Поражение','{winner}; {loss}; {reward}'),
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
    u=await user(c.from_user.id);n='@'+u['username'] if u['username'] else 'не указан';kills='\n'.join(f'{a}: {int(u[b])}' for a,b in [('🪖 Пехота','kill_soldier'),('🎯 Перехватчики','kill_interceptor'),('🛩 БПЛА','kill_drone'),('🚙 БМП','kill_bmp'),('🛡 Танки','kill_tank'),('🚁 Вертолёты','kill_helicopter'),('✈️ Самолёты','kill_plane'),('🚀 Ракеты','kill_missile'),('💥 Артиллерия','kill_artillery')]);t=await tpl('profile',f'👤 {BRAND} • ПРОФИЛЬ\n\n👤 Юзер: {n}\n💵 Капитал: ${money(u["balance"])}\n🏭 Ферма: {u["farm_level"]}/10\n🏆 Побед: {u["attacks_won"]}\n💀 Поражений: {u["attacks_lost"]}\n⚔️ КД атаки: {cd_text(u)}\n\n🎯 УНИЧТОЖЕНО\n{kills}',username=n,balance=money(u['balance']),farm=u['farm_level'],wins=u['attacks_won'],losses=u['attacks_lost'],battle_cd=cd_text(u),kills=kills);await safe(c,t,back())
async def army(c):
    u=await user(c.from_user.id);kw={k:int(u[k]) for k in UNITS};kw['username']='@'+u['username'] if u['username'] else 'не указан';await safe(c,await tpl('army',f'🎖 {BRAND} • АРМИЯ\n\n{army_text(u)}',**kw),back())
async def balance_from_message(m):
    await ensure_user(m.from_user.id,m.from_user.username);u=await user(m.from_user.id);await m.answer(f'💵 {BRAND} • БАЛАНС\n\n💰 Капитал: ${money(u["balance"])}',reply_markup=home_kb(await admin(m.from_user.id)))
async def shop(c):
    items='\n'.join(f'{v["title"]} — ${money(v["price"])}' for k,v in UNITS.items() if k!='artillery');rows=[[(f'{v["title"]} — ${money(v["price"])}',f'buyq:{k}')] for k,v in UNITS.items() if k!='artillery'];rows.append([('⬅️ Назад','home')]);await safe(c,f'🛒 {BRAND} • ВОЕННЫЙ АРСЕНАЛ\n\n{items}\n\nВыберите единицу и введите количество.',kb(rows))
async def buyq(c,k):
    if k not in UNITS or k=='artillery':return await c.answer('Недоступно',show_alert=True)
    STATE[c.from_user.id]=('buy',k);await safe(c,f'🛒 {UNITS[k]["title"]}\n\nЦена: ${money(UNITS[k]["price"])}\n\nВведите количество:',back('shop'))
async def buy_confirm(c,k,q):
    if k not in UNITS or q<1 or q>1000000:return await c.answer('Некорректное количество',show_alert=True)
    price=UNITS[k]['price']*q;db=await connect();cur=await db.execute(f'UPDATE users SET balance=balance-?,{k}={k}+? WHERE user_id=? AND balance>=?',(price,q,c.from_user.id,price));await db.commit();await db.close()
    if cur.rowcount!=1:return await safe(c,'❌ Недостаточно средств.',back('shop'))
    await safe(c,f'✅ Покупка выполнена\n\n{UNITS[k]["title"]} × {q}\n💵 Списано: ${money(price)}',back('shop'))

async def main():
    if not BOT_TOKEN:raise RuntimeError('BOT_TOKEN is empty')
    await init_db();await init_settings(ADMIN_ID);db=await connect();await db.execute('INSERT OR IGNORE INTO admins(user_id) VALUES(?)',(ADMIN_ID,));
    if OWNER_ID2:await db.execute('INSERT OR IGNORE INTO admins(user_id) VALUES(?)',(OWNER_ID2,))
    await db.commit();await db.close();tg=Bot(BOT_TOKEN);dp=Dispatcher();dp.message.register(start,CommandStart());dp.message.register(text_handler,F.text);dp.callback_query.register(callback,F.data);print(f'{BRAND} started');await dp.start_polling(tg)
if __name__=='__main__':asyncio.run(main())
