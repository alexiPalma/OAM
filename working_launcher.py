"""OAM production launcher."""
import asyncio
import contextvars
import re
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart

import run
import bot as app
from config import BOT_TOKEN, ADMIN_ID, OWNER_IDS, UNITS
from db import connect, init_db, is_admin, top_users
from settings import init_settings
import achievements

OWNER = contextvars.ContextVar("menu_owner", default=None)
PROMO_WAIT = set()
PROMO_ADMIN = {}
CODES = {1:"soldier",2:"interceptor",3:"drone",4:"bmp",5:"tank",6:"helicopter",7:"plane",8:"missile",9:"artillery"}
CASE_LABELS = {"case1":"📦 Кейс 1", "case2":"📦 Кейс 2", "donate_case":"🎁 Донат-кейс"}
CASES = tuple(CASE_LABELS)
_ORIGINAL_KB = app.kb

def scoped_kb(rows):
    owner = OWNER.get()
    if not owner:
        return _ORIGINAL_KB(rows)
    scoped=[]
    for row in rows:
        new=[]
        for item in row:
            if isinstance(item,(tuple,list)) and len(item)==2:
                text,data=item; data=str(data)
                if not data.startswith(("accept:","decline:","g:")):
                    data=f"g:{owner}:{data}"
                new.append((text,data))
            else:new.append(item)
        scoped.append(new)
    return _ORIGINAL_KB(scoped)
app.kb = scoped_kb

def unit_codes_text():
    names={1:"🪖 Солдаты",2:"🎯 Перехватчики",3:"🛩 БПЛА",4:"🚙 БМП",5:"🛡 Танк",6:"🚁 Вертолёт",7:"✈️ Самолёт",8:"🚀 Ракета",9:"💥 Артиллерия"}
    return "КОДЫ ТЕХНИКИ:\n\n"+"\n".join(f"{i} — {n}" for i,n in names.items())+"\n\nВыдача:\n/givepehot @username КОД КОЛИЧЕСТВО\n\nПример:\n/givepehot @macrasoft 1 100"

async def admin_access(uid):
    return uid in OWNER_IDS or bool(await is_admin(uid, ADMIN_ID))

async def ensure_promo_schema():
    db=await connect()
    try:
        await db.execute("CREATE TABLE IF NOT EXISTS promo_uses(code TEXT NOT NULL,user_id INTEGER NOT NULL,PRIMARY KEY(code,user_id))")
        cols=await db.execute("PRAGMA table_info(promos)")
        existing={r[1] for r in await cols.fetchall()}
        if 'reward_type' not in existing: await db.execute('ALTER TABLE promos ADD COLUMN reward_type TEXT NOT NULL DEFAULT "money"')
        if 'reward_amount' not in existing: await db.execute('ALTER TABLE promos ADD COLUMN reward_amount INTEGER NOT NULL DEFAULT 0')
        await db.commit()
    finally: await db.close()

def promo_unit_name(unit): return UNITS[unit]['title'] if unit in UNITS else unit

def promo_admin_kb():
    return _ORIGINAL_KB([[('➕ Создать промокод','pa:create')],[('📋 Все промокоды','pa:list')],[('🗑 Удалить промокод','pa:delete')],[('⬅️ Назад','admin')]])

def promo_type_kb():
    return _ORIGINAL_KB([[('💰 Деньги','pa:type:money')],[('🎖 Техника','pa:type:unit')],[('📦 Кейсы','pa:type:case')],[('⬅️ Назад','a_promos')]])

def promo_units_kb():
    names={1:"🪖 Солдаты",2:"🎯 Перехватчики",3:"🛩 БПЛА",4:"🚙 БМП",5:"🛡 Танк",6:"🚁 Вертолёт",7:"✈️ Самолёт",8:"🚀 Ракета",9:"💥 Артиллерия"}
    rows=[[(f"{names[n]} — код {n}",f"pa:unit:{CODES[n]}")] for n in range(1,10)]
    rows.append([('⬅️ Назад','pa:create')])
    return _ORIGINAL_KB(rows)

def promo_cases_kb():
    return _ORIGINAL_KB([[(label,f"pa:case:{key}")] for key,label in CASE_LABELS.items()]+[[('⬅️ Назад','pa:create')]])

async def promo_admin_menu(c):
    if not await admin_access(c.from_user.id): return await c.answer('Нет доступа.',show_alert=True)
    await ensure_promo_schema()
    return await app.safe(c,'🎟 ПРОМОКОДЫ • АДМИН\n\nЗдесь промокоды создаются полностью через кнопки.\n\n🎖 Техника — единый список: солдаты, перехватчики и вся остальная техника.\n📦 Кейсы доступны как отдельная награда.',promo_admin_kb())

async def promo_create_start(c):
    if not await admin_access(c.from_user.id): return await c.answer('Нет доступа.',show_alert=True)
    PROMO_ADMIN[c.from_user.id]={'step':'code'}
    return await app.safe(c,'➕ СОЗДАНИЕ ПРОМОКОДА\n\nШаг 1/4\n\nВведите код промокода.\n\nРазрешены A-Z, a-z, 0-9, _ и -.\nПример: SUMMER2026',app.back('a_promos'))

async def promo_type(c):
    state=PROMO_ADMIN.get(c.from_user.id)
    if not state or 'code' not in state: return await promo_create_start(c)
    return await app.safe(c,f"🎟 Код: {state['code']}\n\nШаг 2/4\n\nВыберите тип награды:",promo_type_kb())

async def promo_finish_type(c,reward_type):
    state=PROMO_ADMIN.get(c.from_user.id)
    if not state:return await c.answer('Сессия создания истекла.',show_alert=True)
    state['reward_type']=reward_type
    if reward_type=='money':
        state['step']='amount'
        return await app.safe(c,f"🎟 Код: {state['code']}\n💰 Награда: Деньги\n\nШаг 3/4\n\nВведите сумму:",app.back('a_promos'))
    if reward_type=='unit':return await app.safe(c,f"🎟 Код: {state['code']}\n🎖 Награда: Техника\n\nВыберите единицу.\n\nСолдаты и перехватчики находятся здесь же, в общем списке техники:",promo_units_kb())
    return await app.safe(c,f"🎟 Код: {state['code']}\n📦 Награда: Кейс\n\nВыберите кейс:",promo_cases_kb())

async def promo_pick_reward(c,prefix,key):
    state=PROMO_ADMIN.get(c.from_user.id)
    if not state:return await c.answer('Сессия создания истекла.',show_alert=True)
    state['reward_type']=f'{prefix}:{key}';state['step']='amount'
    label=promo_unit_name(key) if prefix=='unit' else CASE_LABELS.get(key,key)
    return await app.safe(c,f"🎟 Код: {state['code']}\n🎁 Награда: {label}\n\nШаг 3/4\n\nВведите количество:",app.back('a_promos'))

def promo_reward_label(state):
    rt=state.get('reward_type','')
    if rt=='money':return '💰 Деньги'
    if rt.startswith('unit:'):return promo_unit_name(rt[5:])
    if rt.startswith('case:'):return CASE_LABELS.get(rt[5:],rt[5:])
    return rt

async def save_admin_promo(state):
    await ensure_promo_schema();db=await connect()
    try:
        code=state['code'];rt=state['reward_type'];amount=int(state['amount']);limit=int(state['limit'])
        await db.execute("INSERT INTO promos(code,amount,uses,max_uses,reward_type,reward_amount) VALUES(?,?,0,?,?,?)",(code,amount if rt=='money' else 0,limit,rt,amount));await db.commit()
    finally:await db.close()

async def promo_create_from_text(m,text):
    uid=m.from_user.id
    if not await admin_access(uid):return False
    state=PROMO_ADMIN.get(uid)
    if not state:return False
    step=state.get('step')
    if step=='code':
        code=text.strip()
        if not re.fullmatch(r'[A-Za-z0-9_-]{2,64}',code):await m.answer('❌ Неверный код. Используйте только A-Z, a-z, 0-9, _ и -.');return True
        await ensure_promo_schema();db=await connect()
        try:cur=await db.execute('SELECT 1 FROM promos WHERE lower(code)=lower(?)',(code,));exists=await cur.fetchone()
        finally:await db.close()
        if exists:await m.answer('❌ Такой промокод уже существует. Введите другой код.');return True
        state['code']=code;state['step']='type';await m.answer(f'🎟 Код: {code}\n\nШаг 2/4\n\nВыберите тип награды:',reply_markup=promo_type_kb());return True
    if step=='amount':
        try:amount=int(text.replace(' ','').replace(',',''))
        except ValueError:await m.answer('❌ Введите целое положительное число.');return True
        if amount<=0 or amount>10**12:await m.answer('❌ Количество должно быть больше 0.');return True
        state['amount']=amount;state['step']='limit';await m.answer(f"🎟 Код: {state['code']}\n🎁 Награда: {promo_reward_label(state)}\n📦 Количество: {amount}\n\nШаг 4/4\n\nВведите лимит активаций:");return True
    if step=='limit':
        try:limit=int(text.replace(' ','').replace(',',''))
        except ValueError:await m.answer('❌ Введите целое положительное число.');return True
        if limit<=0 or limit>10**9:await m.answer('❌ Лимит должен быть больше 0.');return True
        state['limit']=limit;await save_admin_promo(state);label=promo_reward_label(state);code=state['code'];amount=state['amount'];PROMO_ADMIN.pop(uid,None)
        await m.answer(f'✅ ПРОМОКОД СОЗДАН\n\n🎟 Код: {code}\n🎁 Награда: {label}\n🔢 Количество: {amount}\n👥 Лимит: {limit}',reply_markup=promo_admin_kb());return True
    return False

async def promo_list(c):
    if not await admin_access(c.from_user.id):return await c.answer('Нет доступа.',show_alert=True)
    await ensure_promo_schema();db=await connect()
    try:cur=await db.execute('SELECT code,amount,uses,max_uses,reward_type,reward_amount FROM promos ORDER BY rowid DESC LIMIT 100');rows=await cur.fetchall()
    finally:await db.close()
    if not rows:return await app.safe(c,'📋 ПРОМОКОДЫ\n\nПока промокодов нет.',promo_admin_kb())
    out=['📋 ПРОМОКОДЫ']
    for p in rows:
        rt=str(p['reward_type'] or 'money');amount=int(p['reward_amount'] or p['amount'] or 0)
        label=f'💰 Деньги × {amount}' if rt=='money' else (f'{promo_unit_name(rt[5:])} × {amount}' if rt.startswith('unit:') else (f'{CASE_LABELS.get(rt[5:],rt[5:])} × {amount}' if rt.startswith('case:') else f'{rt} × {amount}'))
        out.append(f'🎟 {p["code"]}\n   {label}\n   Использовано: {int(p["uses"])}/{int(p["max_uses"])}')
    return await app.safe(c,'\n\n'.join(out),promo_admin_kb())

async def promo_delete_menu(c):
    if not await admin_access(c.from_user.id):return await c.answer('Нет доступа.',show_alert=True)
    await ensure_promo_schema();db=await connect()
    try:cur=await db.execute('SELECT code FROM promos ORDER BY rowid DESC LIMIT 50');rows=await cur.fetchall()
    finally:await db.close()
    if not rows:return await app.safe(c,'🗑 УДАЛЕНИЕ ПРОМОКОДА\n\nПромокодов нет.',promo_admin_kb())
    kb_rows=[[(f'🗑 {r["code"]}',f'pa:del:{r["code"]}')] for r in rows];kb_rows.append([('⬅️ Назад','a_promos')])
    return await app.safe(c,'🗑 УДАЛЕНИЕ ПРОМОКОДА\n\nВыберите код:',_ORIGINAL_KB(kb_rows))

async def promo_delete(c,code):
    if not await admin_access(c.from_user.id):return await c.answer('Нет доступа.',show_alert=True)
    await ensure_promo_schema();db=await connect()
    try:await db.execute('DELETE FROM promo_uses WHERE code=?',(code,));cur=await db.execute('DELETE FROM promos WHERE code=?',(code,));await db.commit()
    finally:await db.close()
    if cur.rowcount!=1:return await c.answer('Промокод не найден.',show_alert=True)
    return await promo_delete_menu(c)

async def help_cmd(m):return await m.answer("ℹ️ ПОМОЩЬ\n\nхелп / help — помощь\nбонус / bonus — ежедневный бонус\nармия / а — армия\nшоп — магазин\nатака / вызовы — бой\nпромо — промокод\nачивки — достижения\nтоп — рейтинг")
async def bonus_keyword(m):return await m.answer("🎁 ЕЖЕДНЕВНЫЙ БОНУС\n\nНажмите кнопку ниже, чтобы открыть бонус.",reply_markup=scoped_kb([[('🎁 Открыть бонус','bonus')],[('⬅️ Назад','home')]]))
async def codes(m):
    if not await admin_access(m.from_user.id):return await m.answer("⛔ Нет доступа.")
    return await m.answer(unit_codes_text())
async def give(m,parts):
    if not await admin_access(m.from_user.id):return await m.answer("⛔ Нет доступа.")
    if len(parts)!=3:return await m.answer("❌ Формат:\n/givepehot @username КОД КОЛИЧЕСТВО\n\n"+unit_codes_text())
    target=await app.find_user(parts[0])
    try:code,amount=int(parts[1]),int(parts[2])
    except ValueError:return await m.answer("❌ Код и количество должны быть числами.")
    if not target or code not in CODES or amount<=0:return await m.answer("❌ Неверные данные.\n\n"+unit_codes_text())
    unit=CODES[code];db=await connect()
    try:await db.execute(f"UPDATE users SET {unit}={unit}+? WHERE user_id=?",(amount,target['user_id']));await db.commit()
    finally:await db.close()
    return await m.answer(f"✅ Выдано: {UNITS[unit]['title']} × {amount}\n\nКод: {code}")

async def addpromo(m,p):
    if not await admin_access(m.from_user.id):return await m.answer("⛔ Нет доступа.")
    if len(p)==3:code,amount_s,limit_s=p;reward_type='money';reward_amount=amount_s
    elif len(p)==5 and p[1].lower() in ('unit','tech','equipment'):
        code,_,unit,amount_s,limit_s=p;raw=unit.lower()
        try:n=int(raw);unit=CODES.get(n,'')
        except ValueError:unit=raw
        if unit not in UNITS:return await m.answer("❌ Неизвестная техника.\n\n"+unit_codes_text())
        reward_type='unit:'+unit;reward_amount=amount_s
    elif len(p)==5 and p[1].lower() in ('case','cases'):
        code,_,case,amount_s,limit_s=p;case=case.lower()
        if case not in CASES:return await m.answer("❌ Кейс: case1, case2, donate_case")
        reward_type='case:'+case;reward_amount=amount_s
    else:return await m.answer("Использование:\n/addpromo КОД СУММА ЛИМИТ\n/addpromo КОД unit ТЕХНИКА_ИЛИ_КОД КОЛИЧЕСТВО ЛИМИТ\n/addpromo КОД case КЕЙС КОЛИЧЕСТВО ЛИМИТ")
    try:amount,limit=int(reward_amount),int(limit_s)
    except ValueError:return await m.answer("❌ Количество и лимит должны быть числами.")
    if amount<=0 or limit<=0:return await m.answer("❌ Значения должны быть больше нуля.")
    await ensure_promo_schema();db=await connect()
    try:await db.execute("INSERT INTO promos(code,amount,uses,max_uses,reward_type,reward_amount) VALUES(?,?,0,?,?,?) ON CONFLICT(code) DO UPDATE SET amount=excluded.amount,max_uses=excluded.max_uses,reward_type=excluded.reward_type,reward_amount=excluded.reward_amount",(code,amount if reward_type=='money' else 0,limit,reward_type,amount));await db.commit()
    finally:await db.close()
    return await m.answer(f"✅ Промокод создан: {code}\n🎁 {reward_type} × {amount}\n👥 Лимит: {limit}")

async def usepromo(m,code):
    await ensure_promo_schema();db=await connect()
    try:
        cur=await db.execute("SELECT * FROM promos WHERE lower(code)=lower(?)",(code.strip(),));p=await cur.fetchone()
        if not p:return await m.answer("❌ Промокод не найден.")
        if int(p['uses'])>=int(p['max_uses']):return await m.answer("❌ Промокод больше недоступен.")
        cur=await db.execute("SELECT 1 FROM promo_uses WHERE code=? AND user_id=?",(p['code'],m.from_user.id))
        if await cur.fetchone():return await m.answer("❌ Вы уже использовали этот промокод.")
        rt=str(p['reward_type'] or 'money');amount=int(p['reward_amount'] or p['amount'] or 0)
        if rt=='money':await db.execute("UPDATE users SET balance=balance+? WHERE user_id=?",(amount,m.from_user.id));reward=f"💵 +${app.money(amount)}"
        elif rt.startswith('unit:'):
            unit=rt[5:]
            if unit not in UNITS:return await m.answer("❌ Неизвестная техника.")
            await db.execute(f"UPDATE users SET {unit}={unit}+? WHERE user_id=?",(amount,m.from_user.id));reward=f"{UNITS[unit]['title']} × {amount}"
        elif rt.startswith('case:'):
            case=rt[5:]
            if case not in CASES:return await m.answer("❌ Неизвестный кейс.")
            await db.execute("CREATE TABLE IF NOT EXISTS case_inventory(user_id INTEGER PRIMARY KEY,case1 INTEGER NOT NULL DEFAULT 0,case2 INTEGER NOT NULL DEFAULT 0,donate_case INTEGER NOT NULL DEFAULT 0)")
            vals={'case1':(amount,0,0),'case2':(0,amount,0),'donate_case':(0,0,amount)}[case]
            await db.execute("INSERT INTO case_inventory(user_id,case1,case2,donate_case) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET case1=case1+excluded.case1,case2=case2+excluded.case2,donate_case=donate_case+excluded.donate_case",(m.from_user.id,*vals));reward=f"📦 {CASE_LABELS[case]} × {amount}"
        else:return await m.answer("❌ Неизвестный тип награды.")
        await db.execute("UPDATE promos SET uses=uses+1 WHERE code=?",(p['code'],));await db.execute("INSERT INTO promo_uses(code,user_id) VALUES(?,?)",(p['code'],m.from_user.id));await db.commit()
    finally:await db.close()
    return await m.answer(f"🎉 Промокод активирован!\n\nНаграда: {reward}")

async def shop(c):
    rows=[[(f"{v['title']} — ${app.money(v['price'])}",f"buyq:{k}")] for k,v in UNITS.items()]
    rows.append([('⬅️ Назад','home')])
    return await app.safe(c,'🛒 АРСЕНАЛ\n\n'+'\n'.join(f"{v['title']} — ${app.money(v['price'])}" for v in UNITS.values()),scoped_kb(rows))
async def buyq(c,k):
    if k not in UNITS:return await c.answer('Недоступно',show_alert=True)
    app.STATE[c.from_user.id]=('buy',k);return await app.safe(c,f"🛒 {UNITS[k]['title']}\n\nЦена: ${app.money(UNITS[k]['price'])}\n\nВведите количество:",app.back('shop'))
async def top(c):
    rows=await top_users(50);out=[]
    for i,r in enumerate(rows,1):
        medal=('🥇','🥈','🥉')[i-1] if i<=3 else '🎖️';name='@'+r['username'] if r['username'] else f"ID {r['user_id']}";out.append(f"{medal} {i}. {name} — 🎖 {int(r['army_total'])}")
    return await app.safe(c,'🏆 ТОП ВОЯК\n\n'+('\n'.join(out) or 'Пока игроков нет.')+'\n\nРейтинг: солдат 1 | перехватчик 1 | БПЛА 3 | БМП 7 | артиллерия 8 | танк 10 | вертолёт 15 | самолёт 25 | ракета 50',app.back())

async def callback(c,bot:Bot):
    data=c.data or ''
    if c.message and c.message.chat.type!='private':
        if data.startswith('g:'):
            _,owner_s,real=data.split(':',2)
            try:owner=int(owner_s)
            except ValueError:owner=0
            if owner!=c.from_user.id and not real.startswith(('accept:','decline:')):return await c.answer('⛔ Это меню принадлежит другому пользователю.',show_alert=True)
            c.data=real;data=real
        elif not data.startswith(('accept:','decline:')):return await c.answer('⛔ Это меню нельзя использовать другому пользователю.',show_alert=True)
    if data=='a_promos':return await promo_admin_menu(c)
    if data=='pa:create':return await promo_create_start(c)
    if data=='pa:list':return await promo_list(c)
    if data=='pa:delete':return await promo_delete_menu(c)
    if data=='pa:type':return await promo_type(c)
    if data.startswith('pa:type:'):return await promo_finish_type(c,data[8:])
    if data.startswith('pa:unit:'):return await promo_pick_reward(c,'unit',data[8:])
    if data.startswith('pa:case:'):return await promo_pick_reward(c,'case',data[8:])
    if data.startswith('pa:del:'):return await promo_delete(c,data[7:])
    if data=='shop':return await shop(c)
    if data.startswith('buyq:'):return await buyq(c,data[5:])
    if data=='top':return await top(c)
    if data=='help':return await help_cmd(c.message)
    return await run.callback(c,bot)

def normalize_keyword(text):
    s=(text or '').strip().lower().replace('ё','е');s=re.sub(r'^/','',s);s=s.split('@',1)[0];s=re.sub(r'[.!?,;:]+$','',s);return s.strip()

async def text_handler(m,bot:Bot):
    text=(m.text or '').strip();key=normalize_keyword(text);p=text.split();cmd=('/'+key.split()[0]) if key else ''
    if await promo_create_from_text(m,text):return
    if key in ('хелп','help'):return await help_cmd(m)
    if key in ('бонус','bonus'):return await bonus_keyword(m)
    if key in ('коды','codes'):return await codes(m)
    if key.startswith('хелп ') or key.startswith('help '):return await help_cmd(m)
    if key.startswith('бонус ') or key.startswith('bonus '):return await bonus_keyword(m)
    if cmd in ('/коды','/codes'):return await codes(m)
    if cmd=='/givepehot':return await give(m,p[1:])
    if cmd=='/addpromo':return await addpromo(m,p[1:])
    if cmd in ('/promo','/промо','/промокод') and len(p)>1:return await usepromo(m,p[1])
    if key in ('промо','промокод','promo','/промо','/промокод','/promo'):
        PROMO_WAIT.add(m.from_user.id);return await m.answer('🎟 Введите промокод:')
    if m.from_user.id in PROMO_WAIT and not text.startswith('/'):
        PROMO_WAIT.discard(m.from_user.id);return await usepromo(m,text)
    return await run.text_handler(m,bot)

async def start(m):return await run.start_wrapper(m)

async def main():
    if not BOT_TOKEN:raise RuntimeError('BOT_TOKEN is empty')
    await init_db();await init_settings(ADMIN_ID);await ensure_promo_schema()
    db=await connect()
    try:await db.execute('INSERT OR IGNORE INTO admins(user_id) VALUES(?)',(ADMIN_ID,));await db.commit()
    finally:await db.close()
    await achievements.init_achievements()
    tg=Bot(BOT_TOKEN);dp=Dispatcher();dp.message.register(start,CommandStart());dp.message.register(text_handler,F.text);dp.callback_query.register(callback,F.data)
    print('OAM working launcher started');await dp.start_polling(tg)

if __name__=='__main__':asyncio.run(main())
