from db import setting, set_setting
DEFAULTS={
'channel_username':'','subscription_bonus':'1500000','daily_bonus':'500000','donate_contact':'@admin','help_text':'📖 <b>WorldWarDynasty • ПОМОЩЬ</b>\n\nРазвивай ферму, покупай армию и участвуй в боях. Все действия выполняются через меню /start.','rules_text':'📕 <b>WorldWarDynasty • ПРАВИЛА</b>\n\n1. Одна атака в час.\n2. После боя проигравший теряет 20% армии.\n3. Победитель получает 5% стоимости уничтоженных единиц.\n4. Проигравший получает 2% стоимости своих потерь.','tax_increment_min':'20000','tax_increment_max':'50000','tax_max':'1000000','attack_cooldown_minutes':'60','loss_percent':'20','kill_reward_percent':'5','loser_reward_percent':'2',
'farm_1_income':'15000','farm_2_income':'36000','farm_3_income':'50000','farm_4_income':'50000','farm_5_income':'100000','farm_6_income':'140000','farm_7_income':'220000','farm_8_income':'333000','farm_9_income':'777000','farm_10_income':'899000','farm_2_upgrade':'900000','farm_3_upgrade':'1000000','farm_4_upgrade':'2000000','farm_5_upgrade':'3000000','farm_6_upgrade':'6000000','farm_7_upgrade':'9000000','farm_8_upgrade':'11000000','farm_9_upgrade':'18000000','farm_10_upgrade':'30000000',
'price_soldier':'20000','price_interceptor':'4000','price_drone':'120000','price_bmp':'1000000','price_tank':'3000000','price_helicopter':'4000000','price_plane':'6000000','price_missile':'20000000',
'donate_50':'5000000','donate_100':'11000000','donate_500':'100000000'}
async def init_settings(owner_id):
    for k,v in DEFAULTS.items():
        if await setting(k) is None: await set_setting(k,v)
    await set_setting('owner_id',str(owner_id))
async def get_int(key): return int(await setting(key,DEFAULTS.get(key,'0')))
async def get_str(key): return str(await setting(key,DEFAULTS.get(key,'')))
