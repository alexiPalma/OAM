import bot

_base_safe = bot.safe

def _render(text, u):
    s=str(text or '')
    name='@'+u['username'] if u and u['username'] else 'не указан'
    values={
        'username':name,'name':name,'balance':bot.money(u['balance']) if u else '0',
        'farm':u['farm_level'] if u else 1,'wins':u['attacks_won'] if u else 0,
        'losses':u['attacks_lost'] if u else 0,'cd':bot.cd_text(u) if u else 'ГОТОВО',
        'tax':bot.money(u['tax']) if u else '0','d50':'5 000 000','d100':'11 000 000','d500':'100 000 000',
        'daily':'500 000','contact':'','count':'','status':'','kills':'','army':'','top':'','tasks':'','cases':'','prizes':'','players':'','phrase':'','reward':'','loser_reward':'','report':'','help':'','rules':'','promos':'','earn':'','admins':'','income':''
    }
    for k,v in values.items(): s=s.replace('{'+k+'}',str(v))
    return s

async def safe(c,text,markup=None):
    u=None
    try: u=await bot.user(c.from_user.id)
    except Exception: pass
    return await _base_safe(c,_render(text,u),markup)

bot.safe=safe
