import asyncio, re
from datetime import datetime, timedelta, timezone
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from db import connect, user
from combat import resolve
from config import UNITS

COOLDOWN = timedelta(minutes=10)
PENDING = {}

def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=a, callback_data=b) for a,b in row] for row in rows])

def now(): return datetime.now(timezone.utc)
def money(v): return f'{int(v):,}'.replace(',',' ')

def cooldown_seconds(u):
    raw=u['last_attack'] or ''
    if not raw:return 0
    try:
        dt=datetime.fromisoformat(raw)
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        return max(0,int((dt+COOLDOWN-now()).total_seconds()))
    except Exception:return 0

def army_size(u): return sum(int(u[k]) for k in UNITS if k!='artillery')
def army_text(u): return '\n'.join(f'{UNITS[k]["title"]}: {int(u[k])}' for k in UNITS)
def clean(text): return re.sub(r'(?i)</?b>|&lt;/?b&gt;','',str(text or ''))

def kill_stats(kills):
    return '\n'.join(f'{UNITS[key]["title"]}: {int(kills.get(key,0))}' for key in UNITS)

async def show(c,text,markup=None):
    text=clean(text)
    try: await c.message.edit_text(text,reply_markup=markup)
    except Exception:
        try: await c.message.answer(text,reply_markup=markup)
        except Exception: pass
    try: await c.answer()
    except Exception: pass

async def attack_menu(c,page=0):
    me=await user(c.from_user.id); left=cooldown_seconds(me)
    if left:return await show(c,f'⚔️ WorldWarDynasty • АТАКА\n\n⏳ До следующей атаки: {left//60:02d}:{left%60:02d}',kb([[('⬅️ Назад','home')]]))
    db=await connect();cur=await db.execute('SELECT * FROM users WHERE user_id!=? ORDER BY balance DESC',(c.from_user.id,));rows=await cur.fetchall();await db.close()
    players=[r for r in rows if not cooldown_seconds(r) and army_size(r)>0]
    per=10;pages=max(1,(len(players)+per-1)//per);page=max(0,min(page,pages-1));items=players[page*per:(page+1)*per]
    buttons=[]
    for p in items:
        name='@'+p['username'] if p['username'] else f'ID {p["user_id"]}'
        buttons.append([(f'⚔️ {name} · {army_size(p)} ед.',f'opp:{p["user_id"]}')])
    if not items:buttons.append([('🔄 Обновить','attack')])
    nav=[]
    if page>0:nav.append(('⬅️ Назад',f'attack_page:{page-1}'))
    if page<pages-1:nav.append(('➡️ Далее',f'attack_page:{page+1}'))
    if nav:buttons.append(nav)
    buttons.append([('⬅️ Назад','home')])
    await show(c,f'⚔️ WorldWarDynasty • ВЫБОР ПРОТИВНИКА\n\nДоступно: {len(players)}\nСтраница: {page+1}/{pages}\n\nВыберите противника:',kb(buttons))

async def opponent(c,uid):
    uid=int(uid)
    if uid==c.from_user.id:return await c.answer('Нельзя атаковать себя.',show_alert=True)
    me=await user(c.from_user.id);opp=await user(uid)
    if not opp:return await c.answer('Игрок не найден.',show_alert=True)
    if cooldown_seconds(me):
        left=cooldown_seconds(me);return await c.answer(f'Ваш КД: {left//60:02d}:{left%60:02d}',show_alert=True)
    if cooldown_seconds(opp):return await c.answer('Этот игрок сейчас недоступен.',show_alert=True)
    if army_size(opp)<=0:return await c.answer('У этого игрока нет армии.',show_alert=True)
    PENDING[c.from_user.id]=uid
    name='@'+opp['username'] if opp['username'] else f'ID {uid}'
    await show(c,f'🎯 WorldWarDynasty • ПРОТИВНИК\n\n👤 {name}\n\nАРМИЯ ПРОТИВНИКА\n{army_text(opp)}',kb([[('⚔️ НАПАСТЬ','battle_confirm')],[('⬅️ Назад','attack')]]))

async def animate_one(message,lines,prefix=''):
    for line in lines:
        try: await message.edit_text(clean(prefix+line))
        except Exception: pass
        await asyncio.sleep(1)

async def confirm(c):
    # IMPORTANT: this function is kept as a fallback only. The active callback
    # below delegates battle_confirm to bot.battle_confirm, which is patched by
    # battle_rules_patch and records the attacker's exact message ID. Previously
    # this local confirm() bypassed that patch, so the attacker never received
    # the synchronized animation.
    uid=PENDING.get(c.from_user.id)
    if not uid:return await c.answer('Сначала выберите противника.',show_alert=True)
    me=await user(c.from_user.id);opp=await user(uid)
    if not opp:return await c.answer('Игрок недоступен.',show_alert=True)
    return await c.answer('Бой обрабатывается активным battle_rules_patch.',show_alert=True)

def install(bot_module):
    original_callback=bot_module.callback
    async def wrapped_callback(c,bot):
        d=c.data or ''
        if d=='attack':return await attack_menu(c,0)
        if d.startswith('attack_page:'):return await attack_menu(c,int(d.split(':',1)[1]))
        if d.startswith('opp:'):return await opponent(c,int(d.split(':',1)[1]))
        if d=='battle_confirm':
            # Do NOT call the local confirm(). The real synchronized handler is
            # bot_module.battle_confirm, installed by battle_rules_patch. This
            # is the critical fix: the previous runtime wrapper intercepted the
            # callback and completely bypassed the synchronized implementation.
            return await bot_module.battle_confirm(c,bot)
        return await original_callback(c,bot)
    bot_module.callback=wrapped_callback
    async def clean_bonus(c):
        prizes=['50% — $100 000','20% — 10 перехватчиков','10% — 2 БПЛА','5% — БМП','5% — 10 БПЛА','2.5% — танк','2.5% — $300 000','4.9% — 50 перехватчиков','0.1% — вертолёт']
        return await bot_module.safe(c,'🎁 WorldWarDynasty • ЕЖЕДНЕВНЫЙ БОНУС\n\n'+'\n'.join(prizes),bot_module.kb([[('🎁 Забрать','daily')],[('⬅️ Назад','home')]]))
    bot_module.bonus=clean_bonus
    original_profile=bot_module.profile
    async def profile_with_cd(c):
        await original_profile(c)
        left=cooldown_seconds(await user(c.from_user.id))
        if left:
            try: await c.message.edit_text((c.message.text or '')+f'\n\n⚔️ КД атаки: {left//60:02d}:{left%60:02d}',reply_markup=bot_module.back())
            except Exception: pass
    bot_module.profile=profile_with_cd
    original_safe=bot_module.safe
    async def clean_safe(c,text,markup=None): return await original_safe(c,clean(text),markup)
    bot_module.safe=clean_safe
