import asyncio, re
from datetime import datetime, timedelta, timezone
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from db import connect, user
from combat import resolve
from config import UNITS

COOLDOWN = timedelta(minutes=10)
PENDING = {}

def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=a,callback_data=b) for a,b in row] for row in rows])

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
def clean(text):
    text=str(text or '')
    return text.replace('<b>','').replace('</b>','').replace('&lt;b&gt;','').replace('&lt;/b&gt;','')

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

async def confirm(c):
    uid=PENDING.get(c.from_user.id)
    if not uid:return await c.answer('Сначала выберите противника.',show_alert=True)
    me=await user(c.from_user.id);opp=await user(uid)
    if not opp:PENDING.pop(c.from_user.id,None);return await c.answer('Игрок недоступен.',show_alert=True)
    if cooldown_seconds(me):return await c.answer('Ваше КД ещё не закончилось.',show_alert=True)
    if cooldown_seconds(opp):PENDING.pop(c.from_user.id,None);return await c.answer('Противник уже недоступен.',show_alert=True)
    PENDING.pop(c.from_user.id,None)
    await show(c,'⚔️ WorldWarDynasty • БОЙ\n\nРазведка завершена.\n🛰 Стороны готовят армии...');await asyncio.sleep(5)
    await show(c,'⚔️ БОЙ\n\n🛩 БПЛА на позиции...\n🎯 Перехватчики в воздухе...\n🚀 Ракетный удар...');await asyncio.sleep(5)
    await show(c,'⚔️ БОЙ\n\n💥 Артиллерия работает...\n🪖 Пехота вступила в бой...\n🚙 БМП атакуют...');await asyncio.sleep(5)
    me=await user(c.from_user.id);opp=await user(uid)
    a_after,d_after,winner,events,kills_a,kills_d=resolve(me,opp,with_kills=True)
    surviving_winner=a_after if winner=='attacker' else d_after
    loser_source=d_after if winner=='attacker' else a_after
    loser_id=uid if winner=='attacker' else c.from_user.id;winner_id=c.from_user.id if winner=='attacker' else uid
    loser_before=opp if winner=='attacker' else me
    loser_after={k:max(0,int(loser_source[k])*80//100) for k in UNITS}
    winner_kills=kills_a if winner=='attacker' else kills_d;loser_kills=kills_d if winner=='attacker' else kills_a
    winner_reward=int(sum(winner_kills[k]*UNITS[k]['price'] for k in UNITS)*0.05)
    loser_reward=int(sum((int(loser_before[k])-loser_after[k])*UNITS[k]['price'] for k in UNITS)*0.02)
    db=await connect();sets=', '.join(f'{k}=?' for k in UNITS)
    await db.execute(f'UPDATE users SET {sets},attacks_won=attacks_won+1,last_attack=? WHERE user_id=?',[int(surviving_winner[k]) for k in UNITS]+[now().isoformat(),winner_id])
    await db.execute(f'UPDATE users SET {sets},attacks_lost=attacks_lost+1,last_attack=? WHERE user_id=?',[loser_after[k] for k in UNITS]+[now().isoformat(),loser_id])
    ksets=', '.join(f'kill_{k}=kill_{k}+?' for k in UNITS)
    await db.execute(f'UPDATE users SET {ksets} WHERE user_id=?',[winner_kills[k] for k in UNITS]+[winner_id])
    await db.execute(f'UPDATE users SET {ksets} WHERE user_id=?',[loser_kills[k] for k in UNITS]+[loser_id])
    await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(winner_reward,winner_id));await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(loser_reward,loser_id))
    report='\n'.join(events[-30:]) if events else 'Бой завершён.'
    await db.execute('INSERT INTO battle_log(attacker,defender,winner,report,created_at) VALUES(?,?,?,?,?)',(c.from_user.id,uid,winner_id,report,now().isoformat()));await db.commit();await db.close()
    if winner=='attacker':result=f'🏆 WIN\n\nТы победил.\n💰 +${money(winner_reward)}\n📉 Армия проигравшего: −20%\n💵 Компенсация проигравшему: +${money(loser_reward)}\n\n{report}'
    else:result=f'💀 LOSS\n\nТы проиграл.\n📉 Твоя армия уменьшена на 20%\n💰 Компенсация: +${money(loser_reward)}\n\n{report}'
    await show(c,result,kb([[('⬅️ Назад','home')]]))

def install(bot_module):
    original_callback=bot_module.callback
    async def wrapped_callback(c,bot):
        d=c.data or ''
        if d=='attack':return await attack_menu(c,0)
        if d.startswith('attack_page:'):return await attack_menu(c,int(d.split(':',1)[1]))
        if d.startswith('opp:'):return await opponent(c,int(d.split(':',1)[1]))
        if d=='battle_confirm':return await confirm(c)
        return await original_callback(c,bot)
    bot_module.callback=wrapped_callback
    async def clean_bonus(c):
        prizes=['50% — $100 000','20% — 10 перехватчиков','10% — 2 БПЛА','5% — БМП','5% — 10 БПЛА','2.5% — танк','2.5% — $300 000','4.9% — 50 перехватчиков','0.1% — вертолёт']
        return await bot_module.safe(c,'🎁 WorldWarDynasty • ЕЖЕДНЕВНЫЙ БОНУС\n\n'+'\n'.join(prizes),bot_module.kb([[('🎁 Забрать','daily')],[('⬅️ Назад','home')]]))
    bot_module.bonus=clean_bonus
    original_profile=bot_module.profile
    async def profile_with_cd(c):
        # Keep the existing profile and add the exact battle cooldown line.
        await original_profile(c)
        left=cooldown_seconds(await user(c.from_user.id))
        if left:
            try:
                await c.message.edit_text((c.message.text or '')+f'\n\n⚔️ КД атаки: {left//60:02d}:{left%60:02d}',reply_markup=bot_module.back())
            except Exception: pass
    bot_module.profile=profile_with_cd
    original_safe=bot_module.safe
    async def clean_safe(c,text,markup=None):
        text=clean(text)
        return await original_safe(c,text,markup)
    bot_module.safe=clean_safe
