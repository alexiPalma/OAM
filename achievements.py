import bot as app
from db import connect, user
from config import UNITS
from aiogram import F

ACHIEVEMENTS=[
('recruit','🪖 Рекрут',(100,50,15,20,1,0,0,200),[('money',50000)]),
('soldier','🎖 Солдат',(200,75,20,30,2,0,0,300),[('money',100),('money',100000)]),
('senior_soldier','🎖 Старший солдат',(500,100,30,45,2,1,0,500),[('money',200),('case1',2)]),
('junior_sergeant','🎗 Младший сержант',(1100,150,70,100,5,2,0,1000),[('money',400),('soldier',50),('interceptor',5),('money',75000)]),
('sergeant','🎗 Сержант',(2000,400,130,300,8,3,0,1900),[('money',800),('money',100000),('drone',10),('tank',5),('soldier',100)]),
('senior_sergeant','🎗 Старший сержант',(5000,600,180,320,10,5,0,4000),[('money',200000),('helicopter',1),('interceptor',150)]),
('junior_lieutenant','⭐ Младший лейтенант',(10000,800,220,400,12,6,0,8500),[('money',500000),('helicopter',2),('tank',1),('bmp',3),('interceptor',100)]),
('lieutenant','⭐ Лейтенант',(15000,850,250,430,15,8,1,12000),[('plane',1),('drone',50)]),
('senior_lieutenant','⭐ Старший лейтенант',(22222,925,300,450,17,9,2,15000),[('plane',1),('helicopter',1),('tank',10),('soldier',5000)]),
('captain','⭐ Капитан',(30000,1025,350,500,19,10,3,18000),[('money',1000000),('soldier',5000),('drone',20),('bmp',30),('interceptor',400)]),
('major','⭐ Майор',(40000,1100,400,540,20,12,5,22000),[('money',1000000),('missile',2),('helicopter',1),('tank',1),('soldier',3000)]),
('lieutenant_colonel','⭐ Подполковник',(80000,1200,470,600,25,15,8,26000),[('missile',4),('soldier',15000),('interceptor',1000),('drone',350)]),
('colonel','🏅 Полковник',(300000,2000,700,1000,60,50,35,50000),[('donate_case',3),('case2',5),('missile',10),('plane',3),('helicopter',5),('soldier',25000),('legend_prefix',1)])]
REQ_KEYS=('soldier','drone','tank','bmp','helicopter','plane','missile','interceptor')
REQ_NAMES=('🪖 Солдаты','🛩 БПЛА','🛡 Танки','🚙 БМП','🚁 Вертолёты','✈️ Самолёты','🚀 Ракеты','🎯 Перехватчики')

async def init_achievements():
    db=await connect()
    await db.execute('CREATE TABLE IF NOT EXISTS achievements(user_id INTEGER,achievement_id TEXT,completed INTEGER NOT NULL DEFAULT 0,claimed INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(user_id,achievement_id))')
    await db.execute('CREATE TABLE IF NOT EXISTS achievement_inventory(user_id INTEGER PRIMARY KEY,case1 INTEGER NOT NULL DEFAULT 0,case2 INTEGER NOT NULL DEFAULT 0,donate_case INTEGER NOT NULL DEFAULT 0,legend_prefix INTEGER NOT NULL DEFAULT 0)')
    await db.commit();await db.close()

def reward_text(rewards):
    names={'soldier':'🪖 солдат','interceptor':'🎯 перехватчиков','drone':'🛩 БПЛА','bmp':'🚙 БМП','tank':'🛡 танк','helicopter':'🚁 вертолёт','plane':'✈️ самолёт','missile':'🚀 ракет','case1':'📦 кейс №1','case2':'📦 кейсов №2','donate_case':'⭐ донат-кейсов','legend_prefix':'👑 префикс «Легенда»'}
    return '\n'.join(f'${n:,}'.replace(',',' ') if t=='money' else f'{names.get(t,t)} × {n}' for t,n in rewards)

def met(row,req):return all(int(row[k])>=n for k,n in zip(REQ_KEYS,req))

async def check(uid,bot=None,notify=True):
    row=await user(uid)
    if not row:return []
    db=await connect();new=[]
    for aid,title,req,_ in ACHIEVEMENTS:
        cur=await db.execute('SELECT completed FROM achievements WHERE user_id=? AND achievement_id=?',(uid,aid));old=await cur.fetchone()
        if old and int(old['completed']):continue
        if met(row,req):
            await db.execute('INSERT INTO achievements(user_id,achievement_id,completed,claimed) VALUES(?,?,1,0) ON CONFLICT(user_id,achievement_id) DO UPDATE SET completed=1',(uid,aid));new.append(title)
    await db.commit();await db.close()
    if bot and notify:
        for title in new:
            try:await bot.send_message(uid,f'🏆 Вы выполнили ачивку «{title}»!\n\n🎁 Заберите вашу награду в разделе «Ачивки».')
            except Exception:pass
    return new

async def menu(c):
    await check(c.from_user.id,c.bot)
    db=await connect();cur=await db.execute('SELECT achievement_id,completed,claimed FROM achievements WHERE user_id=?',(c.from_user.id,));states={r['achievement_id']:(r['completed'],r['claimed']) for r in await cur.fetchall()};await db.close()
    rows=[]
    for aid,title,_,_ in ACHIEVEMENTS:
        done,claimed=states.get(aid,(0,0));mark='☑️' if claimed else ('✅' if done else '🔒');rows.append([(f'{mark} {title}',f'ach:{aid}')])
    rows.append([('⬅️ Назад','home')]);await app.safe(c,f'🏆 {app.BRAND} • АЧИВКИ\n\nНажмите на любую ачивку, чтобы посмотреть требования и награду.',app.kb(rows))

async def detail(c,aid):
    item=next((x for x in ACHIEVEMENTS if x[0]==aid),None)
    if not item:return await c.answer('Ачивка не найдена.',show_alert=True)
    _,title,req,rewards=item;await check(c.from_user.id,c.bot,False);db=await connect();cur=await db.execute('SELECT completed,claimed FROM achievements WHERE user_id=? AND achievement_id=?',(c.from_user.id,aid));s=await cur.fetchone();await db.close();row=await user(c.from_user.id);done=bool(s and s['completed']);claimed=bool(s and s['claimed'])
    reqtext='\n'.join(f'{REQ_NAMES[i]}: {int(row[k])}/{n}' for i,(k,n) in enumerate(zip(REQ_KEYS,req)) if n)
    rows=[]
    if done and not claimed:rows.append([('🎁 Забрать награду',f'ach_claim:{aid}')])
    rows.append([('⬅️ Назад','achievements')]);status='☑️ Награда получена' if claimed else ('✅ Выполнено' if done else '🔒 Не выполнено')
    await app.safe(c,f'🏆 {title}\n\n📋 Требования:\n{reqtext}\n\n🎁 Награда:\n{reward_text(rewards)}\n\nСтатус: {status}',app.kb(rows))

async def claim(c,aid):
    item=next((x for x in ACHIEVEMENTS if x[0]==aid),None)
    if not item:return await c.answer('Ачивка не найдена.',show_alert=True)
    _,title,_,rewards=item;await check(c.from_user.id,c.bot,False);db=await connect();cur=await db.execute('SELECT completed,claimed FROM achievements WHERE user_id=? AND achievement_id=?',(c.from_user.id,aid));s=await cur.fetchone()
    if not s or not s['completed']:await db.close();return await c.answer('Ачивка ещё не выполнена.',show_alert=True)
    if s['claimed']:await db.close();return await c.answer('Награда уже получена.',show_alert=True)
    sets=[];args=[];inv={'case1':0,'case2':0,'donate_case':0,'legend_prefix':0}
    for typ,n in rewards:
        if typ=='money':sets.append('balance=balance+?');args.append(n)
        elif typ in UNITS:sets.append(f'{typ}={typ}+?');args.append(n)
        elif typ in inv:inv[typ]+=n
    if sets:args.append(c.from_user.id);await db.execute(f'UPDATE users SET {",".join(sets)} WHERE user_id=?',args)
    await db.execute('INSERT INTO achievement_inventory(user_id,case1,case2,donate_case,legend_prefix) VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET case1=case1+excluded.case1,case2=case2+excluded.case2,donate_case=donate_case+excluded.donate_case,legend_prefix=legend_prefix+excluded.legend_prefix',(c.from_user.id,inv['case1'],inv['case2'],inv['donate_case'],inv['legend_prefix']))
    await db.execute('UPDATE achievements SET claimed=1 WHERE user_id=? AND achievement_id=?',(c.from_user.id,aid));await db.commit();await db.close();await app.safe(c,f'🎁 Награда за «{title}» получена!\n\n{reward_text(rewards)}',app.kb([[('⬅️ К ачивкам','achievements')]]))

def install_sync():
    if getattr(app,'_achievements_installed',False):return
    app._achievements_installed=True
    old_home=app.home_kb
    def home(a=False):
        m=old_home(a);rows=[list(r) for r in m.inline_keyboard];rows.insert(-1,[app.InlineKeyboardButton(text='🏆 Ачивки',callback_data='achievements')]);return app.InlineKeyboardMarkup(inline_keyboard=rows)
    app.home_kb=home
    # Register a dedicated handler instead of replacing the existing callback function object.
    router=getattr(app,'router',None)
    dp=getattr(app,'dp',None)
    target=router or dp
    if target is not None and hasattr(target,'callback_query'):
        async def achievement_callback(c):
            d=c.data or ''
            if d=='achievements':return await menu(c)
            if d.startswith('ach:'):return await detail(c,d.split(':',1)[1])
            if d.startswith('ach_claim:'):return await claim(c,d.split(':',1)[1])
        target.callback_query.register(achievement_callback,F.data.startswith('ach'))
    # Check after purchases and daily bonus.
    for name in ('buy_confirm','daily'):
        fn=getattr(app,name,None)
        if fn:
            async def wrapped(*args,_fn=fn,**kwargs):
                result=await _fn(*args,**kwargs)
                try:
                    c=args[0];await check(c.from_user.id,c.bot,True)
                except Exception:pass
                return result
            setattr(app,name,wrapped)
