"""Permanent WorldWarDynasty runtime fixes.
Loaded automatically by Python before run.py/bot.py.
"""
import contextvars
import os
import random
import sys
from collections import OrderedDict

try:
    import config
    order = [('soldier', 1), ('interceptor', 1), ('drone', 3), ('bmp', 7), ('artillery', 8), ('tank', 10), ('helicopter', 15), ('plane', 25), ('missile', 50)]
    units = OrderedDict()
    for key, rating in order:
        item = dict(config.UNITS[key])
        item['rating'] = rating
        if key == 'artillery':
            item['price'] = 2_500_000
        units[key] = item
    config.UNITS = dict(units)
    config.UNIT_BY_ID = {v['id']: k for k, v in config.UNITS.items()}
except Exception:
    pass

CTX = contextvars.ContextVar('wwd_context', default=None)

def unwrap_owner(data):
    text = str(data or '')
    marker = '|wwdu:'
    if marker not in text:
        return text, None
    base, raw = text.rsplit(marker, 1)
    try:
        return base, int(raw)
    except ValueError:
        return base, None

try:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    _button_init = InlineKeyboardButton.__init__
    if not getattr(InlineKeyboardButton, '_wwd_owner_patch', False):
        def owner_button_init(self, *args, **kwargs):
            _button_init(self, *args, **kwargs)
            ctx = CTX.get()
            if not ctx or ctx.get('chat_type') not in ('group', 'supergroup'):
                return
            data = getattr(self, 'callback_data', None)
            if data and '|wwdu:' not in str(data):
                tagged = f'{data}|wwdu:{ctx["uid"]}'
                if len(tagged.encode('utf-8')) <= 64:
                    self.callback_data = tagged
        InlineKeyboardButton.__init__ = owner_button_init
        InlineKeyboardButton._wwd_owner_patch = True
except Exception:
    pass

try:
    from aiogram.dispatcher.dispatcher import Dispatcher
    _feed_update = Dispatcher.feed_update
    if not getattr(Dispatcher, '_wwd_owner_patch', False):
        async def feed_update_owned(self, bot, update, **kwargs):
            event = None
            for name in ('message', 'callback_query', 'edited_message', 'channel_post'):
                obj = getattr(update, name, None)
                if obj is not None:
                    event = obj
                    break
            frm = getattr(event, 'from_user', None) if event else None
            chat = getattr(event, 'chat', None) if event else None
            ctx = {'uid': getattr(frm, 'id', None), 'chat_type': getattr(chat, 'type', None)}
            if getattr(event, 'data', None) is not None and ctx['chat_type'] in ('group', 'supergroup'):
                data, owner = unwrap_owner(event.data)
                if owner is None or owner != ctx['uid']:
                    try:
                        await event.answer('🔒 Это меню принадлежит другому пользователю.', show_alert=True)
                    except Exception:
                        pass
                    return None
                event.data = data
            token = CTX.set(ctx)
            try:
                return await _feed_update(self, bot, update, **kwargs)
            finally:
                CTX.reset(token)
        Dispatcher.feed_update = feed_update_owned
        Dispatcher._wwd_owner_patch = True
except Exception:
    pass

try:
    import bot as app
    from db import connect, user
    from config import FARMS, UNITS, DAILY_BONUS_PRIZES
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    def fixed_kb(rows):
        keyboard = []
        for row in rows:
            buttons = []
            for text, value in row:
                value = str(value)
                if value.startswith(('https://', 'http://', 'tg://')):
                    buttons.append(InlineKeyboardButton(text=str(text), url=value))
                else:
                    buttons.append(InlineKeyboardButton(text=str(text), callback_data=value))
            keyboard.append(buttons)
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    app.kb = fixed_kb

    async def fixed_tpl(key, default, **kw):
        raw = await app.setting('msg_' + key, default)
        if isinstance(raw, str):
            raw = raw.replace('\\r\\n', '\n').replace('\\n', '\n')
        try:
            return app.clean(raw).format(**kw)
        except Exception:
            fallback = default
            if isinstance(fallback, str):
                fallback = fallback.replace('\\r\\n', '\n').replace('\\n', '\n')
            return app.clean(fallback)
    app.tpl = fixed_tpl

    import db as _db
    async def fixed_top_users(limit=50):
        db = await connect()
        weights = {'soldier':1,'interceptor':1,'drone':3,'bmp':7,'artillery':8,'tank':10,'helicopter':15,'plane':25,'missile':50}
        expr = ' + '.join(f'COALESCE({k},0)*{v}' for k,v in weights.items())
        cur = await db.execute(f'SELECT *, ({expr}) AS army_total FROM users ORDER BY army_total DESC, attacks_won DESC, user_id ASC LIMIT ?', (max(1,min(50,int(limit))),))
        rows = await cur.fetchall()
        await db.close()
        return rows
    _db.top_users = fixed_top_users

    async def fixed_top(c):
        rows = await fixed_top_users(50)
        out=[]
        for i,row in enumerate(rows,1):
            medal=['🥇','🥈','🥉'][i-1] if i<=3 else '🎖️'
            name='@'+row['username'] if row['username'] else f'ID {row["user_id"]}'
            equipment=[]
            for key,unit in UNITS.items():
                count=int(row[key])
                if count: equipment.append(f'{unit["title"]} × {count}')
            out.append(f'{medal} {i}. {app.esc(name)} — 🏆 {int(row["army_total"])} рейтинга\n   {", ".join(equipment) if equipment else "нет техники"}')
        listing='\n'.join(out) or 'Пока игроков нет.'
        text=await app.tpl('top',f'🏆 {app.BRAND} • ТОП ВОЯК\n\n{listing}',top=listing,position='—')
        return await app.safe(c,text,app.back())
    app.top=fixed_top

    async def fixed_farm(c):
        row=await user(c.from_user.id); level=int(row['farm_level']); farm_data=FARMS[level]; tax=app.money(row['tax']); status='🟢 АКТИВНА' if level>0 else '⚪ НЕ РАЗВЁРНУТА'
        text=await app.tpl('farm',f'🏭 {app.BRAND} • ФЕРМА\n\nУровень: {level}/10\nПроизводство: ${app.money(farm_data["income"])}/час\n💸 Накоплено налога: ${tax}\nСтавка налога: 25%\nСтатус: {status}',level=level,income=app.money(farm_data['income']),tax=tax,status=status)
        return await app.safe(c,text,app.kb([[('💰 Получить','payout'),('⬆️ Улучшить','upgrade')],[('💸 Оплатить налог','paytax')],[('⬅️ Назад','home')]]))
    app.farm=fixed_farm

    _old_text_handler=app.text_handler
    if not getattr(_old_text_handler,'_wwd_keyword_patch',False):
        async def text_handler_keywords(m,bot,*args,**kwargs):
            low=(m.text or '').strip().lower()
            if low in ('help','хелп','/help','/хелп'):
                return await m.answer(f'ℹ️ {app.BRAND} • ПОМОЩЬ\n\nРазвивайте ферму, покупайте армию и участвуйте в боях.',reply_markup=app.back())
            if low in ('bonus','бонус','/bonus','/бонус'):
                prizes='\n'.join(f'{p:g}% — {label}' for p,_,_,label in DAILY_BONUS_PRIZES)
                return await m.answer(f'🎁 {app.BRAND} • ЕЖЕДНЕВНЫЙ БОНУС\n\n{prizes}',reply_markup=app.kb([[('🎁 Забрать','daily')],[('⬅️ Назад','home')]]))
            return await _old_text_handler(m,bot,*args,**kwargs)
        text_handler_keywords._wwd_keyword_patch=True
        app.text_handler=text_handler_keywords

    try:
        import achievements
        achievements.REQ_KEYS=tuple(f'kill_{k}' for k in ('soldier','drone','tank','bmp','helicopter','plane','missile','interceptor'))
        achievements.REQ_NAMES=('💀 Уничтожено солдат','💀 Уничтожено БПЛА','💀 Уничтожено танков','💀 Уничтожено БМП','💀 Уничтожено вертолётов','💀 Уничтожено самолётов','💀 Уничтожено ракет','💀 Уничтожено перехватчиков')
    except Exception:
        pass

    try:
        import combat
        _old_resolve=combat.resolve
        if not getattr(combat,'_wwd_artillery_patch',False):
            def artillery_phase(attacker,defender,kills):
                d=dict(defender)
                for _ in range(int(attacker.get('artillery',0))):
                    if d.get('artillery',0) and random.random()<0.50:
                        d['artillery']-=1; kills['artillery']+=1
                    if d.get('soldier',0):
                        n=min(30,int(d['soldier'])); d['soldier']-=n; kills['soldier']+=n
                    if d.get('bmp',0):
                        n=min(2,int(d['bmp'])); d['bmp']-=n; kills['bmp']+=n
                    if d.get('tank',0) and random.random()<0.65:
                        d['tank']-=1; kills['tank']+=1
                return d
            def resolve_with_artillery(attacker,defender,with_kills=False):
                a={k:int(attacker[k]) for k in UNITS}; d={k:int(defender[k]) for k in UNITS}; ka={k:0 for k in UNITS}; kd={k:0 for k in UNITS}
                d_after=artillery_phase(a,d,ka); a_after=artillery_phase(d,a,kd)
                a_no=dict(a_after); d_no=dict(d_after); a_no['artillery']=0; d_no['artillery']=0
                aa,dd,winner,events,old_ka,old_kd=_old_resolve(a_no,d_no,True)
                for key in UNITS:
                    ka[key]+=old_ka.get(key,0); kd[key]+=old_kd.get(key,0)
                aa['artillery']=max(0,int(a['artillery'])-kd.get('artillery',0)); dd['artillery']=max(0,int(d['artillery'])-ka.get('artillery',0))
                if with_kills: return aa,dd,winner,events,ka,kd
                return aa,dd,winner,events
            combat.resolve=resolve_with_artillery; combat._wwd_artillery_patch=True
    except Exception:
        pass

    def patch_run_main(frame):
        g=frame.f_globals
        if g.get('__name__')!='__main__' or not str(g.get('__file__','')).lower().endswith('run.py'): return False
        home=g.get('home_kb')
        if home is not None and not getattr(home,'_wwd_ach_patch',False):
            def home_with_achievements(is_admin_user=False):
                markup=home(is_admin_user); rows=[list(row) for row in markup.inline_keyboard]
                if not any(b.callback_data=='achievements' for row in rows for b in row): rows.insert(max(0,len(rows)-(1 if is_admin_user else 0)),[InlineKeyboardButton(text='🏆 Ачивки',callback_data='achievements')])
                return InlineKeyboardMarkup(inline_keyboard=rows)
            home_with_achievements._wwd_ach_patch=True; g['home_kb']=home_with_achievements

        if all(name in g for name in ('add_promo','use_promo_extended','cases','case')) and not g.get('_wwd_cases_patched'):
            g['_wwd_cases_patched']=True; old_add=g['add_promo']; old_use=g['use_promo_extended']; old_case=g['case']
            async def ensure_case_table():
                db=await connect(); await db.execute('CREATE TABLE IF NOT EXISTS promo_case_inventory(user_id INTEGER PRIMARY KEY,case1 INTEGER NOT NULL DEFAULT 0,case2 INTEGER NOT NULL DEFAULT 0,president INTEGER NOT NULL DEFAULT 0)'); await db.commit(); await db.close()
            async def add_promo(message,parts):
                if len(parts)==5 and parts[1].lower() in ('case','кейс'):
                    if not await g['admin_ok'](message.from_user.id): return await message.answer('⛔ Нет доступа.')
                    code,_,case_id,amount_s,max_s=parts; aliases={'1':'case1','case1':'case1','2':'case2','case2':'case2','3':'president','president':'president'}; case_id=aliases.get(case_id.lower())
                    if not case_id or not amount_s.isdigit() or not max_s.isdigit() or int(amount_s)<=0 or int(max_s)<=0: return await message.answer('❌ Формат: /addpromo КОД case case1 КОЛИЧЕСТВО ЛИМИТ')
                    await ensure_case_table(); db=await connect(); await db.execute('''INSERT INTO promos(code,amount,uses,max_uses,reward_type,reward_amount) VALUES(?,0,0,?,?,?) ON CONFLICT(code) DO UPDATE SET amount=0,max_uses=excluded.max_uses,reward_type=excluded.reward_type,reward_amount=excluded.reward_amount''',(code,int(max_s),'case:'+case_id,int(amount_s))); await db.commit(); await db.close(); return await message.answer(f'✅ Промокод создан.\n📦 {case_id} × {amount_s}\n👥 Лимит: {max_s}')
                return await old_add(message,parts)
            async def use_promo_extended(message,code):
                db=await connect(); cur=await db.execute('SELECT * FROM promos WHERE lower(code)=lower(?)',(code.strip(),)); promo=await cur.fetchone(); await db.close()
                if not promo or not str(promo['reward_type'] or '').startswith('case:'): return await old_use(message,code)
                if int(promo['uses'])>=int(promo['max_uses']): return await message.answer('❌ Промокод больше недоступен.')
                db=await connect(); cur=await db.execute('SELECT 1 FROM promo_uses WHERE code=? AND user_id=?',(promo['code'],message.from_user.id))
                if await cur.fetchone(): await db.close(); return await message.answer('❌ Вы уже использовали этот промокод.')
                await db.execute('CREATE TABLE IF NOT EXISTS promo_case_inventory(user_id INTEGER PRIMARY KEY,case1 INTEGER NOT NULL DEFAULT 0,case2 INTEGER NOT NULL DEFAULT 0,president INTEGER NOT NULL DEFAULT 0)'); case_id=str(promo['reward_type']).split(':',1)[1]; amount=int(promo['reward_amount'] or 1)
                await db.execute('INSERT OR IGNORE INTO promo_case_inventory(user_id) VALUES(?)',(message.from_user.id,)); await db.execute(f'UPDATE promo_case_inventory SET {case_id}={case_id}+? WHERE user_id=?',(amount,message.from_user.id)); await db.execute('UPDATE promos SET uses=uses+1 WHERE code=?',(promo['code'],)); await db.execute('INSERT INTO promo_uses(code,user_id) VALUES(?,?)',(promo['code'],message.from_user.id)); await db.commit(); await db.close(); return await message.answer(f'🎉 Промокод активирован!\n\n📦 {case_id} × {amount}')
            async def case(c,cid):
                if cid not in ('case1','case2','president'): return await old_case(c,cid)
                await ensure_case_table(); db=await connect(); cur=await db.execute(f'UPDATE promo_case_inventory SET {cid}={cid}-1 WHERE user_id=? AND {cid}>0',(c.from_user.id,)); await db.commit(); await db.close()
                if cur.rowcount!=1: return await old_case(c,cid)
                pools={'case1':[('soldier',2,75),('interceptor',11,15),('soldier',10,10)],'case2':[('bmp',1,80),('tank',1,10),('helicopter',1,7.5),('plane',1,2.5)],'president':[('helicopter',1,90),('plane',1,8),('missile',1,2)]}
                r=random.uniform(0,100); acc=0
                for unit,amount,chance in pools[cid]:
                    acc+=chance
                    if r<acc: break
                db=await connect(); await db.execute(f'UPDATE users SET {unit}={unit}+? WHERE user_id=?',(amount,c.from_user.id)); await db.commit(); await db.close(); return await g['app'].safe(c,f'📦 Бесплатный кейс открыт!\n\n{UNITS[unit]["title"]} × {amount}\n🎲 Шанс: {chance}%',g['app'].back('cases'))
            g['add_promo']=add_promo; g['use_promo_extended']=use_promo_extended; g['case']=case
        return True

    def trace(frame,event,arg):
        if event in ('line','return'):
            try:
                if patch_run_main(frame) and frame.f_globals.get('_wwd_cases_patched'):
                    sys.settrace(None); return None
            except Exception:
                pass
        return trace
    sys.settrace(trace)

    try:
        import shop_runtime_patch
        shop_runtime_patch.install()
    except Exception:
        pass
except Exception:
    pass
