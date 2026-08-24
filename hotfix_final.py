import bot as app
from hotfix_2026_08_24 import admin, promo_apply

async def text_handler(m,bot):
    text=(m.text or '').strip();low=text.lower();p=text.split();cmd=p[0].split('@')[0].lower() if p else ''
    if low in ('хелп','help'):
        t=await app.tpl('help',f'ℹ️ {app.BRAND} • ПОМОЩЬ\n\nРазвивайте ферму, покупайте армию и участвуйте в боях.',username='@'+m.from_user.username if m.from_user.username else 'не указан')
        return await m.answer(t,reply_markup=app.back())
    st=app.STATE.get(m.from_user.id)
    if st and st[0]=='promo' and not text.startswith('/'):
        app.STATE.pop(m.from_user.id,None)
        return await promo_apply(m,text)
    if low in ('адм','админ'):
        return await app.admin_panel(m) if await admin(m.from_user.id) else await m.answer('⛔ Нет доступа.')
    if low=='атаковать': return await app.attack_from_message(m)
    if p and p[0].lower()=='атаковать' and len(p)>=2:return await app.attack_by_username(m,p[1])
    if low.startswith(('промокод ','промо ','promo ')):return await promo_apply(m,p[1])
    if text.startswith('/') and cmd in ('/adm','/admin'):
        return await app.admin_panel(m) if await admin(m.from_user.id) else await m.answer('⛔ Нет доступа.')
    if text.startswith('/') and cmd in ('/promo','/промо','/промокод'):
        if len(p)>=2:return await promo_apply(m,p[1])
        app.STATE[m.from_user.id]=('promo',None);return await m.answer('🎟 Введите промокод:')
    return await app._hotfix_text_handler(m,bot)

def install():
    app._hotfix_text_handler=app.text_handler
    app.text_handler=text_handler
