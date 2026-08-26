import asyncio, re
from datetime import datetime, timedelta, timezone
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import UNITS
from db import connect, user
from combat import resolve

BATTLE_COOLDOWN=timedelta(minutes=10)
PENDING={}
SYNC_INVITES={}


def _kb(rows): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=a,callback_data=b) for a,b in row] for row in rows])
def _money(v): return f'{int(v):,}'.replace(',',' ')
def _now(): return datetime.now(timezone.utc)
def _cd(u):
    if not u['last_attack']: return 0
    try:
        dt=datetime.fromisoformat(u['last_attack'])
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        return max(0,int((dt+BATTLE_COOLDOWN-_now()).total_seconds()))
    except Exception:
        return 0
def _army_power(u): return sum(int(u[k]) for k in UNITS if k!='artillery')
def _army(u): return '\n'.join(f'{v["title"]}: <b>{u[k]}</b>' for k,v in UNITS.items())

async def _safe(c,text,markup=None):
    try: await c.message.edit_text(text,reply_markup=markup,parse_mode='HTML')
    except Exception:
        try: await c.message.answer(text,reply_markup=markup,parse_mode='HTML')
        except Exception: await c.message.answer(re.sub('<[^>]+>','',text),reply_markup=markup)
    try: await c.answer()
    except Exception: pass

async def attack_menu(c,page=0):
    me=await user(c.from_user.id); left=_cd(me)
    if left:
        return await _safe(c,f'⚔️ <b>WorldWarDynasty • АТАКА</b>\n\n⏳ До следующей атаки: <b>{left//60:02d}:{left%60:02d}</b>',_kb([[('⬅️ Назад','home')]]))
    db=await connect();cur=await db.execute('SELECT * FROM users WHERE user_id!=? ORDER BY balance DESC',(c.from_user.id,));rows=await cur.fetchall();await db.close()
    players=[p for p in rows if not _cd(p) and _army_power(p)>0]
    per=10;pages=max(1,(len(players)+per-1)//per);page=max(0,min(page,pages-1));items=players[page*per:(page+1)*per]
    buttons=[]
    for p in items:
        name='@'+p['username'] if p['username'] else f'ID {p["user_id"]}'
        buttons.append([(f'⚔️ {name} • {_army_power(p)} ед.',f'bp:{p["user_id"]}')])
    nav=[]
    if page>0:nav.append(('⬅️ Предыдущая',f'bpage:{page-1}'))
    if page<pages-1:nav.append(('➡️ Следующая',f'bpage:{page+1}'))
    if nav:buttons.append(nav)
    buttons.append([('⬅️ Назад','home')])
    await _safe(c,f'⚔️ <b>WorldWarDynasty • ВЫБОР ПРОТИВНИКА</b>\n\nДоступно игроков: <b>{len(players)}</b>\nСтраница: <b>{page+1}/{pages}</b>\n\nВыберите противника:',_kb(buttons))

async def opponent(c,uid):
    uid=int(uid)
    if uid==c.from_user.id:return await c.answer('Нельзя атаковать себя.',show_alert=True)
    me=await user(c.from_user.id);opp=await user(uid)
    if not opp:return await c.answer('Игрок не найден.',show_alert=True)
    if _cd(me):return await c.answer(f'КД: {_cd(me)//60:02d}:{_cd(me)%60:02d}',show_alert=True)
    if _cd(opp):return await c.answer('Противник сейчас недоступен.',show_alert=True)
    PENDING[c.from_user.id]=uid
    name='@'+opp['username'] if opp['username'] else f'ID {uid}'
    await _safe(c,f'🎯 <b>ПРОТИВНИК</b>\n\n👤 {name}\n\n<b>АРМИЯ ПРОТИВНИКА</b>\n{_army(opp)}',_kb([[('⚔️ НАПАСТЬ','bconfirm')],[('⬅️ Назад','attack')]]))

async def confirm(c):
    """Legacy direct-battle path kept for compatibility with old callback data."""
    uid=PENDING.get(c.from_user.id)
    if not uid:return await c.answer('Сначала выберите противника.',show_alert=True)
    me=await user(c.from_user.id);opp=await user(uid)
    if not opp:return await c.answer('Игрок недоступен.',show_alert=True)
    PENDING.pop(c.from_user.id,None)
    return await _run_battle(c,uid,me,opp,bot=None,attacker_message_id=None)

BATTLE_LINES=['⚔️ Идёт бой','💥 Гремят взрывы','🪖 Пехота зачищает посадки','🔥 Раздаются выстрелы','🌫 Над полем боя поднимается дым','⚡ Ударная волна проходит по позиции','🪖 Подразделения продвигаются вперёд','💥 На линии фронта новый взрыв','🏴 Позиции сторон меняются','⚔️ Бой продолжается']

async def _edit_chat(bot,chat_id,message_id,text):
    if not message_id:return
    try: await bot.edit_message_text(chat_id=chat_id,message_id=message_id,text=text,parse_mode=None)
    except Exception: pass

async def _run_battle(c,attacker_id,me,opp,bot,attacker_message_id):
    attacker_id=int(attacker_id);defender_id=c.from_user.id
    first='⚔️ WorldWarDynasty • БОЙ\n\nБой начинается...\n\n⏱ 15 сек.'
    if attacker_message_id and bot:
        await _edit_chat(bot,attacker_id,attacker_message_id,first)
    try: await c.message.edit_text(first,parse_mode=None)
    except Exception: pass

    for i in range(15):
        line=BATTLE_LINES[i % len(BATTLE_LINES)]
        text=f'⚔️ WorldWarDynasty • БОЙ\n\n{line}\n\n⏱ {15-i} сек.'
        # Both edits are started at the same time. There is no separate animation loop.
        tasks=[asyncio.create_task(_edit_chat(bot,attacker_id,attacker_message_id,text))] if bot and attacker_message_id else []
        try: await c.message.edit_text(text,parse_mode=None)
        except Exception: pass
        if tasks: await asyncio.gather(*tasks,return_exceptions=True)
        await asyncio.sleep(1)

    a_after,d_after,winner,events,kills_a,kills_d=resolve(me,opp,with_kills=True)
    winner_id=attacker_id if winner=='attacker' else defender_id
    loser_id=defender_id if winner=='attacker' else attacker_id
    winner_arm=a_after if winner=='attacker' else d_after
    loser_raw=d_after if winner=='attacker' else a_after
    loser_source=opp if winner=='attacker' else me
    loser_arm={k:int(loser_raw[k])*80//100 for k in UNITS}
    winner_k=kills_a if winner=='attacker' else kills_d
    loser_k=kills_d if winner=='attacker' else kills_a
    reward=int(sum(winner_k[k]*UNITS[k]['price'] for k in UNITS)*.05)
    loser_reward=int(sum((int(loser_source[k])-loser_arm[k])*UNITS[k]['price'] for k in UNITS)*.02)

    db=await connect();setcols=', '.join(f'{k}=?' for k in UNITS);ksets=', '.join(f'kill_{k}=kill_{k}+?' for k in UNITS)
    await db.execute(f'UPDATE users SET {setcols},attacks_won=attacks_won+1,last_attack=? WHERE user_id=?',[winner_arm[k] for k in UNITS]+[_now().isoformat(),winner_id])
    await db.execute(f'UPDATE users SET {setcols},attacks_lost=attacks_lost+1,last_attack=? WHERE user_id=?',[loser_arm[k] for k in UNITS]+[_now().isoformat(),loser_id])
    await db.execute(f'UPDATE users SET {ksets} WHERE user_id=?',[winner_k[k] for k in UNITS]+[winner_id])
    await db.execute(f'UPDATE users SET {ksets} WHERE user_id=?',[loser_k[k] for k in UNITS]+[loser_id])
    await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(reward,winner_id))
    await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(loser_reward,loser_id))
    await db.commit();await db.close()

    titles={'soldier':'🪖 Пехота','interceptor':'🎯 Перехватчики','drone':'🛩 БПЛА','bmp':'🚙 БМП','tank':'🛡 Танки','helicopter':'🚁 Вертолёты','plane':'✈️ Самолёты','missile':'🚀 Ракеты','artillery':'💥 Артиллерия'}
    winner_kills='\n'.join(f'{titles[k]}: {int(winner_k.get(k,0))}' for k in titles)
    loser_kills='\n'.join(f'{titles[k]}: {int(loser_k.get(k,0))}' for k in titles)
    wn=await user(winner_id);winner_name='@'+wn['username'] if wn['username'] else f'ID {winner_id}'
    wintext=f'🏆 WIN\n\nПобедитель: {winner_name}\n💰 Награда: ${_money(reward)}\n\n🎯 Уничтожено:\n{winner_kills}'
    losstext=f'💀 LOSS\n\n🏆 Победитель: {winner_name}\n📉 Твоя армия: −20%\n💵 Компенсация: ${_money(loser_reward)}\n\n🎯 Уничтожено:\n{loser_kills}'
    if bot:
        await _edit_chat(bot,winner_id,attacker_message_id if winner_id==attacker_id else None,wintext)
        await _edit_chat(bot,loser_id,attacker_message_id if loser_id==attacker_id else None,losstext)
        if winner_id==defender_id:
            try: await c.message.edit_text(wintext,reply_markup=_kb([[('⬅️ Назад','home')]]),parse_mode=None)
            except Exception: pass
        else:
            try: await c.message.edit_text(losstext,reply_markup=_kb([[('⬅️ Назад','home')]]),parse_mode=None)
            except Exception: pass
    else:
        await _safe(c,wintext if winner_id==defender_id else losstext,_kb([[('⬅️ Назад','home')]]))

async def sync_battle_confirm(c,bot,original):
    attacker_id=c.from_user.id
    defender_id=original_pending=PENDING.get(attacker_id)
    # If this patch is layered on top of bot.py, use bot.py's PENDING dictionary.
    if defender_id is None:
        defender_id=getattr(original,'_battle_pending_target',None)
    bot_pending=getattr(__import__('bot'), 'PENDING', {})
    defender_id=bot_pending.get(attacker_id,defender_id)
    if defender_id is None:
        return await original(c,bot)
    try:
        result=await original(c,bot)
    except Exception:
        raise
    # bot.py has now edited the attacker's message to the waiting state.
    SYNC_INVITES[attacker_id]=(int(defender_id),c.message.message_id)
    return result

async def sync_accept(c,attacker_id,bot,original):
    attacker_id=int(attacker_id);defender_id=c.from_user.id
    bot_module=__import__('bot')
    bot_invites=getattr(bot_module,'INVITES',{})
    if bot_invites.get(attacker_id)!=defender_id:
        return await original(c,attacker_id,bot)
    me=await user(attacker_id);opp=await user(defender_id)
    if not me or not opp or _cd(me) or _cd(opp):
        bot_invites.pop(attacker_id,None);SYNC_INVITES.pop(attacker_id,None)
        return await c.answer('Бой уже недоступен.',show_alert=True)
    bot_invites.pop(attacker_id,None)
    stored=SYNC_INVITES.pop(attacker_id,None)
    attacker_message_id=stored[1] if stored and stored[0]==defender_id else None
    return await _run_battle(c,attacker_id,me,opp,bot,attacker_message_id)

async def patched_callback(c,bot,original):
    d=c.data or ''
    if d=='attack': return await attack_menu(c,0)
    if d.startswith('bpage:'): return await attack_menu(c,int(d.split(':',1)[1]))
    if d.startswith('bp:'): return await opponent(c,int(d.split(':',1)[1]))
    if d=='bconfirm': return await confirm(c)
    if d.startswith('accept:'): return await sync_accept(c,int(d.split(':',1)[1]),bot,original)
    if d=='bonus':
        prizes=['50% — $100 000','20% — 10 перехватчиков','10% — 2 БПЛА','5% — БМП','5% — 10 БПЛА','2.5% — танк','2.5% — $300 000','4.9% — 50 перехватчиков','0.1% — вертолёт']
        return await _safe(c,'🎁 <b>WorldWarDynasty • ЕЖЕДНЕВНЫЙ БОНУС</b>\n\n'+'\n'.join(prizes),_kb([[('🎁 Забрать','daily')],[('⬅️ Назад','home')]]))
    return await original(c,bot)

def install(bot_module):
    original=bot_module.callback
    async def wrapper(c,bot): return await patched_callback(c,bot,original)
    bot_module.callback=wrapper
    old_safe=bot_module.safe
    async def clean_safe(c,text,markup=None):
        text=text.replace('&lt;b&gt;','').replace('&lt;/b&gt;','')
        return await old_safe(c,text,markup)
    bot_module.safe=clean_safe
