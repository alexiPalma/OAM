"""WorldWarDynasty runtime fixes.

This module is auto-loaded by Python when the project directory is on sys.path.
It also patches the real imported modules, so run.py and bot.py use the same fixes.
"""
import contextvars
import random
import sys
from collections import OrderedDict

CTX = contextvars.ContextVar('wwd_context', default=None)

# ---------------------------------------------------------------------------
# Group menu ownership: a callback from another user is rejected.
# ---------------------------------------------------------------------------
try:
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    from aiogram.dispatcher.dispatcher import Dispatcher

    _old_button_init = InlineKeyboardButton.__init__
    if not getattr(InlineKeyboardButton, '_wwd_owner_patch', False):
        def _owner_button_init(self, *args, **kwargs):
            _old_button_init(self, *args, **kwargs)
            ctx = CTX.get()
            if not ctx or ctx.get('chat_type') not in ('group', 'supergroup'):
                return
            data = getattr(self, 'callback_data', None)
            uid = ctx.get('uid')
            if data and uid and '|wwdu:' not in str(data):
                tagged = f'{data}|wwdu:{uid}'
                if len(tagged.encode('utf-8')) <= 64:
                    self.callback_data = tagged
        InlineKeyboardButton.__init__ = _owner_button_init
        InlineKeyboardButton._wwd_owner_patch = True

    _old_feed_update = Dispatcher.feed_update
    if not getattr(Dispatcher, '_wwd_owner_patch', False):
        async def _owned_feed_update(self, bot, update, **kwargs):
            event = None
            for name in ('callback_query', 'message', 'edited_message', 'channel_post'):
                event = getattr(update, name, None)
                if event is not None:
                    break
            frm = getattr(event, 'from_user', None) if event else None
            chat = getattr(event, 'chat', None) if event else None
            uid = getattr(frm, 'id', None)
            chat_type = getattr(chat, 'type', None)
            data = getattr(event, 'data', None)
            if data is not None and chat_type in ('group', 'supergroup'):
                marker = '|wwdu:'
                if marker not in str(data):
                    try:
                        await event.answer('🔒 Это меню принадлежит другому пользователю.', show_alert=True)
                    except Exception:
                        pass
                    return None
                base, raw_owner = str(data).rsplit(marker, 1)
                try:
                    owner = int(raw_owner)
                except ValueError:
                    owner = -1
                if owner != uid:
                    try:
                        await event.answer('🔒 Это меню принадлежит другому пользователю.', show_alert=True)
                    except Exception:
                        pass
                    return None
                event.data = base
            token = CTX.set({'uid': uid, 'chat_type': chat_type})
            try:
                return await _old_feed_update(self, bot, update, **kwargs)
            finally:
                CTX.reset(token)
        Dispatcher.feed_update = _owned_feed_update
        Dispatcher._wwd_owner_patch = True
except Exception:
    pass

# ---------------------------------------------------------------------------
# Actual application fixes.
# ---------------------------------------------------------------------------
try:
    import config
    order = [
        ('soldier', 1), ('interceptor', 1), ('drone', 3), ('bmp', 7),
        ('artillery', 8), ('tank', 10), ('helicopter', 15),
        ('plane', 25), ('missile', 50),
    ]
    units = OrderedDict()
    for key, rating in order:
        item = dict(config.UNITS[key])
        item['rating'] = rating
        if key == 'artillery':
            item['price'] = 2_500_000
        units[key] = item
    config.UNITS = dict(units)
    config.UNIT_BY_ID = {v['id']: k for k, v in config.UNITS.items()}

    import db
    import bot as app
    from db import connect, user
    from config import FARMS, UNITS, DAILY_BONUS_PRIZES

    def fixed_kb(rows):
        keyboard = []
        for row in rows:
            buttons = []
            for item in row:
                text, value = item
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
            fallback = default if isinstance(default, str) else str(default)
            fallback = fallback.replace('\\r\\n', '\n').replace('\\n', '\n')
            return app.clean(fallback)
    app.tpl = fixed_tpl

    RATING = {'soldier':1,'interceptor':1,'drone':3,'bmp':7,'artillery':8,'tank':10,'helicopter':15,'plane':25,'missile':50}
    async def fixed_top_users(limit=50):
        conn = await connect()
        expr = ' + '.join(f'COALESCE({k},0)*{w}' for k,w in RATING.items())
        cur = await conn.execute(
            f'SELECT user_id,username,balance,farm_level,{expr} AS army_total FROM users '
            'ORDER BY army_total DESC, attacks_won DESC, user_id ASC LIMIT ?',
            (max(1, min(50, int(limit))),),
        )
        rows = await cur.fetchall()
        await conn.close()
        return rows
    db.top_users = fixed_top_users

    async def fixed_top(c):
        rows = await fixed_top_users(50)
        out = []
        for i, row in enumerate(rows, 1):
            medal = ['🥇','🥈','🥉'][i-1] if i <= 3 else '🎖️'
            name = '@' + row['username'] if row['username'] else f'ID {row["user_id"]}'
            equipment = []
            for key, unit in UNITS.items():
                count = int(row[key])
                if count:
                    equipment.append(f'{unit["title"]} × {count}')
            out.append(
                f'{medal} {i}. {app.esc(name)} — 🏆 {int(row["army_total"])} рейтинга\n'
                f'   {", ".join(equipment) if equipment else "нет техники"}'
            )
        listing = '\n'.join(out) or 'Пока игроков нет.'
        text = await app.tpl('top', f'🏆 {app.BRAND} • ТОП ВОЯК\n\n{listing}', top=listing, position='—')
        return await app.safe(c, text, app.back())
    app.top = fixed_top

    async def fixed_farm(c):
        row = await user(c.from_user.id)
        level = int(row['farm_level'])
        f = FARMS[level]
        tax = app.money(row['tax'])
        status = '🟢 АКТИВНА' if level > 0 else '⚪ НЕ РАЗВЁРНУТА'
        text = await app.tpl(
            'farm',
            f'🏭 {app.BRAND} • ФЕРМА\n\nУровень: {level}/10\n'
            f'Производство: ${app.money(f["income"])}/час\n'
            f'💸 Накоплено налога: ${tax}\nСтавка налога: 25%\nСтатус: {status}',
            level=level, income=app.money(f['income']), tax=tax, status=status,
        )
        return await app.safe(c, text, app.kb([
            [('💰 Получить','payout'),('⬆️ Улучшить','upgrade')],
            [('💸 Оплатить налог','paytax')],
            [('⬅️ Назад','home')],
        ]))
    app.farm = fixed_farm

    # Artillery must be usable, not merely present in config.
    async def fixed_shop(c):
        items = '\n'.join(f'{v["title"]} — ${app.money(v["price"])}' for v in UNITS.values())
        rows = [[(f'{v["title"]} — ${app.money(v["price"])}', f'buyq:{k}')] for k,v in UNITS.items()]
        rows.append([('⬅️ Назад','home')])
        return await app.safe(c, f'🛒 {app.BRAND} • ВОЕННЫЙ АРСЕНАЛ\n\n{items}\n\nВыберите единицу и введите количество.', app.kb(rows))
    app.shop = fixed_shop

    async def fixed_shop_message(m):
        items = '\n'.join(f'{v["title"]} — ${app.money(v["price"])}' for v in UNITS.values())
        rows = [[(f'{v["title"]} — ${app.money(v["price"])}', f'buyq:{k}')] for k,v in UNITS.items()]
        rows.append([('⬅️ Назад','home')])
        return await m.answer(f'🛒 {app.BRAND} • ВОЕННЫЙ АРСЕНАЛ\n\n{items}\n\nВыберите единицу.', reply_markup=app.kb(rows))
    app.shop_from_message = fixed_shop_message

    async def fixed_buyq(c, key):
        if key not in UNITS:
            return await c.answer('Недоступно', show_alert=True)
        app.STATE[c.from_user.id] = ('buy', key)
        return await app.safe(c, f'🛒 {UNITS[key]["title"]}\n\nЦена: ${app.money(UNITS[key]["price"])}\n\nВведите количество:', app.back('shop'))
    app.buyq = fixed_buyq

    # Existing achievement thresholds stay intact; only the measured statistic
    # changes from owned equipment to destroyed equipment.
    try:
        import achievements
        achievements.REQ_KEYS = tuple('kill_' + k for k in ('soldier','drone','tank','bmp','helicopter','plane','missile','interceptor'))
        achievements.REQ_NAMES = ('💀 Уничтожено солдат','💀 Уничтожено БПЛА','💀 Уничтожено танков','💀 Уничтожено БМП','💀 Уничтожено вертолётов','💀 Уничтожено самолётов','💀 Уничтожено ракет','💀 Уничтожено перехватчиков')
    except Exception:
        pass

    # bot.py imported resolve directly, so patch both combat.resolve and app.resolve.
    try:
        import combat
        old_resolve = combat.resolve
        if not getattr(combat, '_wwd_artillery_patch', False):
            def artillery_phase(attacker, defender, events, label, kills):
                d = dict(defender)
                for _ in range(int(attacker.get('artillery', 0))):
                    if d.get('artillery', 0) and random.random() < 0.50:
                        killed = min(1, int(d['artillery']))
                        d['artillery'] -= killed; kills['artillery'] += killed
                        events.append(f'{label} 💥 артиллерия контрит артиллерию — 50%')
                    if d.get('soldier', 0):
                        killed = min(30, int(d['soldier']))
                        d['soldier'] -= killed; kills['soldier'] += killed
                        events.append(f'{label} 💥 артиллерия уничтожила до 30 пехоты')
                    if d.get('bmp', 0):
                        killed = min(2, int(d['bmp']))
                        d['bmp'] -= killed; kills['bmp'] += killed
                        events.append(f'{label} 💥 артиллерия уничтожила до 2 БМП')
                    if d.get('tank', 0) and random.random() < 0.65:
                        d['tank'] -= 1; kills['tank'] += 1
                        events.append(f'{label} 💥 артиллерия уничтожила танк — 65%')
                return d

            def resolve_artillery(attacker, defender, with_kills=False):
                a = {k:int(attacker[k]) for k in UNITS}
                d = {k:int(defender[k]) for k in UNITS}
                ka = {k:0 for k in UNITS}; kd = {k:0 for k in UNITS}
                d_after = artillery_phase(a, d, [], '🔴', ka)
                a_after = artillery_phase(d, a, [], '🔵', kd)
                a_no = dict(a_after); d_no = dict(d_after)
                a_no['artillery'] = 0; d_no['artillery'] = 0
                aa, dd, winner, events, old_ka, old_kd = old_resolve(a_no, d_no, True)
                ka.update({k: ka.get(k,0)+old_ka.get(k,0) for k in UNITS})
                kd.update({k: kd.get(k,0)+old_kd.get(k,0) for k in UNITS})
                aa['artillery'] = int(a_after.get('artillery',0))
                dd['artillery'] = int(d_after.get('artillery',0))
                if with_kills:
                    return aa, dd, winner, events, ka, kd
                return aa, dd, winner, events
            combat.resolve = resolve_artillery
            app.resolve = resolve_artillery
            combat._wwd_artillery_patch = True
    except Exception:
        pass

    # Keywords requested for both command and ordinary text input.
    old_text_handler = app.text_handler
    if not getattr(old_text_handler, '_wwd_keyword_patch', False):
        async def keyword_handler(m, bot, *args, **kwargs):
            low = (m.text or '').strip().lower()
            if low in ('help','хелп','/help','/хелп'):
                return await m.answer(f'ℹ️ {app.BRAND} • ПОМОЩЬ\n\nРазвивайте ферму, покупайте армию и участвуйте в боях.', reply_markup=app.back())
            if low in ('bonus','бонус','/bonus','/бонус'):
                prizes = '\n'.join(f'{p:g}% — {label}' for p,_,_,label in DAILY_BONUS_PRIZES)
                return await m.answer(f'🎁 {app.BRAND} • ЕЖЕДНЕВНЫЙ БОНУС\n\n{prizes}', reply_markup=app.kb([[('🎁 Забрать','daily')],[('⬅️ Назад','home')]]))
            return await old_text_handler(m, bot, *args, **kwargs)
        keyword_handler._wwd_keyword_patch = True
        app.text_handler = keyword_handler

except Exception as exc:
    # Never prevent the bot from starting because an optional runtime patch failed.
    print(f'[WorldWarDynasty] runtime patch warning: {exc}')

# The repository already contains the artillery-shop helper. Re-run it after the
# direct patch above so older deployments get the same shop behavior.
try:
    import shop_runtime_patch
    shop_runtime_patch.install()
except Exception:
    pass

# ---------------------------------------------------------------------------
# Promo codes that grant free cases. run.py is executed as __main__, so its
# functions are patched lazily as soon as its globals become available.
# ---------------------------------------------------------------------------
def _patch_run(frame):
    g = frame.f_globals
    if g.get('__name__') != '__main__' or not str(g.get('__file__','')).lower().endswith('run.py'):
        return False
    if g.get('_wwd_case_promos_done'):
        return True
    required = ('add_promo','use_promo_extended','case','admin_ok','app')
    if not all(k in g for k in required):
        return False

    old_add = g['add_promo']; old_use = g['use_promo_extended']; old_case = g['case']; appmod = g['app']
    async def ensure_case_inventory():
        dbx = await connect()
        await dbx.execute('CREATE TABLE IF NOT EXISTS promo_case_inventory(user_id INTEGER PRIMARY KEY,case1 INTEGER NOT NULL DEFAULT 0,case2 INTEGER NOT NULL DEFAULT 0,president INTEGER NOT NULL DEFAULT 0)')
        await dbx.commit(); await dbx.close()

    async def add_promo(message, parts):
        # /addpromo CODE case case1 2 100
        if len(parts) == 5 and parts[1].lower() in ('case','кейс'):
            if not await g['admin_ok'](message.from_user.id):
                return await message.answer('⛔ Нет доступа.')
            code, _, case_id, amount_s, max_s = parts
            aliases={'1':'case1','case1':'case1','2':'case2','case2':'case2','3':'president','president':'president'}
            case_id=aliases.get(case_id.lower())
            if not case_id or not amount_s.isdigit() or not max_s.isdigit() or int(amount_s)<=0 or int(max_s)<=0:
                return await message.answer('❌ Формат: /addpromo КОД case case1 КОЛИЧЕСТВО ЛИМИТ')
            await ensure_case_inventory()
            dbx=await connect()
            await dbx.execute('''INSERT INTO promos(code,amount,uses,max_uses,reward_type,reward_amount) VALUES(?,0,0,?,?,?) ON CONFLICT(code) DO UPDATE SET amount=0,uses=0,max_uses=excluded.max_uses,reward_type=excluded.reward_type,reward_amount=excluded.reward_amount''',(code,int(max_s),'case:'+case_id,int(amount_s)))
            await dbx.commit(); await dbx.close()
            return await message.answer(f'✅ Промокод создан.\n📦 {case_id} × {amount_s}\n👥 Лимит: {max_s}')
        return await old_add(message, parts)

    async def use_promo_extended(message, code):
        dbx=await connect(); cur=await dbx.execute('SELECT * FROM promos WHERE lower(code)=lower(?)',(code.strip(),)); promo=await cur.fetchone(); await dbx.close()
        if not promo or not str(promo['reward_type'] or '').startswith('case:'):
            return await old_use(message, code)
        if int(promo['uses'])>=int(promo['max_uses']):
            return await message.answer('❌ Промокод больше недоступен.')
        dbx=await connect(); cur=await dbx.execute('SELECT 1 FROM promo_uses WHERE code=? AND user_id=?',(promo['code'],message.from_user.id))
        if await cur.fetchone(): await dbx.close(); return await message.answer('❌ Вы уже использовали этот промокод.')
        await ensure_case_inventory()
        case_id=str(promo['reward_type']).split(':',1)[1]; amount=int(promo['reward_amount'] or 1)
        await dbx.execute('INSERT OR IGNORE INTO promo_case_inventory(user_id) VALUES(?)',(message.from_user.id,))
        await dbx.execute(f'UPDATE promo_case_inventory SET {case_id}={case_id}+? WHERE user_id=?',(amount,message.from_user.id))
        await dbx.execute('UPDATE promos SET uses=uses+1 WHERE code=?',(promo['code'],))
        await dbx.execute('INSERT INTO promo_uses(code,user_id) VALUES(?,?)',(promo['code'],message.from_user.id))
        await dbx.commit(); await dbx.close()
        return await message.answer(f'🎉 Промокод активирован!\n\n📦 Бесплатные кейсы: {case_id} × {amount}')

    async def case(c, cid):
        if cid not in ('case1','case2','president'):
            return await old_case(c,cid)
        await ensure_case_inventory()
        dbx=await connect(); cur=await dbx.execute(f'UPDATE promo_case_inventory SET {cid}={cid}-1 WHERE user_id=? AND {cid}>0',(c.from_user.id,)); await dbx.commit(); await dbx.close()
        if cur.rowcount != 1:
            return await old_case(c,cid)
        pools={'case1':[('soldier',2,75),('interceptor',11,15),('soldier',10,10)],'case2':[('bmp',1,80),('tank',1,10),('helicopter',1,7.5),('plane',1,2.5)],'president':[('helicopter',1,90),('plane',1,8),('missile',1,2)]}
        r=random.uniform(0,100); acc=0
        for unit,amount,chance in pools[cid]:
            acc += chance
            if r < acc: break
        dbx=await connect(); await dbx.execute(f'UPDATE users SET {unit}={unit}+? WHERE user_id=?',(amount,c.from_user.id)); await dbx.commit(); await dbx.close()
        return await appmod.safe(c,f'📦 Бесплатный кейс открыт!\n\n{UNITS[unit]["title"]} × {amount}\n🎲 Шанс: {chance}%',appmod.back('cases'))

    g['add_promo']=add_promo; g['use_promo_extended']=use_promo_extended; g['case']=case; g['_wwd_case_promos_done']=True
    return True

def _trace(frame, event, arg):
    if event in ('line','return'):
        try:
            if _patch_run(frame):
                sys.settrace(None)
                return None
        except Exception:
            pass
    return _trace

try:
    sys.settrace(_trace)
except Exception:
    pass
