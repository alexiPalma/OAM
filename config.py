import os
import sys
import importlib.abc
import importlib.machinery
from dotenv import load_dotenv
load_dotenv()
BOT_TOKEN=os.getenv('BOT_TOKEN','')
OWNER_ID=int(os.getenv('OWNER_ID') or os.getenv('ADMIN_ID') or '0')
OWNER_ID2=int(os.getenv('OWNER_ID2') or '0')
OWNER_IDS=tuple(x for x in (OWNER_ID, OWNER_ID2) if x)
ADMIN_ID=OWNER_ID
DB_PATH=os.getenv('DB_PATH','voennabot.db')
FARMS={0:{'income':0,'upgrade':500_000},1:{'income':15_000,'upgrade':500_000},2:{'income':36_000,'upgrade':900_000},3:{'income':50_000,'upgrade':1_000_000},4:{'income':50_000,'upgrade':2_000_000},5:{'income':100_000,'upgrade':3_000_000},6:{'income':140_000,'upgrade':6_000_000},7:{'income':220_000,'upgrade':9_000_000},8:{'income':333_000,'upgrade':11_000_000},9:{'income':777_000,'upgrade':18_000_000},10:{'income':899_000,'upgrade':30_000_000}}
UNITS={'soldier':{'id':1,'title':'🪖 Пехота','price':20_000,'loss':1_000,'rating':1},'interceptor':{'id':2,'title':'🎯 Дрон-перехватчик','price':4_000,'loss':4_000,'rating':1},'drone':{'id':3,'title':'🛩 БПЛА','price':120_000,'loss':20_000,'rating':3},'bmp':{'id':4,'title':'🚙 БМП','price':1_000_000,'loss':55_000,'rating':7},'artillery':{'id':9,'title':'💥 Артиллерия','price':2_500_000,'loss':250_000,'rating':8},'tank':{'id':5,'title':'🛡 Танк','price':3_000_000,'loss':100_000,'rating':10},'helicopter':{'id':6,'title':'🚁 Вертолёт','price':4_000_000,'loss':100_000,'rating':15},'plane':{'id':7,'title':'✈️ Самолёт','price':6_000_000,'loss':500_000,'rating':25},'missile':{'id':8,'title':'🚀 Ракета','price':20_000_000,'loss':1_000_000,'rating':50}}
UNIT_BY_ID={v['id']:k for k,v in UNITS.items()}
DONATIONS={50:5_000_000,100:11_000_000,500:100_000_000}
DAILY_BONUS_PRIZES=[(49.0,'money',100_000,'$100 000'),(20.0,'interceptor',10,'10 перехватчиков'),(10.0,'drone',2,'2 БПЛА'),(5.0,'bmp',1,'БМП'),(5.0,'drone',10,'10 БПЛА'),(4.9,'interceptor',50,'50 перехватчиков'),(2.5,'tank',1,'танк'),(2.5,'money',300_000,'$300 000'),(0.9,'case1',1,'📦 кейс №1'),(0.1,'case2',1,'📦 кейс №2')]

class _RunFixLoader(importlib.abc.Loader):
    def __init__(self,loader): self.loader=loader
    def create_module(self,spec):
        fn=getattr(self.loader,'create_module',None); return fn(spec) if fn else None
    def exec_module(self,module): self.loader.exec_module(module); _patch_run(module)
class _RunFixFinder(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path,target=None):
        if fullname!='run': return None
        spec=importlib.machinery.PathFinder.find_spec(fullname,path)
        if spec and spec.loader and not isinstance(spec.loader,_RunFixLoader): spec.loader=_RunFixLoader(spec.loader)
        return spec

def _patch_run(run):
    if getattr(run,'_wwd_final_fix',False): return
    run._wwd_final_fix=True
    import random
    from db import connect,top_users
    import bot as app
    async def fixed_top(c):
        rows=await top_users(50);out=[]
        for i,r in enumerate(rows,1):
            medal=['🥇','🥈','🥉'][i-1] if i<=3 else '🎖️';name='@'+r['username'] if r['username'] else f'ID {r["user_id"]}'
            out.append(f'{medal} {i}. {name} — 🎖 {int(r["army_total"]):,}'.replace(',',' '))
        return await app.safe(c,f'🏆 {app.BRAND} • ТОП ВОЯК\n\n'+'\n'.join(out),app.back())
    app.top=fixed_top
    async def fixed_shop(c):
        rows=[[(f'{v["title"]} — ${app.money(v["price"])}',f'buyq:{k}')] for k,v in UNITS.items()];rows.append([('⬅️ Назад','home')])
        text='🛒 '+app.BRAND+' • ВОЕННЫЙ АРСЕНАЛ\n\n'+'\n'.join(f'{v["title"]} — ${app.money(v["price"])}' for v in UNITS.values())+'\n\nВыберите единицу и введите количество.'
        return await app.safe(c,text,app.kb(rows))
    async def fixed_buyq(c,k):
        if k not in UNITS:return await c.answer('Недоступно',show_alert=True)
        app.STATE[c.from_user.id]=('buy',k);return await app.safe(c,f'🛒 {UNITS[k]["title"]}\n\nЦена: ${app.money(UNITS[k]["price"])}\n\nВведите количество:',app.back('shop'))
    async def fixed_buy_confirm(c,k,q):
        if k not in UNITS or q<1 or q>1_000_000:return await c.answer('Некорректное количество',show_alert=True)
        price=UNITS[k]['price']*q;db=await connect();cur=await db.execute(f'UPDATE users SET balance=balance-?,{k}={k}+? WHERE user_id=? AND balance>=?',(price,q,c.from_user.id,price));await db.commit();await db.close()
        if cur.rowcount!=1:return await app.safe(c,'❌ Недостаточно средств.',app.back('shop'))
        return await app.safe(c,f'✅ Покупка выполнена\n\n{UNITS[k]["title"]} × {q}\n💵 Списано: ${app.money(price)}',app.back('shop'))
    app.shop=fixed_shop;app.buyq=fixed_buyq;app.buy_confirm=fixed_buy_confirm
    async def fixed_daily(c):
        u=await app.user(c.from_user.id);today=app.now().date().isoformat()
        if u['daily_claim']==today:return await c.answer('Сегодня уже получено.',show_alert=True)
        r=random.uniform(0,100);acc=0;selected=None
        for prize in DAILY_BONUS_PRIZES:
            acc+=prize[0]
            if r<acc:selected=prize;break
        if selected is None:return await c.answer('Попробуйте ещё раз.',show_alert=True)
        _,kind,amount,label=selected;db=await connect()
        try:
            if kind in ('case1','case2','donate_case'):
                await db.execute('CREATE TABLE IF NOT EXISTS case_inventory(user_id INTEGER PRIMARY KEY,case1 INTEGER NOT NULL DEFAULT 0,case2 INTEGER NOT NULL DEFAULT 0,donate_case INTEGER NOT NULL DEFAULT 0)')
                await db.execute(f'INSERT INTO case_inventory(user_id,{kind}) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET {kind}={kind}+excluded.{kind}',(c.from_user.id,int(amount)))
            else:
                col='balance' if kind=='money' else kind
                await db.execute(f'UPDATE users SET {col}={col}+?,daily_claim=? WHERE user_id=?',(amount,today,c.from_user.id))
                await db.commit();return await app.safe(c,f'🎁 Вы получили: {label}.',app.back('bonus'))
            await db.execute('UPDATE users SET daily_claim=? WHERE user_id=?',(today,c.from_user.id));await db.commit()
        finally: await db.close()
        return await app.safe(c,f'🎁 Вы получили: {label}.',app.back('bonus'))
    app.daily=fixed_daily
    old_promo=run.use_promo_extended
    async def fixed_promo(message,code):
        db=await connect()
        try:
            cur=await db.execute('SELECT * FROM promos WHERE lower(code)=lower(?)',(code.strip(),));promo=await cur.fetchone()
            if not promo:return await message.answer('❌ Промокод не найден.')
            if int(promo['uses'])>=int(promo['max_uses']):return await message.answer('❌ Промокод больше недоступен.')
            cur=await db.execute('SELECT 1 FROM promo_uses WHERE code=? AND user_id=?',(promo['code'],message.from_user.id))
            if await cur.fetchone():return await message.answer('❌ Вы уже использовали этот промокод.')
            reward_type=str(promo['reward_type'] or 'money');amount=int(promo['reward_amount'] or promo['amount'] or 0)
            if reward_type.startswith('case:'):
                case=reward_type.split(':',1)[1]
                if case not in ('case1','case2','donate_case'):return await message.answer('❌ Некорректный кейс.')
                await db.execute('CREATE TABLE IF NOT EXISTS case_inventory(user_id INTEGER PRIMARY KEY,case1 INTEGER NOT NULL DEFAULT 0,case2 INTEGER NOT NULL DEFAULT 0,donate_case INTEGER NOT NULL DEFAULT 0)')
                await db.execute(f'INSERT INTO case_inventory(user_id,{case}) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET {case}={case}+excluded.{case}',(message.from_user.id,amount));reward_text=f'📦 {case} × {amount}'
            elif reward_type.startswith('unit:'):
                unit=reward_type.split(':',1)[1]
                if unit not in UNITS or amount<=0:return await message.answer('❌ Промокод содержит некорректную технику.')
                await db.execute(f'UPDATE users SET {unit}={unit}+? WHERE user_id=?',(amount,message.from_user.id));reward_text=f'{UNITS[unit]["title"]} × {amount}'
            else:
                await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(amount,message.from_user.id));reward_text=f'💵 +${app.money(amount)}'
            await db.execute('UPDATE promos SET uses=uses+1 WHERE code=?',(promo['code'],));await db.execute('INSERT INTO promo_uses(code,user_id) VALUES(?,?)',(promo['code'],message.from_user.id));await db.commit()
        finally: await db.close()
        return await message.answer(f'🎉 Промокод активирован!\n\nНаграда: {reward_text}')
    run.use_promo_extended=fixed_promo
    async def fixed_add_promo(message,parts):
        if not await run.admin_ok(message.from_user.id):return await message.answer('⛔ Нет доступа.')
        reward_type='money'
        if len(parts)==3:code,amount_s,max_s=parts
        elif len(parts)==4 and parts[1].lower()=='money':code,_,amount_s,max_s=parts
        elif len(parts)==5 and parts[1].lower() in ('unit','tech','equipment'):
            code,_,unit,amount_s,max_s=parts;unit=unit.lower()
            if unit not in UNITS:return await message.answer('❌ Неизвестная техника.')
            reward_type='unit:'+unit
        elif len(parts)==5 and parts[1].lower() in ('case','cases'):
            code,_,case,amount_s,max_s=parts;case=case.lower()
            if case not in ('case1','case2','donate_case'):return await message.answer('❌ Кейс: case1, case2 или donate_case.')
            reward_type='case:'+case
        else:return await message.answer('❌ Формат:\n/addpromo КОД СУММА ЛИМИТ\n/addpromo КОД unit ТЕХНИКА КОЛИЧЕСТВО ЛИМИТ\n/addpromo КОД case КЕЙС КОЛИЧЕСТВО ЛИМИТ')
        try:amount,max_uses=int(amount_s),int(max_s)
        except ValueError:return await message.answer('❌ Значения должны быть числами.')
        if amount<=0 or max_uses<=0:return await message.answer('❌ Значения должны быть больше нуля.')
        db=await connect()
        try:
            money_amount=amount if reward_type=='money' else 0
            await db.execute('''INSERT INTO promos(code,amount,uses,max_uses,reward_type,reward_amount) VALUES(?,?,0,?,?,?) ON CONFLICT(code) DO UPDATE SET amount=excluded.amount,max_uses=excluded.max_uses,reward_type=excluded.reward_type,reward_amount=excluded.reward_amount''',(code,money_amount,max_uses,reward_type,amount));await db.commit()
        finally:await db.close()
        label=f'${app.money(amount)}' if reward_type=='money' else reward_type.replace(':',' ')+' × '+str(amount)
        return await message.answer(f'✅ Промокод создан/обновлён.\n\n🎟 {code}\n🎁 {label}\n👥 Лимит: {max_uses}')
    run.add_promo=fixed_add_promo
    old_callback=run.callback
    async def fixed_callback(c,tg_bot):
        if c.data=='a_promos':return await app.safe(c,'🎟 ПРОМОКОДЫ\n\n/addpromo КОД СУММА ЛИМИТ\n/addpromo КОД unit ТЕХНИКА КОЛИЧЕСТВО ЛИМИТ\n/addpromo КОД case КЕЙС КОЛИЧЕСТВО ЛИМИТ\n\nКейсы: case1, case2, donate_case',app.back('admin'))
        return await old_callback(c,tg_bot)
    run.callback=fixed_callback

if not any(isinstance(x,_RunFixFinder) for x in sys.meta_path):sys.meta_path.insert(0,_RunFixFinder())
