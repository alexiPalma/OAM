from battle_runtime import cooldown_seconds, kb, money, show
from db import user
from config import UNITS

async def profile(c):
    u=await user(c.from_user.id)
    name='@'+u['username'] if u['username'] else 'не указан'
    kills=[('🪖 Пехота','kill_soldier'),('🎯 Перехватчики','kill_interceptor'),('🛩 БПЛА','kill_drone'),('🚙 БМП','kill_bmp'),('🛡 Танки','kill_tank'),('🚁 Вертолёты','kill_helicopter'),('✈️ Самолёты','kill_plane'),('🚀 Ракеты','kill_missile'),('💥 Артиллерия','kill_artillery')]
    kt='\n'.join(f'{title}: {int(u[col])}' for title,col in kills)
    left=cooldown_seconds(u)
    cd=f'{left//60:02d}:{left%60:02d}' if left else 'ГОТОВО'
    text=(f'🛰 WorldWarDynasty • ЛИЧНОЕ ДОСЬЕ\n\n'
          f'👤 Позывной: {name}\n💵 Капитал: ${money(u["balance"])}\n'
          f'🏭 Ферма: {u["farm_level"]}/10\n🏆 Побед: {u["attacks_won"]}\n'
          f'💀 Поражений: {u["attacks_lost"]}\n⚔️ КД атаки: {cd}\n\n'
          f'🎯 УНИЧТОЖЕНО\n{kt}')
    await show(c,text,kb([[('⬅️ Назад','home')]]))

def install(bot_module):
    bot_module.profile=profile
