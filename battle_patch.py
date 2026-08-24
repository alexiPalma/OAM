import asyncio, re
from datetime import datetime, timedelta, timezone
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import UNITS
from db import connect, user
from combat import resolve

BATTLE_COOLDOWN=timedelta(minutes=10)
PENDING={}

def _kb(rows): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=a,callback_data=b) for a,b in row] for row in rows])
def _money(v): return f'{int(v):,}'.replace(',',' ')
def _now(): return datetime.now(timezone.utc)
def _cd(u):
    if not u['last_attack']: return 0
    return max(0,int((datetime.fromisoformat(u['last_attack'])+BATTLE_COOLDOWN-_now()).total_seconds()))
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
    uid=PENDING.get(c.from_user.id)
    if not uid:return await c.answer('Сначала выберите противника.',show_alert=True)
    me=await user(c.from_user.id);opp=await user(uid)
    if not opp:return await c.answer('Игрок недоступен.',show_alert=True)
    if _cd(me):return await c.answer('Ваше КД ещё не закончилось.',show_alert=True)
    if _cd(opp):return await c.answer('Противник уже недоступен.',show_alert=True)
    PENDING.pop(c.from_user.id,None)
    await _safe(c,'⚔️ <b>БОЙ НАЧАЛСЯ</b>\n\nПодготовка армий...\n⏱ 15 секунд\n\n🛰 Разведка...')
    await asyncio.sleep(5); await _safe(c,'⚔️ <b>БОЙ</b>\n\n🛩 БПЛА на позиции...\n🎯 Перехватчики в воздухе...\n🚀 Ракетный удар...\n\n⏱ 10 секунд')
    await asyncio.sleep(5); await _safe(c,'⚔️ <b>БОЙ</b>\n\n💥 Артиллерия работает...\n🪖 Пехота вступила в бой...\n🚙 БМП атакуют...\n\n⏱ 5 секунд')
    await asyncio.sleep(5)
    me=await user(c.from_user.id);opp=await user(uid)
    a_after,d_after,winner,events,kills_a,kills_d=resolve(me,opp,with_kills=True)
    loser_id=uid if winner=='attacker' else c.from_user.id; winner_id=c.from_user.id if winner=='attacker' else uid
    loser_before=opp if winner=='attacker' else me
    loser_after={k:int(loser_before[k])*80//100 for k in UNITS}
    win_k=kills_a if winner=='attacker' else kills_d
    win_reward=int(sum(win_k[k]*UNITS[k]['price'] for k in UNITS)*0.05)
    loser_reward=int(sum((int(loser_before[k])-loser_after[k])*UNITS[k]['price'] for k in UNITS)*0.02)
    db=await connect();setcols=', '.join(f'{k}=?' for k in UNITS)
    await db.execute(f'UPDATE users SET {setcols},attacks_lost=attacks_lost+1,last_attack=? WHERE user_id=?',[loser_after[k] for k in UNITS]+[_now().isoformat(),loser_id])
    await db.execute('UPDATE users SET attacks_won=attacks_won+1,last_attack=? WHERE user_id=?',(_now().isoformat(),winner_id))
    for owner,kills in ((c.from_user.id,kills_a),(uid,kills_d)):
        sets=', '.join(f'kill_{k}=kill_{k}+?' for k in UNITS)
        await db.execute(f'UPDATE users SET {sets} WHERE user_id=?',[kills[k] for k in UNITS]+[owner])
    await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(win_reward,winner_id))
    await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(loser_reward,loser_id))
    report='\n'.join(events[-30:]) or 'Бой завершён.'
    await db.execute('INSERT INTO battle_log(attacker,defender,winner,report,created_at) VALUES(?,?,?,?,?)',(c.from_user.id,uid,winner_id,report,_now().isoformat()))
    await db.commit();await db.close()
    if winner=='attacker': result=f'🏆 <b>WIN</b>\n\nТы победил.\n\n💰 +${_money(win_reward)}\n🎯 Награда проигравшего: +${_money(loser_reward)}\n📉 Армия проигравшего: −20%\n\n{report}'
    else: result=f'💀 <b>LOSS</b>\n\nТы проиграл.\n\n💰 Награда победителя: +${_money(win_reward)}\n🎯 Твоя компенсация: +${_money(loser_reward)}\n📉 Твоя армия: −20%\n\n{report}'
    await _safe(c,result,_kb([[('⬅️ Назад','home')]]))

async def patched_callback(c,bot,original):
    d=c.data or ''
    if d=='attack': return await attack_menu(c,0)
    if d.startswith('bpage:'): return await attack_menu(c,int(d.split(':')[1]))
    if d.startswith('bp:'): return await opponent(c,int(d.split(':')[1]))
    if d=='bconfirm': return await confirm(c)
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
