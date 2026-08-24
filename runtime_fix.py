import bot as app
from db import connect,is_admin,setting,set_setting
from config import ADMIN_ID,OWNER_ID,OWNER_ID2,OWNER_IDS,FARMS,UNITS
from datetime import datetime,timedelta,timezone

def _money(v): return f'{int(v):,}'.replace(',',' ')
def _now(): return datetime.now(timezone.utc)
def _tax_for(v): return int(v*.25)
async def _admin(uid):
    try:return bool(await app.admin(uid))
    except Exception:return uid in OWNER_IDS or uid in (OWNER_ID,OWNER_ID2) or await is_admin(uid,ADMIN_ID)

async def farm(c):
    u=await app.user(c.from_user.id);lvl=max(0,min(10,int(u['farm_level'])));f=FARMS[lvl];tax=int(u['tax']);status='🟢 АКТИВНА' if lvl>0 else '⚪ НЕ РАЗВЁРНУТА'
    t=await app.tpl('farm',f'🏭 {app.BRAND} • ФЕРМА\n\nУровень: {lvl}/10\nПроизводство: ${_money(f["income"])}/час\nНалог: ${_money(tax)}\nСтавка налога: 25%\nСтатус: {status}',level=lvl,income=_money(f['income']),tax=_money(tax),status=status)
    await app.safe(c,t,app.kb([[('💰 Получить','payout'),('⬆️ Улучшить','upgrade')],[('💸 Оплатить налог','paytax')],[('⬅️ Назад','home')]]))
async def payout(c):
    u=await app.user(c.from_user.id);lvl=int(u['farm_level'])
    if lvl<=0:return await app.safe(c,'🏭 Сначала улучшите ферму до 1 уровня за $500 000.',app.back('farm'))
    if int(u['tax'])>0:return await app.safe(c,f'❌ Сначала оплатите налог: ${_money(u["tax"])}.',app.back('farm'))
    try:last=datetime.fromisoformat(u['last_payout']);last=last if last.tzinfo else last.replace(tzinfo=timezone.utc)
    except Exception:last=_now()-timedelta(hours=1)
    if _now()-last<timedelta(hours=1):return await app.safe(c,'⏳ Выплата доступна один раз в час.',app.back('farm'))
    income=int(FARMS[lvl]['income']);tax=_tax_for(income);db=await connect();await db.execute('UPDATE users SET balance=balance+?,last_payout=?,tax=? WHERE user_id=?',(income,_now().isoformat(),tax,c.from_user.id));await db.commit();await db.close();await app.safe(c,f'💰 Получено: +${_money(income)}\n💸 Налог 25%: ${_money(tax)}\n\nСледующая выплата — через 1 час.',app.back('farm'))
async def paytax(c):
    u=await app.user(c.from_user.id);tax=int(u['tax'])
    if tax<=0:return await app.safe(c,'✅ Налог к оплате отсутствует.',app.back('farm'))
    if int(u['balance'])<tax:return await app.safe(c,f'❌ Недостаточно средств. Нужно ${_money(tax)}.',app.back('farm'))
    db=await connect();await db.execute('UPDATE users SET balance=balance-?,tax=0 WHERE user_id=?',(tax,c.from_user.id));await db.commit();await db.close();await app.safe(c,f'✅ Налог ${_money(tax)} оплачен.',app.back('farm'))
async def upgrade(c):
    u=await app.user(c.from_user.id);lvl=int(u['farm_level'])
    if lvl>=10:return await app.safe(c,'🏭 Ферма уже на максимальном 10 уровне.',app.back('farm'))
    cost=int(FARMS[lvl+1]['upgrade']);db=await connect();cur=await db.execute('UPDATE users SET balance=balance-?,farm_level=? WHERE user_id=? AND balance>=?',(cost,lvl+1,c.from_user.id,cost));await db.commit();await db.close()
    if cur.rowcount!=1:return await app.safe(c,f'❌ Для {lvl+1} уровня нужно ${_money(cost)}.',app.back('farm'))
    await app.safe(c,f'⬆️ Ферма улучшена: {lvl} → {lvl+1} уровень.\n💵 Списано: ${_money(cost)}',app.back('farm'))

FIXED_QUESTS=[('earn_any','🎁 Получи приз в «Заработать»','$15 000'),('buy_soldier_10','🪖 Купи 10 солдат','$250 000'),('fight_once','⚔️ Сразись','$300 000'),('buy_interceptor_50','🎯 Приобрети 50 перехватчиков','$300 000'),('buy_bmp','🚙 Приобрети БМП','🛩 5 БПЛА + 🪖 10 солдат + 🎯 10 перехватчиков')]
async def quests(c):
    u=await app.user(c.from_user.id);db=await connect();cur=await db.execute('SELECT quest_id FROM quest_claims WHERE user_id=?',(c.from_user.id,));claimed={r['quest_id'] for r in await cur.fetchall()};await db.close()
    done={'earn_any':await app.earn_any_done(c.from_user.id),'buy_soldier_10':int(u['soldier'])>=10,'fight_once':int(u['attacks_won'])+int(u['attacks_lost'])>=1,'buy_interceptor_50':int(u['interceptor'])>=50,'buy_bmp':int(u['bmp'])>=1};rows=[];items=[]
    for qid,title,reward in FIXED_QUESTS:
        if qid in claimed:continue
        items.append(f'{title} — {reward}');rows.append([(f'✅ {title}' if done[qid] else f'🔒 {title}',f'quest:{qid}')])
    if not rows:rows.append([('✅ Все задания выполнены','home')])
    t=await app.tpl('quests',f'📋 {app.BRAND} • ЗАДАНИЯ\n\n'+('\n'.join(items) if items else 'Все задания выполнены.'),tasks='\n'.join(items));rows.append([('⬅️ Назад','home')]);await app.safe(c,t,app.kb(rows))
async def earn(c):
    u=await app.user(c.from_user.id);db=await connect();cur=await db.execute('SELECT id,kind,url,reward FROM earn_tasks WHERE active=1 ORDER BY id');dyn=await cur.fetchall();await db.close();labels={'boost':'🚀 Буст канала / группы','channel':'📢 Подписка на канал','group':'👥 Вход в группу'};rows=[]
    for x in dyn:
        rows.append([(f'{labels.get(x["kind"],x["kind"])} · +${_money(x["reward"])}',x['url'])]);rows.append([('✅ Проверить выполнение',f'earn_check:{x["kind"]}:{x["id"]}')])
    task_text='\n'.join(f'{labels.get(x["kind"],x["kind"])} — +${_money(x["reward"])}' for x in dyn) or 'Пока нет доступных заданий.';rows.append([('⬅️ Назад','home')]);t=await app.tpl('earn',f'💰 {app.BRAND} • ЗАРАБОТАТЬ\n\n{task_text}',balance=_money(u['balance']),tasks=task_text);await app.safe(c,t,app.kb(rows))

async def _kw_army(m):
    u=await app.user(m.from_user.id);kw={k:int(u[k]) for k in UNITS};kw['username']='@'+u['username'] if u['username'] else 'не указан';t=await app.tpl('army',f'🎖 {app.BRAND} • АРМИЯ\n\n{app.army_text(u)}',**kw);await m.answer(t,reply_markup=app.back())
async def _kw_farm(m):
    u=await app.user(m.from_user.id);lvl=int(u['farm_level']);f=FARMS[lvl];status='🟢 АКТИВНА' if lvl>0 else '⚪ НЕ РАЗВЁРНУТА';t=await app.tpl('farm',f'🏭 {app.BRAND} • ФЕРМА\n\nУровень: {lvl}/10\nПроизводство: ${_money(f["income"])}/час\nНалог: ${_money(u["tax"])}\nСтатус: {status}',level=lvl,income=_money(f['income']),tax=_money(u['tax']),status=status);await m.answer(t,reply_markup=app.kb([[('💰 Получить','payout'),('⬆️ Улучшить','upgrade')],[('💸 Оплатить налог','paytax')],[('⬅️ Назад','home')]]))
async def _kw_donate(m):
    from config import DONATIONS
    from settings import get_str
    contact=await get_str('donate_contact');t=await app.tpl('donate',f'💳 {app.BRAND} • ДОНАТ\n\n50 ⭐ — ${_money(DONATIONS[50])}\n100 ⭐ — ${_money(DONATIONS[100])}\n500 ⭐ — ${_money(DONATIONS[500])}\n\n📨 {contact}',donate50=_money(DONATIONS[50]),donate100=_money(DONATIONS[100]),donate500=_money(DONATIONS[500]),contact=contact);await m.answer(t,reply_markup=app.back())
async def _kw_rules(m):
    t=await app.tpl('rules',f'📕 {app.BRAND} • ПРАВИЛА\n\n1. Развивайте армию.\n2. Атаки имеют КД 10 минут.',username='@'+m.from_user.username if m.from_user.username else 'не указан');await m.answer(t,reply_markup=app.back())
async def _kw_help(m):
    t=await app.tpl('help',f'ℹ️ {app.BRAND} • ПОМОЩЬ\n\nРазвивайте ферму, покупайте армию и участвуйте в боях.',username='@'+m.from_user.username if m.from_user.username else 'не указан');await m.answer(t,reply_markup=app.back())
async def _kw_shop(m):
    items='\n'.join(f'{v["title"]} — ${_money(v["price"])}' for k,v in UNITS.items() if k!='artillery');rows=[[(f'{v["title"]} — ${_money(v["price"])}',f'buyq:{k}')] for k,v in UNITS.items() if k!='artillery'];rows.append([('⬅️ Назад','home')]);t=await app.tpl('shop',f'🛒 {app.BRAND} • ВОЕННЫЙ АРСЕНАЛ\n\n{items}\n\nВыберите единицу и введите количество.');await m.answer(t,reply_markup=app.kb(rows))
async def _kw_attack(m):
    u=await app.user(m.from_user.id);left=app.cd_seconds(u)
    if left:
        t=await app.tpl('attack',f'⚔️ {app.BRAND} • АТАКА\n\n⏳ КД: {left//60:02d}:{left%60:02d}',count=0,page=1,pages=1);return await m.answer(t,reply_markup=app.back())
    db=await connect();cur=await db.execute('SELECT * FROM users WHERE user_id!=? ORDER BY balance DESC',(m.from_user.id,));allrows=await cur.fetchall();await db.close();players=[r for r in allrows if not app.cd_seconds(r) and app.army_size(r)>0];per=10;pages=max(1,(len(players)+per-1)//per);rows=[]
    for p in players[:per]:
        n='@'+p['username'] if p['username'] else f'ID {p["user_id"]}';rows.append([(f'⚔️ {n} · {app.army_size(p)} ед.',f'opp:{p["user_id"]}')])
    if pages>1:rows.append([('➡️ Далее','attack_page:1')])
    rows.append([('⬅️ Назад','home')]);t=await app.tpl('attack',f'⚔️ {app.BRAND} • ВЫБОР ПРОТИВНИКА\n\nДоступно: {len(players)}\nСтраница 1/{pages}\n\nВыберите противника:',count=len(players),page=1,pages=pages);await m.answer(t,reply_markup=app.kb(rows))

async def _edit_menu(c):
    rows=[]
    for key,info in app.EDIT_FIELDS.items():rows.append([(f'✏️ {info[0]}',f'editmsg:{key}')])
    rows.append([('📋 Задания','editmsg:quests')]);rows.append([('⬅️ Назад','admin')]);await app.safe(c,'✏️ РЕДАКТИРОВАТЬ\n\nВыберите конкретное сообщение. Каждый пункт имеет свой ключ, поэтому изменение одного текста не меняет другой.',app.kb(rows))
async def _edit_start(c,key):
    fields=dict(app.EDIT_FIELDS);fields['quests']=('Задания','{tasks} — список текущих заданий')
    if key not in fields:return await c.answer('Сообщение не найдено.',show_alert=True)
    title,docs=fields[key];current=await setting('msg_'+key);app.STATE[c.from_user.id]=('editmsg',key);await app.safe(c,f'✏️ {title}\n\nТЕКУЩИЙ ТЕКСТ:\n\n{current or "(стандартный текст)"}\n\nДоступные параметры:\n{docs}\n\nОтправьте новый полный текст одним сообщением.',app.kb([[('⬅️ Назад','a_edit')]]))
async def _admin_section(c,s):
    if not await _admin(c.from_user.id):return await c.answer('⛔ Нет доступа.',show_alert=True)
    if s=='a_edit':return await _edit_menu(c)
    if s=='a_tasks':return await app.safe(c,'📋 ЗАДАНИЯ\n\nФиксированные задания находятся у игроков в разделе «Задания».',app.back('admin'))
    if s=='a_earn':return await app.safe(c,'💰 ЗАРАБОТАТЬ\n\nЗдесь находятся только добавленные вами задания:\n🚀 Буст канала / группы\n📢 Подписка на канал\n👥 Вход в группу',app.kb([[('🚀 Буст канала / группы','earn_add:boost')],[('📢 Подписка на канал','earn_add:channel')],[('👥 Вход в группу','earn_add:group')],[('📋 Список добавленных','earn_list')],[('⬅️ Назад','admin')]]))
    return await app._original_admin_section(c,s)

async def text_handler(m,bot):
    text=(m.text or '').strip();p=text.split();cmd=p[0].split('@')[0].lower() if p else '';low=text.lower();st=app.STATE.get(m.from_user.id)
    if st and st[0]=='editmsg' and await _admin(m.from_user.id):
        key=st[1]
        if key in set(app.EDIT_FIELDS)|{'quests'}:
            await set_setting('msg_'+key,m.text or '');app.STATE.pop(m.from_user.id,None);return await m.answer('✅ Текст сохранён. Изменяется только выбранный пункт.')
    if not text.startswith('/'):
        if low in ('a','а','армия'):return await _kw_army(m)
        if low=='ферма':return await _kw_farm(m)
        if low in ('б','баланс'):return await app.balance_from_message(m)
        if low=='донат':return await _kw_donate(m)
        if low=='шоп':return await _kw_shop(m)
        if low=='правила':return await _kw_rules(m)
        if low=='помощь':return await _kw_help(m)
        if low=='вызовы':return await app.attack_from_message(m)
        if low=='атака':return await _kw_attack(m)
        if p and p[0].lower() in ('атака','атак') and len(p)>=2:return await app.attack_by_username(m,p[1])
        if low.startswith(('промокод ','промо ','promo ')):return await app.use_promo(m,p[1])
        if low in ('промо','промокод','promo'):app.STATE[m.from_user.id]=('promo',None);return await m.answer('🎟 Введите промокод:')
        if low in ('адм','админ'):return await app.admin_panel(m) if await _admin(m.from_user.id) else await m.answer('⛔ Нет доступа.')
    if text.startswith('/'):
        if cmd in ('/promo','/промо','/промокод'):
            if len(p)>=2:return await app.use_promo(m,p[1])
            app.STATE[m.from_user.id]=('promo',None);return await m.answer('🎟 Введите промокод:')
        if cmd in ('/attack','/atack'):
            if len(p)>=2:return await app.attack_by_username(m,p[1])
            return await app.attack_from_message(m)
        if cmd in ('/addboost','/addchannel','/addgroup') and await _admin(m.from_user.id) and len(p)==3:
            url=p[1];reward=int(p[2]) if p[2].isdigit() else 0
            if not url.startswith(('https://t.me/','http://t.me/')) or reward<=0:return await m.answer(f'❌ Формат: {cmd} https://t.me/... 150000')
            kind={'/addboost':'boost','/addchannel':'channel','/addgroup':'group'}[cmd];db=await connect();await db.execute('INSERT OR IGNORE INTO earn_tasks(kind,url,reward) VALUES(?,?,?)',(kind,url,reward));await db.commit();await db.close();return await m.answer('✅ Добавлено в «Заработать».')
        if cmd=='/createpromo' and await _admin(m.from_user.id) and len(p)==4:
            code=p[1].upper();amount=int(p[2]) if p[2].isdigit() else 0;limit=int(p[3]) if p[3].isdigit() else 0
            if not code or amount<=0 or limit<=0:return await m.answer('❌ Формат: /createpromo КОД СУММА ЛИМИТ')
            db=await connect();await db.execute('INSERT OR REPLACE INTO promos(code,amount,max_uses,uses) VALUES(?,?,?,0)',(code,amount,limit));await db.commit();await db.close();return await m.answer('✅ Промокод создан.')
        if cmd=='/deletepromo' and await _admin(m.from_user.id) and len(p)==2:
            db=await connect();await db.execute('DELETE FROM promos WHERE lower(code)=lower(?)',(p[1],));await db.execute('DELETE FROM promo_uses WHERE lower(code)=lower(?)',(p[1],));await db.commit();await db.close();return await m.answer('✅ Промокод удалён.')
        if cmd=='/givecash' and await _admin(m.from_user.id) and len(p)==3:
            target=await app.find_user(p[1]);amount=int(p[2]) if p[2].isdigit() else 0
            if not target or amount<=0:return await m.answer('❌ Неверные данные.')
            db=await connect();await db.execute('UPDATE users SET balance=balance+? WHERE user_id=?',(amount,target['user_id']));await db.commit();await db.close();return await m.answer('✅ Валюта выдана.')
        if cmd=='/givepehot' and await _admin(m.from_user.id) and len(p)==4:
            target=await app.find_user(p[1]);uid=int(p[2]) if p[2].isdigit() else 0;q=int(p[3]) if p[3].isdigit() else 0
            if not target or uid not in app.UNIT_BY_ID or q<=0:return await m.answer('❌ Неверные данные.')
            unit=app.UNIT_BY_ID[uid];db=await connect();await db.execute(f'UPDATE users SET {unit}={unit}+? WHERE user_id=?',(q,target['user_id']));await db.commit();await db.close();return await m.answer('✅ Выдано.')
        if cmd in ('/adm','/admin'):return await app.admin_panel(m) if await _admin(m.from_user.id) else await m.answer('⛔ Нет доступа.')
    return await app._original_text_handler(m,bot)

async def callback(c,bot):
    d=c.data or ''
    try:
        if d=='quests':return await quests(c)
        if d=='earn':return await earn(c)
        if d=='a_tasks':return await app.safe(c,'📋 ЗАДАНИЯ\n\nФиксированные задания находятся у игроков в разделе «Задания».',app.back('admin'))
        if d=='a_edit':return await _edit_menu(c)
        if d.startswith('editmsg:'):return await _edit_start(c,d.split(':',1)[1])
        if d=='farm':return await farm(c)
        if d=='payout':return await payout(c)
        if d=='paytax':return await paytax(c)
        if d=='upgrade':return await upgrade(c)
        return await app._original_callback(c,bot)
    except Exception as e:
        try:await c.answer('Произошла ошибка. Попробуйте ещё раз.',show_alert=True)
        except Exception:pass
        print('callback error:',repr(e))

def _home_kb_with_quests(a=False):
    rows=[[('🏭 Ферма','farm'),('🎖 Армия','army')],[('🛒 Арсенал','shop'),('⚔️ Атака','attack')],[('💰 Заработать','earn'),('📋 Задания','quests')],[('🎁 Бонус','bonus'),('🎟 Промокод','promo')],[('📦 Кейсы','cases'),('👤 Профиль','profile')],[('🏆 Топ вояк','top'),('💳 Донат','donate')],[('📕 Правила','rules'),('ℹ️ Помощь','help')]]
    if a:rows.append([('⚙️ Админ-панель','admin')])
    return app.kb(rows)

def install():
    if not hasattr(app,'_wwd_original_admin_section'):
        app._wwd_original_admin_section=app.admin_section;app._wwd_original_text_handler=app.text_handler;app._wwd_original_callback=app.callback;app._wwd_original_home_kb=app.home_kb
    app._original_admin_section=app._wwd_original_admin_section;app._original_text_handler=app._wwd_original_text_handler;app._original_callback=app._wwd_original_callback
    app.admin_section=_admin_section;app.text_handler=text_handler;app.callback=callback;app.home_kb=_home_kb_with_quests
    app.farm=farm;app.payout=payout;app.paytax=paytax;app.upgrade=upgrade;app.quests=quests;app.earn=earn
