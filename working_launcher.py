import asyncio, contextvars
import run
import bot as app
from config import UNITS
from db import connect, top_users

OWNER=contextvars.ContextVar('menu_owner',default=None)
PROMO_WAIT=set()
CODES={1:'soldier',2:'interceptor',3:'drone',4:'bmp',5:'tank',6:'helicopter',7:'plane',8:'missile',9:'artillery'}
CASES=('case1','case2','donate_case')

def cb(x):
    uid=OWNER.get();return x if uid is None or x.startswith(('accept:','decline:')) else f'g{uid}:{x}'

def kb(rows):
    from aiogram.types import InlineKeyboardButton,InlineKeyboardMarkup
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=a,callback_data=cb(b)) for a,b in row] for row in rows])
app.kb=kb

async def shop(c):
    token=OWNER.set(c.from_user.id if c.message and c.message.chat.type!='private' else None)
    try:
        rows=[];text=[]
        for k in ('soldier','interceptor','drone','bmp','artillery','tank','helicopter','plane','missile'):
            v=UNITS[k];text.append(f'{v["title"]} — ${app.money(v["price"])}');rows.append([(f'{v["title"]} — ${app.money(v["price"])}',f'buyq:{k}')])
        rows.append([('⬅️ Назад','home')]);return await app.safe(c,'🛒 АРСЕНАЛ\n\n'+'\n'.join(text),kb(rows))
    finally:OWNER.reset(token)

async def buyq(c,k):
    if k not in UNITS:return await c.answer('Недоступно',show_alert=True)
    token=OWNER.set(c.from_user.id if c.message and c.message.chat.type!='private' else None)
    try:
        app.STATE[c.from_user.id]=('buy',k);return await app.safe(c,f'🛒 {UNITS[k]["title"]}\n\nЦена: ${app.money(UNITS[k]["price"])}\n\nВведите количество:',app.back('shop'))
    finally:OWNER.reset(token)

async def top(c):
    token=OWNER.set(c.from_user.id if c.message and c.message.chat.type!='private' else None)
    try:
        rows=await top_users(50);out=[]
        for i,r in enumerate(rows,1):
            medal=('🥇','🥈','🥉')[i-1] if i<=3 else '🎖️';name='@'+r['username'] if r['username'] else f'ID {r["user_id"]}'
            out.append(f'{medal} {i}. {name} — 🎖 {int(r["army_total"])}')
        return await app.safe(c,'🏆 ТОП ВОЯК\n\n'+('\n'.join(out) or 'Пока игроков нет.')+'\n\nРейтинг: солдат 1 | перехватчик 1 | БПЛА 3 | БМП 7 | артиллерия 8 | танк 10 | вертолёт 15 | самолёт 25 | ракета 50',app.back())
    finally:OWNER.reset(token)

async def help_cmd(m):return await m.answer('ℹ️ ПОМОЩЬ\n\nхелп / help — помощь\nбонус / bonus — бонус\nармия / а — армия\nшоп — магазин\nатака / вызовы — бой\nпромо — промокод\nачивки — достижения\nтоп — рейтинг')

async def codes(m):
    if not await run.admin_ok(m.from_user.id):return await m.answer('⛔ Нет доступа.')
    names=['','солдат','перехватчик','БПЛА','БМП','танк','вертолёт','самолёт','ракета','артиллерия']
    return await m.answer('КОДЫ ТЕХНИКИ\n\n'+'\n'.join(f'{i} — {names[i]}' for i in range(1,10))+'\n\nПример: /givepehot @username 9 2\n\nПромо-кейсы: case1, case2, donate_case')

async def give(m,p):
    if not await run.admin_ok(m.from_user.id):return await m.answer('⛔ Нет доступа.')
    if len(p)!=3:return await m.answer('Формат: /givepehot @username КОД КОЛИЧЕСТВО\nИспользуй /коды')
    u=await app.find_user(p[0])
    try:code,n=int(p[1]),int(p[2])
    except ValueError:return await m.answer('Неверный код/количество')
    if not u or code not in CODES or n<=0:return await m.answer('Неверные данные. /коды')
    unit=CODES[code];db=await connect();await db.execute(f'UPDATE users SET {unit}={unit}+? WHERE user_id=?',(n,u['user_id']));await db.commit();await db.close();return await m.answer(f'✅ {UNITS[unit]["title"]} × {n} выдано.')

async def addpromo(m,p):
    if not await run.admin_ok(m.from_user.id):return await m.answer('⛔ Нет доступа.')
    if len(p)==3:code,amount,limit=p;rtype='money'
    elif len(p)==5 and p[1].lower()=='unit':code,_,unit,amount,limit=p;rtype='unit:'+unit.lower()
    elif len(p)==5 and p[1].lower()=='case':code,_,case,amount,limit=p;rtype='case:'+case.lower()
    else:return await m.answer('/addpromo КОД СУММА ЛИМИТ\n/addpromo КОД unit ТЕХНИКА КОЛИЧЕСТВО ЛИМИТ\n/addpromo КОД case КЕЙС КОЛИЧЕСТВО ЛИМИТ\nКейсы: case1, case2, donate_case')
    try:a,l=int(amount),int(limit)
    except ValueError:return await m.answer('Количество и лимит должны быть числами')
    if a<=0 or l<=0:return await m.answer('Количество и лимит должны быть больше нуля')
    if rtype.startswith('unit:') and rtype[5:] not in UNITS:return await m.answer('Неизвестная техника')
    if rtype.startswith('case:') and rtype[5:] not in CASES:return await m.answer('Кейс: case1, case2, donate_case')
    db=await connect();await db.execute('INSERT INTO promos(code,amount,uses,max_uses,reward_type,reward_amount) VALUES(?,?,0,?,?,?) ON CONFLICT(code) DO UPDATE SET amount=excluded.amount,max_uses=excluded.max_uses,reward_type=excluded.reward_type,reward_amount=excluded.reward_amount',(code,a if rtype=='money' else 0,l,rtype,a));await db.commit();await db.close();return await m.answer('✅ Промокод создан: '+code)

async def usepromo(m,code):
    db=await connect()
    try:
        cur=await db.execute('SELECT * FROM promos WHERE lower(code)=lower(?)',(code.strip(),));p=await cur.fetchone()
        if not p:return await m.answer('❌ Промокод не найден.')
        if int(p['uses'])>=int(p['max_uses']):return await m.answer('❌ Промокод больше недоступен.')
        cur=await db.execute('SELECT 1 FROM promo_uses WHERE code=? AND user_id=?',(p['code'],m.from_user.id))
        if await cur.fetchone():return await m.answer('❌ Вы уже использовали этот промокод.')
        rt=str(p['reward_type'] or 'money');amount=int(p['reward_amount'] or p['amount'] or 0)
        if rt=='money':await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(amount,m.from_user.id));reward=f'💵 +${app.money(amount)}'
        elif rt.startswith('unit:'):
            unit=rt[5:]
            if unit not in UNITS:return await m.answer('❌ Неизвестная техника.')
            await db.execute(f'UPDATE users SET {unit}={unit}+? WHERE user_id=?',(amount,m.from_user.id));reward=f'{UNITS[unit]["title"]} × {amount}'
        elif rt.startswith('case:'):
            cid=rt[5:]
            if cid not in CASES:return await m.answer('❌ Неизвестный кейс.')
            await db.execute('CREATE TABLE IF NOT EXISTS case_inventory(user_id INTEGER PRIMARY KEY,case1 INTEGER NOT NULL DEFAULT 0,case2 INTEGER NOT NULL DEFAULT 0,donate_case INTEGER NOT NULL DEFAULT 0)')
            vals=(amount if cid=='case1' else 0,amount if cid=='case2' else 0,amount if cid=='donate_case' else 0)
            await db.execute('INSERT INTO case_inventory(user_id,case1,case2,donate_case) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET case1=case1+excluded.case1,case2=case2+excluded.case2,donate_case=donate_case+excluded.donate_case',(m.from_user.id,*vals));reward=f'📦 {cid} × {amount}'
        else:return await m.answer('❌ Неизвестный тип награды.')
        await db.execute('UPDATE promos SET uses=uses+1 WHERE code=?',(p['code'],));await db.execute('INSERT INTO promo_uses(code,user_id) VALUES(?,?)',(p['code'],m.from_user.id));await db.commit()
    finally:await db.close()
    return await m.answer(f'🎉 Промокод активирован!\n\nНаграда: {reward}')

orig_cb=run.callback;orig_text=run.text_handler
app.shop=shop;app.buyq=buyq;app.top=top

async def callback(c,b):
    d=c.data or '';group=bool(c.message and c.message.chat.type!='private')
    if group:
        if d.startswith('g') and ':' in d:
            uid,real=d[1:].split(':',1)
            try:owner=int(uid)
            except ValueError:owner=0
            if owner!=c.from_user.id and not real.startswith(('accept:','decline:')):return await c.answer('⛔ Это меню принадлежит другому пользователю.',show_alert=True)
            d=real;c.data=d
        elif not d.startswith(('accept:','decline:')):return await c.answer('⛔ Это меню нельзя использовать другому пользователю.',show_alert=True)
    token=OWNER.set(c.from_user.id if group else None)
    try:
        if d=='shop':return await shop(c)
        if d.startswith('buyq:'):return await buyq(c,d[5:])
        if d=='top':return await top(c)
        return await orig_cb(c,b)
    finally:OWNER.reset(token)

class FakeCallback:
    def __init__(self,m):self.message=m;self.from_user=m.from_user;self.data='bonus';self.bot=None
    async def answer(self,*a,**k):pass

async def text(m,b):
    token=OWNER.set(m.from_user.id if m.chat.type!='private' else None)
    try:
        p=(m.text or '').strip().split();cmd=p[0].split('@')[0].lower() if p else '';low=(m.text or '').strip().lower()
        if low in ('хелп','help','/help','/хелп'):return await help_cmd(m)
        if low in ('бонус','bonus','/bonus','/бонус'):return await app.bonus(FakeCallback(m))
        if cmd in ('/коды','/codes','коды','codes'):return await codes(m)
        if cmd=='/givepehot':return await give(m,p[1:])
        if cmd=='/addpromo':return await addpromo(m,p[1:])
        if cmd in ('/promo','/промо','/промокод') and len(p)>1:return await usepromo(m,p[1])
        if low in ('промо','промокод','promo','/promo','/промо','/промокод'):
            PROMO_WAIT.add(m.from_user.id);return await m.answer('🎟 Введите промокод:')
        if m.from_user.id in PROMO_WAIT and not m.text.startswith('/'):
            PROMO_WAIT.discard(m.from_user.id);return await usepromo(m,m.text.strip())
        return await orig_text(m,b)
    finally:OWNER.reset(token)
run.callback=callback;run.text_handler=text

if __name__=='__main__':asyncio.run(run.main())
