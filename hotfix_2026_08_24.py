import asyncio
from datetime import datetime, timedelta, timezone
import random
import bot as app
from config import OWNER_ID, OWNER_ID2, OWNER_IDS, ADMIN_ID, FARMS, UNITS
from db import connect, is_admin, setting, set_setting

FARM_TAX_LIMITS={1:100_000,2:300_000,3:720_000,4:1_000_000,5:2_000_000,6:2_800_000,7:4_500_000,8:6_600_000,9:15_500_000,10:18_000_000}

def money(v): return f'{int(v):,}'.replace(',',' ')
def now(): return datetime.now(timezone.utc)
async def admin(uid):
    return uid in OWNER_IDS or uid in (OWNER_ID,OWNER_ID2) or await is_admin(uid,ADMIN_ID)
async def tax_limit(level): return FARM_TAX_LIMITS.get(int(level),0)

async def farm(c):
    u=await app.user(c.from_user.id);lvl=int(u['farm_level']);f=FARMS[lvl];limit=await tax_limit(lvl);tax=int(u['tax'])
    status='🟢 АКТИВНА' if lvl else '⚪ НЕ РАЗВЁРНУТА'
    text=await app.tpl('farm',f'🏭 {app.BRAND} • ФЕРМА\n\nУровень: {lvl}/10\nПроизводство: ${money(f["income"])}/час\nНалог накоплен: ${money(tax)} / ${money(limit)}\nСтавка налога: 25%\nСтатус: {status}',level=lvl,income=money(f['income']),tax=money(tax),status=status)
    await app.safe(c,text,app.kb([[('💰 Получить','payout'),('⬆️ Улучшить','upgrade')],[('💸 Оплатить налог','paytax')],[('⬅️ Назад','home')]]))

async def payout(c):
    u=await app.user(c.from_user.id);lvl=int(u['farm_level'])
    if lvl<=0:return await app.safe(c,'🏭 Сначала улучшите ферму до 1 уровня за $500 000.',app.back('farm'))
    tax=int(u['tax']);limit=await tax_limit(lvl);income=int(FARMS[lvl]['income']);new_tax=tax+int(income*.25)
    if tax>=limit or new_tax>=limit:
        return await app.safe(c,f'💸 Налог достиг лимита для {lvl} уровня.\n\nНужно оплатить: ${money(tax)}.',app.back('farm'))
    try:
        last=datetime.fromisoformat(u['last_payout']);last=last if last.tzinfo else last.replace(tzinfo=timezone.utc)
    except Exception:last=now()-timedelta(hours=1)
    if now()-last<timedelta(hours=1):return await app.safe(c,'⏳ Выплата доступна один раз в час.',app.back('farm'))
    db=await connect();await db.execute('UPDATE users SET balance=balance+?,last_payout=?,tax=? WHERE user_id=?',(income,now().isoformat(),new_tax,c.from_user.id));await db.commit();await db.close()
    await app.safe(c,f'💰 Получено: +${money(income)}\n💸 В налог добавлено: ${money(int(income*.25))}\n📊 Налог: ${money(new_tax)} / ${money(limit)}',app.back('farm'))

async def paytax(c):
    u=await app.user(c.from_user.id);tax=int(u['tax'])
    if tax<=0:return await app.safe(c,'✅ Налог к оплате отсутствует.',app.back('farm'))
    if int(u['balance'])<tax:return await app.safe(c,f'❌ Недостаточно средств. Нужно ${money(tax)}.',app.back('farm'))
    db=await connect();await db.execute('UPDATE users SET balance=balance-?,tax=0 WHERE user_id=?',(tax,c.from_user.id));await db.commit();await db.close();await app.safe(c,f'✅ Налог ${money(tax)} оплачен. Ферма снова может приносить прибыль.',app.back('farm'))

async def upgrade(c):
    u=await app.user(c.from_user.id);lvl=int(u['farm_level'])
    if lvl>=10:return await app.safe(c,'🏭 Ферма уже на максимальном 10 уровне.',app.back('farm'))
    cost=500_000 if lvl==0 else int(FARMS[lvl+1]['upgrade'])
    db=await connect();cur=await db.execute('UPDATE users SET balance=balance-?,farm_level=? WHERE user_id=? AND balance>=?',(cost,lvl+1,c.from_user.id,cost));await db.commit();await db.close()
    if cur.rowcount!=1:return await app.safe(c,f'❌ Для {lvl+1} уровня нужно ${money(cost)}.',app.back('farm'))
    await app.safe(c,f'⬆️ Ферма улучшена: {lvl} → {lvl+1} уровень.\n💵 Списано: ${money(cost)}',app.back('farm'))

async def promo_apply(m,code):
    db=await connect();cur=await db.execute('SELECT * FROM promos WHERE lower(code)=lower(?)',(code.strip(),));p=await cur.fetchone()
    if not p:await db.close();return await m.answer('❌ Промокод не найден.')
    if int(p['uses'])>=int(p['max_uses']):await db.close();return await m.answer('❌ Промокод больше недоступен.')
    cur=await db.execute('SELECT 1 FROM promo_uses WHERE code=? AND user_id=?',(p['code'],m.from_user.id))
    if await cur.fetchone():await db.close();return await m.answer('❌ Вы уже использовали этот промокод.')
    reward_type=p['reward_type'] if 'reward_type' in p.keys() else 'money';amount=int(p['reward_amount'] if 'reward_amount' in p.keys() else p['amount']);col=reward_type if reward_type in UNITS else 'balance'
    await db.execute(f'UPDATE users SET {col}={col}+? WHERE user_id=?',(amount,m.from_user.id));await db.execute('UPDATE promos SET uses=uses+1 WHERE code=?',(p['code'],));await db.execute('INSERT INTO promo_uses(code,user_id) VALUES(?,?)',(p['code'],m.from_user.id));await db.commit();await db.close()
    label='$'+money(amount) if col=='balance' else f'{UNITS[col]["title"]} × {amount}'
    await m.answer(f'🎉 Промокод активирован!\n\nНаграда: {label}')

async def text_handler(m,bot):
    text=(m.text or '').strip();p=text.split();low=text.lower();cmd=p[0].split('@')[0].lower() if p else ''
    if not text.startswith('/'):
        if low in ('адм','админ'):
            if await admin(m.from_user.id): return await app.admin_panel(m)
            return await m.answer('⛔ Нет доступа.')
        if low in ('хелп','help'): return await app._original_text_handler(m,bot) if low=='help' else await app._original_text_handler(m,bot)
        if low=='атаковать': return await app.attack_from_message(m)
        if p and p[0].lower()=='атаковать' and len(p)>=2: return await app.attack_by_username(m,p[1])
        if low.startswith(('промокод ','промо ','promo ')): return await promo_apply(m,p[1])
        if low in ('промо','промокод','promo'): app.STATE[m.from_user.id]=('promo',None);return await m.answer('🎟 Введите промокод:')
    if text.startswith('/'):
        if cmd in ('/adm','/admin'):
            if await admin(m.from_user.id):return await app.admin_panel(m)
            return await m.answer('⛔ Нет доступа.')
        if cmd in ('/promo','/промо','/промокод'):
            if len(p)>=2:return await promo_apply(m,p[1])
            app.STATE[m.from_user.id]=('promo',None);return await m.answer('🎟 Введите промокод:')
        if cmd in ('/atack','/attack'):
            if len(p)>=2:return await app.attack_by_username(m,p[1])
            return await app.attack_from_message(m)
        if cmd=='/takecash' and await admin(m.from_user.id) and len(p)==3:
            target=await app.find_user(p[1]);amount=int(p[2]) if p[2].isdigit() else 0
            if not target or amount<=0:return await m.answer('❌ Формат: /takecash @user сумма')
            db=await connect();cur=await db.execute('UPDATE users SET balance=MAX(0,balance-?) WHERE user_id=?',(amount,target['user_id']));await db.commit();await db.close();return await m.answer('✅ Валюта списана.')
        if cmd=='/addpromo' and await admin(m.from_user.id):
            if len(p)==4 and p[2].isdigit() and p[3].isdigit(): code=p[1];rtype='money';amount=int(p[2]);limit=int(p[3])
            elif len(p)==5 and p[3].isdigit() and p[4].isdigit(): code=p[1];rtype=p[2].lower();amount=int(p[3]);limit=int(p[4])
            else:return await m.answer('❌ Формат: /addpromo КОД СУММА ЛИМИТ\nили /addpromo КОД money|soldier|interceptor|drone|bmp|tank|helicopter|plane|missile|artillery КОЛИЧЕСТВО ЛИМИТ')
            if rtype!='money' and rtype not in UNITS:return await m.answer('❌ Неизвестный тип награды.')
            db=await connect();await db.execute('INSERT INTO promos(code,amount,max_uses,reward_type,reward_amount) VALUES(?,?,?,?,?) ON CONFLICT(code) DO UPDATE SET amount=excluded.amount,max_uses=excluded.max_uses,reward_type=excluded.reward_type,reward_amount=excluded.reward_amount',(code,amount if rtype=='money' else 0,limit,rtype,amount));await db.commit();await db.close();return await m.answer('✅ Промокод создан.')
    return await app._original_text_handler(m,bot)

async def battle_accept(c,attacker_id,bot):
    attacker_id=int(attacker_id);defender_id=c.from_user.id
    if app.INVITES.get(attacker_id)!=defender_id:return await c.answer('Приглашение уже недействительно.',show_alert=True)
    app.INVITES.pop(attacker_id,None);att=await app.user(attacker_id);defn=await app.user(defender_id)
    if not att or not defn or app.cd_seconds(att) or app.cd_seconds(defn):return await c.answer('Бой уже недоступен.',show_alert=True)
    await c.message.edit_text('⚔️ БОЙ НАЧИНАЕТСЯ...')
    for i in range(15):
        line=random.choice(app.BATTLE_LINES)
        try:await c.message.edit_text(f'⚔️ {app.BRAND} • БОЙ\n\n{line}\n\n⏱ {15-i} сек.')
        except Exception:pass
        await asyncio.sleep(1)
    a_after,d_after,winner,events,kills_a,kills_d=app.resolve(att,defn,with_kills=True)
    winner_id=attacker_id if winner=='attacker' else defender_id;loser_id=defender_id if winner=='attacker' else attacker_id
    winner_src=att if winner=='attacker' else defn;loser_src=defn if winner=='attacker' else att
    winner_arm={k:int(winner_src[k]) for k in UNITS};loser_arm={k:int(loser_src[k])*80//100 for k in UNITS}
    winner_k=kills_a if winner=='attacker' else kills_d
    reward=int(sum(winner_k[k]*UNITS[k]['price'] for k in UNITS)*.05)
    loser_reward=int(sum((int(loser_src[k])-loser_arm[k])*UNITS[k]['price'] for k in UNITS)*.02)
    db=await connect();sets=','.join(f'{k}=?' for k in UNITS);ksets=','.join(f'kill_{k}=kill_{k}+?' for k in UNITS)
    await db.execute(f'UPDATE users SET {sets},attacks_won=attacks_won+1,last_attack=? WHERE user_id=?',[winner_arm[k] for k in UNITS]+[app.now().isoformat(),winner_id])
    await db.execute(f'UPDATE users SET {sets},attacks_lost=attacks_lost+1,last_attack=? WHERE user_id=?',[loser_arm[k] for k in UNITS]+[app.now().isoformat(),loser_id])
    await db.execute(f'UPDATE users SET {ksets} WHERE user_id=?',[winner_k[k] for k in UNITS]+[winner_id])
    if reward:await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(reward,winner_id))
    if loser_reward:await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(loser_reward,loser_id))
    await db.commit();await db.close()
    wn=await app.user(winner_id);winner_name='@'+wn['username'] if wn['username'] else f'ID {winner_id}';kills='\n'.join(f'{UNITS[k]["title"]}: {winner_k[k]}' for k in UNITS if winner_k[k]) or '—'
    wintext=await app.tpl('win',f'🏆 WIN\n\nПобедитель: {winner_name}\n💰 Награда: ${money(reward)}\n\n🎯 Уничтожено:\n{kills}',winner=winner_name,reward=money(reward),kills=kills)
    losstext=await app.tpl('loss',f'💀 LOSS\n\n🏆 Победитель: {winner_name}\n📉 Твоя армия: −20%\n💵 Компенсация: ${money(loser_reward)}',winner=winner_name,loss='20%',reward=money(loser_reward))
    await bot.send_message(winner_id,wintext,reply_markup=app.back());await bot.send_message(loser_id,losstext,reply_markup=app.back())

def home_kb(a=False):
    rows=[[('🏭 Ферма','farm'),('🎖 Армия','army')],[('🛒 Арсенал','shop'),('⚔️ Атаковать','attack')],[('💰 Заработать','earn'),('📋 Задания','quests')],[('🎁 Бонус','bonus'),('🎟 Промокод','promo')],[('📦 Кейсы','cases'),('👤 Профиль','profile')],[('🏆 Топ вояк','top'),('💳 Донат','donate')],[('📕 Правила','rules'),('ℹ️ Помощь','help')]]
    if a:rows.append([('⚙️ Админ-панель','admin')])
    return app.kb(rows)

def callback(c,bot):
    async def inner():
        d=c.data or ''
        if d=='a_promos': return await app.safe(c,'🎟 ПРОМОКОДЫ\n\nДеньги:\n/addpromo КОД СУММА ЛИМИТ\n\nТехника:\n/addpromo КОД soldier|interceptor|drone|bmp|tank|helicopter|plane|missile|artillery КОЛИЧЕСТВО ЛИМИТ',app.back('admin'))
        if d=='battle_confirm': return await battle_confirm(c,bot)
        if d.startswith('accept:'): return await battle_accept(c,d.split(':',1)[1],bot)
        return await app._original_callback(c,bot)
    return inner()
async def battle_confirm(c,bot): return await app.battle_confirm(c,bot)

def install():
    app._original_text_handler=getattr(app,'text_handler')
    app._original_callback=getattr(app,'callback')
    app.home_kb=home_kb;app.text_handler=text_handler;app.callback=callback
    app.farm=farm;app.payout=payout;app.paytax=paytax;app.upgrade=upgrade;app.battle_accept=battle_accept
