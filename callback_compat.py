"""Stable final callback/text adapter for the WorldWarDynasty bot."""
import bot as app
import achievements
from config import OWNER_ID, OWNER_ID2, OWNER_IDS, ADMIN_ID, UNITS
from db import connect, is_admin


def _is_admin(uid): return uid in OWNER_IDS or uid in (OWNER_ID, OWNER_ID2)
async def _admin_ok(uid):
    if _is_admin(uid): return True
    try: return bool(await is_admin(uid, ADMIN_ID))
    except Exception: return False

async def _admin_panel(c):
    if not await _admin_ok(c.from_user.id): return await c.answer('⛔ Нет доступа.', show_alert=True)
    await app.safe(c,'⚙️ WorldWarDynasty • АДМИН-ПАНЕЛЬ\n\nВыберите раздел. Все действия доступны только владельцам/админам.',app.admin_kb())

async def _admin_message(m):
    if not await _admin_ok(m.from_user.id): return await m.answer('⛔ Нет доступа.')
    return await m.answer('⚙️ WorldWarDynasty • АДМИН-ПАНЕЛЬ\n\nВыберите раздел. Все действия доступны только владельцам/админам.',reply_markup=app.admin_kb())

async def _admin_section(c,data):
    if not await _admin_ok(c.from_user.id): return await c.answer('⛔ Нет доступа.',show_alert=True)
    fn=getattr(app,'_admin_section',None)
    if fn is not None:
        try: return await fn(c,data)
        except (AttributeError,TypeError): pass
    titles={'a_currency':'💰 ВАЛЮТА','a_bonus':'🎁 БОНУСЫ','a_cases':'📦 КЕЙСЫ','a_promos':'🎟 ПРОМОКОДЫ','a_earn':'💰 ЗАРАБОТАТЬ','a_donate':'💳 ДОНАТ','a_rules':'📕 ПРАВИЛА','a_admins':'👥 АДМИНЫ','a_give':'🎖 ВЫДАТЬ / СПИСАТЬ','a_broadcast':'📣 РАССЫЛКА','a_stats':'📊 СТАТИСТИКА','a_edit':'✏️ РЕДАКТИРОВАТЬ','a_farms':'🏭 ФЕРМЫ','a_battles':'⚔️ БОИ','a_owner2':'👑 ВЛАДЕЛЕЦ 2'}
    if data=='a_promos': return await app.safe(c,'🎟 ПРОМОКОДЫ\n\nДеньги:\n/addpromo КОД СУММА ЛИМИТ\n\nТехника:\n/addpromo КОД soldier|interceptor|drone|bmp|tank|helicopter|plane|missile|artillery КОЛИЧЕСТВО ЛИМИТ',app.back('admin'))
    if data=='a_give': return await app.safe(c,'🎖 ВЫДАТЬ / СПИСАТЬ\n\nВалюта:\n/takecash @username сумма\n\nТехника:\n/takeunit @username unit количество\n\nДоступные unit:\n'+', '.join(UNITS.keys()),app.back('admin'))
    if data=='a_owner2': return await app.safe(c,'👑 ВЛАДЕЛЕЦ 2\n\nВторой ID задаётся через OWNER_ID2 в .env.\nПосле изменения перезапустите бота.',app.back('admin'))
    if data=='a_edit' and hasattr(app,'edit_menu'): return await app.edit_menu(c)
    return await app.safe(c,titles.get(data,'⚙️ АДМИН-ПАНЕЛЬ')+'\n\nРаздел открыт.',app.back('admin'))

async def _takeunit(m,parts):
    if not await _admin_ok(m.from_user.id): return await m.answer('⛔ Нет доступа.')
    if len(parts)!=3: return await m.answer('❌ Формат: /takeunit @username unit количество')
    target=await app.find_user(parts[0]);unit=parts[1].lower()
    try: amount=int(parts[2])
    except ValueError: amount=0
    if not target: return await m.answer('❌ Пользователь не найден.')
    if unit not in UNITS or amount<=0: return await m.answer('❌ Неверная техника или количество.\nДоступно: '+', '.join(UNITS.keys()))
    db=await connect()
    try:
        cur=await db.execute(f'UPDATE users SET {unit}=MAX(0,{unit}-?) WHERE user_id=?',(amount,target['user_id']))
        await db.commit()
    finally: await db.close()
    if cur.rowcount!=1: return await m.answer('❌ Не удалось изменить армию пользователя.')
    return await m.answer(f"✅ Списано: {amount} × {UNITS[unit]['title']} у @{target['username'] or target['user_id']}.")

def install():
    previous_callback=app.callback
    previous_text=getattr(app,'text_handler',None)
    async def callback(c):
        data=c.data or ''
        if data=='achievements': return await achievements.menu(c)
        if data.startswith('ach:'): return await achievements.detail(c,data.split(':',1)[1])
        if data.startswith('ach_claim:'): return await achievements.claim(c,data.split(':',1)[1])
        if data=='admin': return await _admin_panel(c)
        if data.startswith('a_'): return await _admin_section(c,data)
        return await previous_callback(c,c.bot)
    async def text_handler(m,bot):
        text=(m.text or '').strip();parts=text.split();low=text.lower()
        if low in ('адм','админ','/адм','/админ','/admin','/adm'): return await _admin_message(m)
        if parts and parts[0].split('@')[0].lower()=='/takeunit': return await _takeunit(m,parts[1:])
        return await previous_text(m,bot)
    app.callback=callback
    if previous_text is not None: app.text_handler=text_handler
